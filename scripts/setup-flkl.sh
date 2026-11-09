#!/usr/bin/env bash
set -euo pipefail

# Run after init.sh has installed uv and Arduino CLI / arduino:avr.
rspb_flkl_dir="${RSPB_FLKL_DIR:-$HOME/Programs/Github/flkl}"
rspb_flkl_branch=pj-yoneyama

if [[ ! -e "$rspb_flkl_dir" ]]; then
    mkdir -p "$(dirname -- "$rspb_flkl_dir")"
    git clone --branch "$rspb_flkl_branch" --single-branch \
        https://github.com/SomeKindOfDuck/flkl.git "$rspb_flkl_dir"
fi

# Reuse an existing checkout without pulling, switching branches or discarding edits.
if [[ ! -e "$rspb_flkl_dir/.git" ]] || \
    [[ "$(git -C "$rspb_flkl_dir" branch --show-current)" != "$rspb_flkl_branch" ]]; then
    printf 'Expected a flkl checkout on branch %s at %s. Set RSPB_FLKL_DIR to the intended checkout.\n' \
        "$rspb_flkl_branch" "$rspb_flkl_dir" >&2
    exit 1
fi
cd -- "$rspb_flkl_dir"
for rspb_required in pyproject.toml uv.lock .python-version ino/ino.ino ino/equal_on.h; do
    if [[ ! -f "$rspb_required" ]]; then
        printf 'Missing flkl project file: %s\n' "$rspb_required" >&2
        exit 1
    fi
done

# pj-yoneyama currently requires Python 3.10 via .python-version.
# Its locked NumPy 1.26 environment must not inherit the newest global Python.
rspb_flkl_python="$(<.python-version)"
uv python install "$rspb_flkl_python"
uv sync --locked --no-dev --python "$rspb_flkl_python"

# These checks import the runtime and parse CLI arguments without opening a device.
uv run --locked --no-dev python -c \
    'import numpy, scipy, pandas, pyarrow, matplotlib, yaml, serial, sounddevice; import amas.agent, utex.agent, pyno.ino'
for rspb_command in train test blink; do
    uv run --locked --no-dev python -m "flkl.bhv.$rspb_command" --help
done

# Compile only. The AVR register-based sketch targets an Uno R3 / ATmega328P.
# Uploading and running an experiment remain explicit actions in flkl.
arduino-cli compile --fqbn "${RSPB_ARDUINO_FQBN:-arduino:avr:uno}" --jobs 1 ./ino

for rspb_config in train test; do
    if [[ ! -e "config/$rspb_config.yaml" ]]; then
        cp "config/$rspb_config-sample.yaml" "config/$rspb_config.yaml"
    fi
done
printf 'flkl/%s is ready at %s. Review config/train.yaml and config/test.yaml before use.\n' \
    "$rspb_flkl_branch" "$rspb_flkl_dir"
