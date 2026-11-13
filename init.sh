#!/usr/bin/env bash
set -euo pipefail

# Run as your normal user with: bash init.sh
# See README.md for prerequisites and version overrides.
rspb_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
rspb_init_nvim="${RSPB_INIT_NVIM:-1}"
rspb_init_flkl="${RSPB_INIT_FLKL:-1}"
if [[ ! "$rspb_init_nvim" =~ ^[01]$ || ! "$rspb_init_flkl" =~ ^[01]$ ]]; then
    printf 'RSPB_INIT_NVIM and RSPB_INIT_FLKL must be 0 or 1.\n' >&2
    exit 1
fi
if [[ $(id -u) -eq 0 ]]; then
    printf 'Run this script as your normal user, without sudo.\n' >&2
    exit 1
fi

if ! command -v apt-get >/dev/null || ! command -v dpkg >/dev/null; then
    printf 'This script requires a Debian/Ubuntu-based distribution.\n' >&2
    exit 1
fi

# Use the userspace architecture, including on a Pi with a 64-bit kernel.
case "$(dpkg --print-architecture)" in
    amd64) rspb_nvim_arch=x86_64 ;;
    arm64)
        rspb_nvim_arch=arm64
        export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
        ;;
    *)
        printf 'A 64-bit OS (arm64 or amd64) is required for this setup.\n' >&2
        exit 1
        ;;
esac

rspb_bin_dir="$HOME/.local/bin"
rspb_cargo_dir="${CARGO_HOME:-$HOME/.cargo}"
export PATH="$rspb_bin_dir:$rspb_cargo_dir/bin:$PATH"
mkdir -p "$rspb_bin_dir"
rspb_tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "$rspb_tmp_dir"' EXIT

download() {
    curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$1" -o "$2"
}

sudo apt-get update
sudo apt-get install -y \
    ca-certificates curl git unzip xz-utils fish fzf fontconfig bash-completion \
    direnv tmux ncurses-term xclip wl-clipboard clangd \
    build-essential cmake pkg-config python3 portaudio19-dev libssl-dev \
    libfontconfig1-dev libxcb-xfixes0-dev libxkbcommon-dev libwayland-dev \
    libegl1 libgl1

# Official stable Neovim binaries support both Raspberry Pi arm64 and amd64.
download "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-$rspb_nvim_arch.tar.gz" \
    "$rspb_tmp_dir/nvim.tar.gz"
tar -xzf "$rspb_tmp_dir/nvim.tar.gz" -C "$rspb_tmp_dir"
"$rspb_tmp_dir/nvim-linux-$rspb_nvim_arch/bin/nvim" --version
mkdir -p "$HOME/.local/opt"
rm -rf -- "$HOME/.local/opt/nvim"
mv "$rspb_tmp_dir/nvim-linux-$rspb_nvim_arch" "$HOME/.local/opt/nvim"
ln -sfn "$HOME/.local/opt/nvim/bin/nvim" "$rspb_bin_dir/nvim"

download https://get.chezmoi.io "$rspb_tmp_dir/chezmoi.sh"
sh "$rspb_tmp_dir/chezmoi.sh" -b "$rspb_bin_dir"

# uv manages both Python and project environments (.venv by default).
# Request Python 3 explicitly so a local .python-version does not pin setup.
download https://astral.sh/uv/install.sh "$rspb_tmp_dir/uv.sh"
UV_INSTALL_DIR="$rspb_bin_dir" UV_NO_MODIFY_PATH=1 sh "$rspb_tmp_dir/uv.sh"
uv python install --default "${RSPB_PYTHON_VERSION:-3}"
for rspb_tool in ipython pynvim isort; do
    uv tool install --upgrade "$rspb_tool"
done

# Build current releases with their published lockfiles and stable Rust.
if [[ -x "$rspb_cargo_dir/bin/rustup" ]]; then
    rustup update stable
else
    download https://sh.rustup.rs "$rspb_tmp_dir/rustup.sh"
    sh "$rspb_tmp_dir/rustup.sh" -y --profile minimal --default-toolchain stable --no-modify-path
fi
cargo +stable install --locked --root "$rspb_cargo_dir" eza fd-find ripgrep starship alacritty bottom

# Preserve the desktop's Hack Nerd Font choice on a fresh Pi.
download https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip \
    "$rspb_tmp_dir/Hack.zip"
rspb_font_dir="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/HackNerdFont"
mkdir -p "$rspb_font_dir"
unzip -oq "$rspb_tmp_dir/Hack.zip" '*.ttf' -d "$rspb_font_dir"
fc-cache -f "$rspb_font_dir"

# fnm installs Node.js in the user account, without a temporary apt/npm install.
download https://fnm.vercel.app/install "$rspb_tmp_dir/fnm.sh"
bash "$rspb_tmp_dir/fnm.sh" --install-dir "$rspb_bin_dir" --skip-shell
rspb_fnm_env="$(fnm env --shell bash)"
eval "$rspb_fnm_env"
fnm install --lts --use
rspb_node_version="$(fnm current)"
fnm default "$rspb_node_version"

# Corepack is no longer bundled with recent Node.js releases.
npm install --global corepack@latest
corepack enable yarn
corepack install --global yarn@stable

# Arduino dependencies for flkl/pyno. Refresh both indexes before installing.
download https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
    "$rspb_tmp_dir/arduino-cli.sh"
BINDIR="$rspb_bin_dir" sh "$rspb_tmp_dir/arduino-cli.sh"
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib update-index
arduino-cli lib install Servo
sudo usermod -a -G dialout "$(id -un)"

if [[ "$rspb_init_flkl" == 1 ]]; then
    bash "$rspb_root/scripts/setup-flkl.sh"
fi

# This final stage can also be rerun independently after an interrupted setup.
bash "$rspb_root/scripts/setup-dotfiles.sh"
