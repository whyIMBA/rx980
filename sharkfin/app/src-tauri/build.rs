// SPDX-FileCopyrightText: JR Lanteigne <root@dnim.dev>
// SPDX-License-Identifier: GPL-3.0-or-later

// Keep in step with src-web/build.rs. Both crates report the same build id in
// data bundles, and src-web compiles registry.rs by path instead of linking
// this crate, so it needs its own copy.
fn main() {
    if let Some(commit) = git_commit() {
        println!("cargo:rustc-env=SHARKFIN_COMMIT={commit}");
    }
    // Without this the recorded commit is whatever HEAD was when the build
    // script last ran. Absent from a tarball build, where there is nothing
    // to watch.
    for path in ["../../.git/HEAD", "../../.git/index"] {
        if std::path::Path::new(path).exists() {
            println!("cargo:rerun-if-changed={path}");
        }
    }
    tauri_build::build()
}

/// `None` when git is unavailable or this is not a checkout, which is the
/// normal case for a release tarball. A modified tree is marked, so a bundle
/// from a local build is never mistaken for the released commit.
fn git_commit() -> Option<String> {
    // Only this repo's own .git counts. A tarball unpacked inside an unrelated
    // checkout would otherwise report that repo's commit, which is worse in a
    // bug report than reporting none.
    if !std::path::Path::new("../../.git").exists() {
        return None;
    }
    let run = |args: &[&str]| {
        std::process::Command::new("git")
            .args(args)
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
    };
    let short = run(&["rev-parse", "--short", "HEAD"]).filter(|s| !s.is_empty())?;
    let dirty = run(&["status", "--porcelain"]).is_some_and(|s| !s.is_empty());
    Some(if dirty {
        format!("{short}-dirty")
    } else {
        short
    })
}
