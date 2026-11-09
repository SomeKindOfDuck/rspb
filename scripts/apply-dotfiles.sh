#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    printf 'Usage: bash scripts/apply-dotfiles.sh CHEZMOI_SOURCE_DIRECTORY\n' >&2
    exit 1
fi

rspb_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
rspb_patch="$rspb_root/patches/raspberry-pi.patch"

# Repeated setup must preserve an already-applied patch and unrelated local edits.
if git -C "$1" apply --reverse --check "$rspb_patch" 2>/dev/null; then
    printf 'Raspberry Pi dotfiles adjustments are already applied.\n'
else
    # Check the complete patch before changing any file; conflicts stop setup.
    git -C "$1" apply --check "$rspb_patch"
    git -C "$1" apply "$rspb_patch"
fi
