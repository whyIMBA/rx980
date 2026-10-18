# 开发与验证

## 环境

- Node.js 22 或以上，Python 3.12 或以上。
- Linux 或 Windows + WSL Ubuntu。Rust stable，目标 `wasm32-unknown-unknown`，组件 `rustfmt`、`clippy`。
- `wasm-bindgen-cli` 版本必须与 `sharkfin/app/src-web/Cargo.lock` 中 `wasm-bindgen` 版本一致，当前为 0.2.126。
- 启动和回放使用本机 Edge 或 Chrome。自动回放还需在根目录执行 `npm ci` 安装测试依赖。

## 从源码构建

在仓库根目录执行，Linux 下不需要 `wsl.exe` 前缀：

```powershell
npm --prefix sharkfin/app ci
wsl.exe -d Ubuntu --exec sh -c 'rustup target add wasm32-unknown-unknown && rustup component add rustfmt clippy && cargo install wasm-bindgen-cli --version 0.2.126 --locked'
wsl.exe -d Ubuntu --exec sh -c 'cd "/mnt/d/codes/RX980键盘驱动" && sh scripts/build-core-linux.sh'
node scripts/build-web.cjs
```

最后一条命令生成 `outputs/rx980-local/`。其他克隆目录需替换示例中的 WSL 路径。已有项目隔离工具链时脚本优先使用 `.toolchain/`，否则使用系统环境。

`.toolchain/cargo/config.toml` 如指向离线依赖目录，迁移后必须同步更新。重新准备离线依赖可运行 `python scripts/vendor_build_deps.py`；此脚本需要网络和 `curl.exe`。

```powershell
node scripts/start-local.cjs
node scripts/stop-local.cjs
```

## 检查

```powershell
node sharkfin/app/node_modules/typescript/bin/tsc --noEmit -p sharkfin/app/tsconfig.json
node sharkfin/app/node_modules/typescript/bin/tsc --noEmit -p sharkfin/app/tsconfig.web.json
node sharkfin/app/node_modules/vitest/vitest.mjs run --root sharkfin/app
python sharkfin/tools/coverage.py --markdown
python sharkfin/tools/lint_layouts.py
wsl.exe -d Ubuntu --exec sh -c 'cd "/mnt/d/codes/RX980键盘驱动" && sh scripts/check-core-linux.sh'
```

上游 Python 工具从脚本位置解析源码路径。Rust 核心检查直接引用共享协议源码，不需要桌面 GUI 依赖。Windows 原生 Tauri 构建和三平台桌面检查另见 `sharkfin/CONTRIBUTING.md`，不以核心检查代替。更新应用依赖后，还需在完整桌面构建环境生成 source map 并运行 `python -X utf8 sharkfin/tools/notices.py --check`，此检查需要可调用的 Cargo 及桌面端依赖。本次迁移未更改应用依赖，原第三方声明按原样保留。

只读界面回放需先有本地完整诊断备份 `backups/rx980-日期.json`，并启动本地服务：

```powershell
npm ci
node scripts/ui-smoke.cjs --replay
```

回放拒绝写入，但不代表实机验证。`scripts/roundtrip_*.py` 会写键盘，不能作为普通自动检查运行。硬件诊断依赖可单独安装 `hidapi==0.15.0`。

## 打包

```powershell
python scripts/package_local.py
```

打包前先完成构建和检查。`outputs/` 下生成 0.1.0 本地应用包和完整仓库源码包。源码包按 Git 跟踪列表及未忽略文件生成，不包含个人备份、浏览器数据、依赖目录及缓存。源码包可解压后按本页步骤重新构建。
