// SPDX-License-Identifier: GPL-3.0-or-later
//! Run the shared upstream protocol tests without desktop GUI dependencies.
#[path = "../../app/src-tauri/src/derive.rs"]
pub mod derive;
#[path = "../../app/src-tauri/src/ops.rs"]
pub mod ops;
#[path = "../../app/src-tauri/src/protocol/mod.rs"]
pub mod protocol;
#[path = "../../app/src-tauri/src/registry.rs"]
pub mod registry;
#[path = "../../app/src-tauri/src/session.rs"]
pub mod session;
#[path = "../../app/src-tauri/src/wire.rs"]
pub mod wire;

#[cfg(test)]
mod rx980_tests;
