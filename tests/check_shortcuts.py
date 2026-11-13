"""Test shortcut setup in temporary homes; never launch a real terminal or use dconf.

Usage: python3 tests/check_shortcuts.py
GNOME checks use the real gsettings command with an isolated keyfile backend.
"""

import ast
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts/setup-shortcuts.py"
MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM = MEDIA_KEYS + ".custom-keybinding:"
SHORTCUT = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/rspb-terminal/"


class ShortcutsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rspb-shortcuts-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.home = self.work / "pi's home"
        self.home.mkdir()
        self.config = self.home / ".config"
        self.launcher = self.home / ".local/bin/rspb-terminal"
        self.env = {
            "HOME": str(self.home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "XDG_CONFIG_HOME": str(self.config), "XDG_CONFIG_DIRS": str(self.work / "etc"),
            "GSETTINGS_BACKEND": "keyfile",
        }

    def run_command(self, *args, check=True):
        result = subprocess.run(args, env=self.env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def setup_shortcuts(self, *args, check=True):
        return self.run_command(sys.executable, str(SETUP), *args, check=check)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_terminal_preference_and_default_fallbacks(self):
        self.setup_shortcuts()
        self.assertTrue(os.access(self.launcher, os.X_OK))
        stub_bin = self.work / "bin"
        self.env["PATH"] = str(stub_bin)
        choices = [self.home / ".cargo/bin/alacritty", stub_bin / "xdg-terminal-exec",
                   stub_bin / "x-terminal-emulator"]
        for executable in choices:
            self.write(executable, f"#!/bin/sh\nprintf '%s\\n' '{executable.name}' \"$@\"\n")
            executable.chmod(0o755)
        for executable in choices:
            self.assertEqual(self.run_command(str(self.launcher), "two words").stdout,
                             executable.name + "\ntwo words\n")
            executable.unlink()
        self.assertNotEqual(self.run_command(str(self.launcher), check=False).returncode, 0)
        cargo = self.work / "custom cargo"
        self.env["CARGO_HOME"] = str(cargo)
        self.write(cargo / "bin/alacritty", "#!/bin/sh\nprintf 'custom cargo\\n'\n").chmod(0o755)
        self.assertEqual(self.run_command(str(self.launcher)).stdout, "custom cargo\n")

    def test_headless_and_unsupported_desktops_do_not_register(self):
        self.env["XDG_CURRENT_DESKTOP"] = "GNOME"
        self.assertIn("not registered", self.setup_shortcuts().stdout)
        self.env.update(DISPLAY=":99", XDG_CURRENT_DESKTOP="KDE")
        self.assertIn("not registered", self.setup_shortcuts().stdout)
        self.assertFalse(self.config.exists())

    def test_labwc_preserves_settings_backup_and_symlink_on_repeat(self):
        original = '''<?xml version="1.0"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <!-- Keep my other settings -->
  <theme><name>PiXflat</name></theme>
  <keyboard><default/><keybind key="C-A-t"><action name="Execute"><command>lxterminal</command></action></keybind>
    <keybind key="A-Return"><action name="ToggleMaximize"/></keybind>
    <keybind key="Mod1-Return"><action name="Execute" command="old-terminal"/></keybind>
  </keyboard>
</openbox_config>
'''
        target = self.write(self.config / "shared.xml", original)
        path = self.config / "labwc/rc.xml"
        path.parent.mkdir()
        path.symlink_to(target)
        self.env.update(WAYLAND_DISPLAY="wayland-test", XDG_CURRENT_DESKTOP="LXDE-pi:labwc")
        self.setup_shortcuts()
        first = path.read_bytes()
        root = ET.fromstring(first)
        ns = {"c": "http://openbox.org/3.4/rc"}
        self.assertEqual(root.findtext("c:theme/c:name", namespaces=ns), "PiXflat")
        self.assertIn(b"Keep my other settings", first)
        bindings = {item.get("key"): item for item in root.findall("c:keyboard/c:keybind", ns)}
        self.assertEqual(set(bindings), {"C-A-t", "A-Return"})
        self.assertEqual(bindings["C-A-t"].findtext("c:action/c:command", namespaces=ns), "lxterminal")
        command = bindings["A-Return"].findtext("c:action/c:command", namespaces=ns)
        self.assertEqual(shlex.split(command), [str(self.launcher)])
        self.setup_shortcuts()
        self.assertEqual(path.read_bytes(), first)
        self.assertTrue(path.is_symlink())
        self.assertEqual(target.with_name("shared.xml.rspb-backup").read_text(), original)

    def test_labwc_inherits_system_settings_and_keeps_implicit_defaults(self):
        system = self.write(self.work / "etc/labwc/rc.xml",
                            '<labwc_config><theme><name>System</name></theme><keyboard><numlock>off</numlock></keyboard></labwc_config>')
        original = system.read_bytes()
        self.setup_shortcuts("--desktop", "labwc")
        root = ET.parse(self.config / "labwc/rc.xml").getroot()
        self.assertEqual(root.findtext("theme/name"), "System")
        self.assertIsNotNone(root.find("keyboard/default"))
        self.assertEqual(system.read_bytes(), original)

    def test_labwc_fresh_config_and_invalid_xml(self):
        self.setup_shortcuts("--desktop", "labwc")
        path = self.config / "labwc/rc.xml"
        self.assertIsNotNone(ET.parse(path).find("keyboard/default"))
        path.write_text("<broken")
        self.assertNotEqual(self.setup_shortcuts("--desktop", "labwc", check=False).returncode, 0)
        self.assertEqual(path.read_text(), "<broken")

    def gget(self, schema, key):
        return ast.literal_eval(self.run_command("gsettings", "get", schema, key).stdout.removeprefix("@as "))

    def gset(self, schema, key, value):
        self.run_command("gsettings", "set", schema, key, json.dumps(value))

    def require_gnome(self):
        if not shutil.which("gsettings") or MEDIA_KEYS not in self.run_command("gsettings", "list-schemas").stdout.splitlines():
            self.skipTest("GNOME schemas / gsettings are not installed")
        self.env.update(DISPLAY=":99", XDG_CURRENT_DESKTOP="ubuntu:GNOME")

    def test_gnome_fresh_setup(self):
        self.require_gnome()
        self.assertEqual(self.gget(MEDIA_KEYS, "custom-keybindings"), [])
        self.setup_shortcuts()
        self.assertEqual(self.gget(MEDIA_KEYS, "custom-keybindings"), [SHORTCUT])
        self.assertEqual(shlex.split(self.gget(CUSTOM + SHORTCUT, "command")), [str(self.launcher)])
        self.assertEqual(self.gget(CUSTOM + SHORTCUT, "binding"), "<Alt>Return")

    def test_gnome_preserves_other_shortcuts_and_handles_conflicts_on_repeat(self):
        self.require_gnome()
        unrelated, conflicting = "/custom/unrelated/", "/custom/conflicting/"
        self.gset(MEDIA_KEYS, "custom-keybindings", [unrelated, conflicting])
        for path, binding in [(unrelated, "<Super>e"), (conflicting, "<Alt>Return")]:
            for key, value in {"name": "Existing", "command": "existing-command", "binding": binding}.items():
                self.gset(CUSTOM + path, key, value)
        self.setup_shortcuts()
        backup = (self.config / "rspb/gnome-shortcuts-before.json").read_bytes()
        self.setup_shortcuts()
        self.assertEqual(self.gget(MEDIA_KEYS, "custom-keybindings"), [unrelated, conflicting, SHORTCUT])
        self.assertEqual(self.gget(CUSTOM + unrelated, "binding"), "<Super>e")
        self.assertEqual(self.gget(CUSTOM + unrelated, "command"), "existing-command")
        self.assertEqual(self.gget(CUSTOM + conflicting, "binding"), "")
        self.assertEqual(json.loads(backup)["bindings"][conflicting]["binding"], "<Alt>Return")
        self.assertEqual((self.config / "rspb/gnome-shortcuts-before.json").read_bytes(), backup)

    def test_gnome_failed_persistence_is_reported(self):
        self.require_gnome()
        self.env["GSETTINGS_BACKEND"] = "memory"
        result = self.setup_shortcuts(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not save GNOME shortcuts", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
