#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export CARGO_HOME="$TASK_ROOT/.toolchain/cargo"
export RUSTUP_HOME="$TASK_ROOT/.toolchain/rustup"
export PATH="$CARGO_HOME/bin:$PATH"
chmod +x "$TASK_ROOT/downloads/rustup-init-linux"
"$TASK_ROOT/downloads/rustup-init-linux" -y --no-modify-path --profile minimal --default-toolchain stable --target wasm32-unknown-unknown
# wasm-pack is supplied as a verified upstream prebuilt binary in .toolchain/bin.
