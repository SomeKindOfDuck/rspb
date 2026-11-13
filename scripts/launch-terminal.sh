#!/bin/sh
set -eu

# Desktop shortcuts do not necessarily inherit the login shell's PATH.
export PATH="$HOME/.local/bin:${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"

for terminal in alacritty xdg-terminal-exec x-terminal-emulator; do
    if command -v "$terminal" >/dev/null 2>&1; then
        exec "$terminal" "$@"
    fi
done

printf 'No terminal found: install Alacritty or configure a default terminal.\n' >&2
exit 1
