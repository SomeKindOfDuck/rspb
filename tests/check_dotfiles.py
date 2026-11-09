"""Offline integration checks against a local checkout of the audited dotfiles.

Usage: python3.11+ tests/check_dotfiles.py /path/to/dotfiles
Set CHEZMOI_BIN / NVIM_BIN when the normal launcher is unavailable.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(sys.argv[1]).resolve()
REVISION = "1dac187d2fc504111fcd5f33f9b6559662f30599"
CHEZMOI = os.environ.get("CHEZMOI_BIN", "chezmoi")
NVIM = os.environ.get("NVIM_BIN", "nvim")


def run(*args, env=None, check=True):
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    if check and result.returncode:
        print(result.stdout, result.stderr, file=sys.stderr)
        result.check_returncode()
    return result


def contents(directory):
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(directory).parts
    }


with tempfile.TemporaryDirectory(prefix="rspb-dotfiles-test-") as temporary:
    work = Path(temporary)
    home = work / "pi home"
    source = work / "source"
    home.mkdir()
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "SHELL": "/bin/bash",
        "LANG": "C.UTF-8",
        "TERM": "xterm-256color",
        "NVIM_LOG_FILE": str(work / "nvim.log"),
    }
    chezmoi = [
        CHEZMOI, "--no-tty", "--source", str(source), "--destination", str(home),
        "--config", str(work / "chezmoi.toml"), "--cache", str(work / "cache"),
        "--persistent-state", str(work / "state.boltdb"),
    ]
    init = ["init", "--guess-repo-url=false", "--revision", REVISION, str(REFERENCE)]
    # Clone explicitly: some sandboxes expose an empty /tmp/.git sentinel,
    # which chezmoi mistakes for an existing parent source repository.
    run("git", "clone", "--quiet", "--no-hardlinks", str(REFERENCE), str(source), env=env)
    run("git", "-C", str(source), "checkout", "--quiet", REVISION, env=env)
    run(*chezmoi, *init, env=env)
    run("bash", str(ROOT / "scripts/apply-dotfiles.sh"), str(source), env=env)
    first = contents(source)
    # Repeat the same sequence used by init.sh, including chezmoi init on a dirty source.
    run(*chezmoi, *init, env=env)
    run("bash", str(ROOT / "scripts/apply-dotfiles.sh"), str(source), env=env)
    assert contents(source) == first, "Repeated setup changed the source"
    run(*chezmoi, "apply", env=env)
    run(*chezmoi, "verify", env=env)
    print("PASS patch application, repeated init/apply, chezmoi verify")

    config = home / ".config"
    assert not (config / "alacritty/alacritty.yml").exists()
    assert not (home / ".condarc").exists()
    alacritty = tomllib.loads((config / "alacritty/alacritty.toml").read_text())
    assert alacritty["font"]["normal"]["family"] == "Hack Nerd Font"
    assert alacritty["colors"]["primary"]["background"] == "0x222436"
    assert alacritty["keyboard"]["bindings"][0]["chars"] == "\x1b\r"
    tomllib.loads((config / "bottom/bottom.toml").read_text())
    for path in [home / ".bashrc", home / ".profile", config / "fish/config.fish"]:
        assert "/home/duck/" not in path.read_text(), path
    run("bash", "-n", str(home / ".bashrc"), str(home / ".profile"))
    run("dash", "-n", str(config / "rspb/env.sh"))
    run("bash", "-c", '. "$HOME/.profile"', env=env)
    run("dash", "-c", '. "$HOME/.profile"', env=env)
    print("PASS Alacritty theme/key binding merge and portable Bash/POSIX profiles")

    for path in (config / "fish").rglob("*.fish"):
        run("fish", "--no-execute", str(path))
    assert not run("fish", "-c", "true", env=env).stderr
    projects = [home / "project one", home / "project two", home / "manual env"]
    for project in projects:
        run(sys.executable, "-m", "venv", "--without-pip", str(project / ".venv"))
        (project / "nested").mkdir()
    fish_check = '''
cd "$argv[1]/nested"
test "$VIRTUAL_ENV" = "$argv[1]/.venv"; or exit 10
cd "$argv[2]"
test "$VIRTUAL_ENV" = "$argv[2]/.venv"; or exit 11
cd "$HOME"
not set -q VIRTUAL_ENV; or exit 12
source "$argv[3]/.venv/bin/activate.fish"
cd "$argv[1]"
test "$VIRTUAL_ENV" = "$argv[3]/.venv"; or exit 13
'''
    result = run("fish", "-c", fish_check, *(str(p) for p in projects), env=env)
    assert not result.stderr, result.stderr
    print("PASS fish startup, nested/spaced project paths, environment switching and manual activation")

    lua_check = work / "check.lua"
    lua_check.write_text('''
local config = vim.env.HOME .. "/.config/nvim/"
for _, path in ipairs(vim.fn.glob(config .. "**/*.lua", false, true)) do
  assert(loadfile(path), path)
end
dofile(config .. "lua/config/rspb.lua")
assert(#vim.g.coc_global_extensions == 7)
for _, name in ipairs(vim.g.coc_global_extensions) do
  assert(name ~= "coc-r-lsp" and name ~= "coc-julia")
end
local options
package.preload["iron.core"] = function() return { setup = function(value) options = value end } end
package.preload["iron.fts.common"] = function() return { bracketed_paste = function() end } end
package.preload["iron.view"] = function() return { split = { horizontal = function() return "split" end } } end
dofile(config .. "lua/plugins/iron.lua").config()
local repl = options.config.repl_definition
assert(repl.python.command[1] == "uv" and repl.python.command[2] == "run")
assert(repl.r == nil and repl.julia == nil)
assert(dofile(config .. "lua/plugins/claudecode.lua").enabled == false)
package.preload["nvim-treesitter.configs"] = function() return { setup = function(value) options = value end } end
dofile(config .. "lua/plugins/treesitter.lua").config()
for _, name in ipairs(options.ensure_installed) do assert(name ~= "r" and name ~= "julia") end
print("Neovim configuration verified")
''')
    result = run(NVIM, "--headless", "-u", "NONE", "-i", "NONE", "-l", str(lua_check), env=env)
    assert "Neovim configuration verified" in result.stdout + result.stderr
    print("PASS Lua syntax, uv REPL, CoC extensions, R/Julia/AI exclusions")

    # A conflicting source must fail without partially applying the rest of the patch.
    conflict = work / "conflict"
    run("git", "clone", "--quiet", "--no-hardlinks", str(REFERENCE), str(conflict), env=env)
    run("git", "-C", str(conflict), "checkout", "--quiet", REVISION, env=env)
    fish_source = conflict / "private_dot_config/private_fish/config.fish"
    fish_source.write_text("# User-owned replacement that must be preserved\n")
    before = contents(conflict)
    result = run("bash", str(ROOT / "scripts/apply-dotfiles.sh"), str(conflict), env=env, check=False)
    assert result.returncode != 0
    assert contents(conflict) == before, "Conflict caused a partial edit"
    print("PASS conflicting dotfiles stop without partial edits")
