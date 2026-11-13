#!/usr/bin/env bash
set -euo pipefail

# Resume the final stage after init.sh has installed the tools and prepared flkl.
rspb_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
rspb_init_nvim="${RSPB_INIT_NVIM:-1}"
if [[ ! "$rspb_init_nvim" =~ ^[01]$ ]]; then
    printf 'RSPB_INIT_NVIM must be 0 or 1.\n' >&2
    exit 1
fi

export PATH="$HOME/.local/bin:${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
if command -v fnm >/dev/null 2>&1; then
    rspb_fnm_env="$(fnm env --shell bash)"
    eval "$rspb_fnm_env"
fi

rspb_revision=1dac187d2fc504111fcd5f33f9b6559662f30599
rspb_dotfiles_source="$(chezmoi source-path)"
if [[ ! -e "$rspb_dotfiles_source/.git" ]]; then
    # chezmoi init --revision uses git clone --revision, requiring Git 2.49+.
    # Clone normally so Ubuntu / Raspberry Pi OS can use their packaged Git.
    git clone -- "${RSPB_DOTFILES_REPO:-https://github.com/SomeKindOfDuck/dotfiles}" \
        "$rspb_dotfiles_source"
fi

if [[ "$(git -C "$rspb_dotfiles_source" rev-parse HEAD)" != "$rspb_revision" ]]; then
    if [[ -n "$(git -C "$rspb_dotfiles_source" status --porcelain)" ]]; then
        printf 'Dotfiles have local changes at a different revision; refusing to switch or overwrite them: %s\n' \
            "$rspb_dotfiles_source" >&2
        exit 1
    fi
    if ! git -C "$rspb_dotfiles_source" cat-file -e "$rspb_revision^{commit}" 2>/dev/null; then
        git -C "$rspb_dotfiles_source" fetch origin "$rspb_revision"
    fi
    git -C "$rspb_dotfiles_source" checkout --detach "$rspb_revision"
fi

bash "$rspb_root/scripts/apply-dotfiles.sh" "$rspb_dotfiles_source"
# Pin before evaluating chezmoi templates, and do not search for a parent Git repo.
chezmoi --source "$rspb_dotfiles_source" --working-tree "$rspb_dotfiles_source" init
chezmoi --source "$rspb_dotfiles_source" apply

mkdir -p "$HOME/.config/fish/completions"
uv generate-shell-completion fish > "$HOME/.config/fish/completions/uv.fish"

if [[ "$rspb_init_nvim" == 1 ]]; then
    RSPB_NVIM_SETUP=1 RSPB_NVIM_SETUP_SCRIPT="$rspb_root/scripts/setup-nvim.lua" \
        nvim --headless -i NONE -c 'lua dofile(vim.env.RSPB_NVIM_SETUP_SCRIPT)'
fi

if [[ -t 0 ]]; then
    chsh -s "$(command -v fish)"
else
    printf 'To make fish your login shell, run: chsh -s %s\n' "$(command -v fish)"
fi
printf 'Setup complete. Log out and back in to activate fish and dialout membership.\n'
