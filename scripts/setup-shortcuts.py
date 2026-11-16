#!/usr/bin/env python3
"""Set Alt+Enter (terminal) and Alt+Backspace (close window) on GNOME or labwc."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
WM_KEYS = "org.gnome.desktop.wm.keybindings"
CUSTOM_KEY = MEDIA_KEYS + ".custom-keybinding:"
SHORTCUT_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/rspb-terminal/"
CLOSE_BINDINGS = ("<alt>backspace", "<mod1>backspace")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def gget(schema, key):
    # gsettings prints empty arrays as '@as []', other values as GVariant literals.
    value = run("gsettings", "get", schema, key)
    return ast.literal_eval(value.removeprefix("@as "))


def gset(schema, key, value):
    run("gsettings", "set", schema, key, json.dumps(value, ensure_ascii=False))
    # dconf can report a missing session bus on stderr while still exiting with 0.
    if gget(schema, key) != value:
        raise RuntimeError("Could not save GNOME shortcuts; run this from a desktop terminal.")


def setup_gnome(launcher, config_home):
    paths = gget(MEDIA_KEYS, "custom-keybindings")
    close_bindings = gget(WM_KEYS, "close")
    old_values = {
        path: {key: gget(CUSTOM_KEY + path, key) for key in ("name", "command", "binding")}
        for path in dict.fromkeys([*paths, SHORTCUT_PATH])
    }
    conflicts = [path for path in paths if path != SHORTCUT_PATH
                 and old_values[path]["binding"].lower() in
                 ("<alt>return", "<mod1>return", *CLOSE_BINDINGS)]
    backup = config_home / "rspb/gnome-shortcuts-before.json"
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(json.dumps({"custom-keybindings": paths, "bindings": old_values},
                                    ensure_ascii=False, indent=2) + "\n")
    # Existing installs already have the Alt+Enter backup. Capture the close
    # bindings separately, before changing them, without overwriting that backup.
    close_backup = config_home / "rspb/gnome-close-before.json"
    if not close_backup.exists():
        close_backup.write_text(json.dumps({
            "close": close_bindings,
            "bindings": {path: old_values[path] for path in conflicts
                         if old_values[path]["binding"].lower() in CLOSE_BINDINGS},
        }, ensure_ascii=False, indent=2) + "\n")
    for path in conflicts:
        gset(CUSTOM_KEY + path, "binding", "")
    for key, value in {"name": "Terminal (rspb)", "command": shlex.quote(str(launcher)),
                       "binding": "<Alt>Return"}.items():
        gset(CUSTOM_KEY + SHORTCUT_PATH, key, value)
    if SHORTCUT_PATH not in paths:
        gset(MEDIA_KEYS, "custom-keybindings", [*paths, SHORTCUT_PATH])
    if not any(binding.lower() in CLOSE_BINDINGS for binding in close_bindings):
        gset(WM_KEYS, "close", [*close_bindings, "<Alt>BackSpace"])
    print("Alt+Enter: Alacritty / default terminal (GNOME).")
    print("Alt+Backspace: close the active window (GNOME).")


def write_labwc_config(path, data):
    # Preserve symlinks and keep a copy of the user's original configuration.
    path = path.resolve()
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".rspb-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(mode)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def setup_labwc(launcher, config_home):
    path = config_home / "labwc/rc.xml"
    system_dirs = (os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":")
    candidates = [path, *(Path(directory) / "labwc/rc.xml" for directory in system_dirs if directory)]
    source = next((candidate for candidate in candidates if candidate.is_file()), None)
    if source:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        root = ET.parse(source, parser=parser).getroot()
    else:
        root = ET.Element("labwc_config")
    namespace, _, name = root.tag.rpartition("}")
    if name not in ("labwc_config", "openbox_config"):
        raise RuntimeError(f"Unexpected labwc configuration root: {root.tag}")
    prefix = namespace + "}" if namespace else ""
    if namespace:
        ET.register_namespace("", namespace[1:])
    keyboards = root.findall(prefix + "keyboard")
    if not keyboards:
        keyboards = [ET.SubElement(root, prefix + "keyboard")]
    # Adding the first explicit keybind must not disable labwc's default bindings.
    if not any(keyboard.findall(prefix + "keybind") or keyboard.find(prefix + "default") is not None
               for keyboard in keyboards):
        ET.SubElement(keyboards[0], prefix + "default")
    for keyboard in keyboards:
        for binding in keyboard.findall(prefix + "keybind"):
            if binding.get("key", "").lower() in ("a-return", "mod1-return", "a-backspace", "mod1-backspace"):
                keyboard.remove(binding)
    binding = ET.SubElement(keyboards[0], prefix + "keybind", key="A-Return")
    action = ET.SubElement(binding, prefix + "action", name="Execute")
    ET.SubElement(action, prefix + "command").text = shlex.quote(str(launcher))
    close_binding = ET.SubElement(keyboards[0], prefix + "keybind", key="A-BackSpace")
    ET.SubElement(close_binding, prefix + "action", name="Close")
    ET.indent(root, space="  ")
    write_labwc_config(path, ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n")
    print(f"Alt+Enter: Alacritty / default terminal (labwc: {path}).")
    print("Alt+Backspace: close the active window (labwc).")
    if os.environ.get("LABWC_PID") and shutil.which("labwc"):
        try:
            run("labwc", "--reconfigure")
        except subprocess.CalledProcessError:
            print("Log out and back in to activate the shortcut (labwc reload failed).")
    else:
        print("Log out and back in to activate the shortcut.")


def detect_desktop():
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    desktop = ":".join(os.environ.get(key, "").lower() for key in
                       ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"))
    if "labwc" in desktop or os.environ.get("LABWC_PID"):
        return "labwc"
    if set(re.split(r"[:\s]+", desktop)) & {"gnome", "ubuntu"}:
        return "gnome"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", choices=("auto", "gnome", "labwc"), default="auto",
                        help="Override desktop detection (default: auto).")
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError("Run as your normal user, without sudo.")
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    launcher = home / ".local/bin/rspb-terminal"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("launch-terminal.sh"), launcher)
    launcher.chmod(0o755)
    desktop = detect_desktop() if args.desktop == "auto" else args.desktop
    if desktop == "gnome":
        setup_gnome(launcher, config_home)
    elif desktop == "labwc":
        setup_labwc(launcher, config_home)
    else:
        print(f"Terminal launcher installed: {launcher}")
        print("Shortcut not registered: no supported desktop session detected. "
              "Run python3 scripts/setup-shortcuts.py from a GNOME or labwc desktop terminal.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"Shortcut setup failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        sys.exit(1)
