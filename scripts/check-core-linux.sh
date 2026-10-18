#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -x "$TASK_ROOT/.toolchain/cargo/bin/cargo" ]; then
    export CARGO_HOME="$TASK_ROOT/.toolchain/cargo"
    export RUSTUP_HOME="$TASK_ROOT/.toolchain/rustup"
    export PATH="$TASK_ROOT/.toolchain/bin:$CARGO_HOME/bin:$PATH"
fi
export CARGO_TARGET_DIR="$TASK_ROOT/.build/rust"
cd "$TASK_ROOT/sharkfin"
OFFLINE=""
if [ -f "${CARGO_HOME:-$HOME/.cargo}/config.toml" ] && [ -d "$TASK_ROOT/.build/vendor" ]; then
    OFFLINE="--offline"
fi
cargo fmt --manifest-path app/src-tauri/Cargo.toml --all --check
cargo fmt --manifest-path app/src-web/Cargo.toml --all --check
cargo fmt --manifest-path tools/core-check/Cargo.toml --all --check
cargo clippy $OFFLINE --locked --manifest-path tools/core-check/Cargo.toml --all-targets -- -D warnings
cargo clippy $OFFLINE --locked --manifest-path app/src-web/Cargo.toml --target wasm32-unknown-unknown --all-targets -- -D warnings
cargo test $OFFLINE --locked --manifest-path tools/core-check/Cargo.toml
