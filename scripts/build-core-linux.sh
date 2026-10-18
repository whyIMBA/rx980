#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -x "$TASK_ROOT/.toolchain/cargo/bin/cargo" ]; then
    export CARGO_HOME="$TASK_ROOT/.toolchain/cargo"
    export RUSTUP_HOME="$TASK_ROOT/.toolchain/rustup"
    export PATH="$TASK_ROOT/.toolchain/bin:$CARGO_HOME/bin:$PATH"
fi
export CARGO_TARGET_DIR="$TASK_ROOT/.build/rust"
export CARGO_HTTP_TIMEOUT=90
if [ -f "$TASK_ROOT/.toolchain/bin/wasm-bindgen" ]; then
    chmod +x "$TASK_ROOT/.toolchain/bin/wasm-bindgen"
fi
# Use the verified vendor cache when present, or normal Cargo downloads.
OFFLINE=""
if [ -f "${CARGO_HOME:-$HOME/.cargo}/config.toml" ] && [ -d "$TASK_ROOT/.build/vendor" ]; then
    OFFLINE="--offline"
fi
cd "$TASK_ROOT/sharkfin"
if [ "${1:-}" != "--build-only" ]; then
    cargo test $OFFLINE --locked --manifest-path tools/core-check/Cargo.toml
fi
cargo build $OFFLINE --locked --manifest-path app/src-web/Cargo.toml --target wasm32-unknown-unknown --release
wasm-bindgen --target web --out-dir app/src-web/pkg "$CARGO_TARGET_DIR/wasm32-unknown-unknown/release/sharkfin_web.wasm"
