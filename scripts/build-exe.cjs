// Windows 单文件版本：Node SEA 内嵌同一个启动脚本及已构建网页。
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { inject } = require('postject');
const root = path.resolve(__dirname, '..');
const work = path.join(root, '.build', 'exe');
const web = path.join(root, 'outputs', 'rx980-local');
const output = path.join(root, 'outputs', 'RX980.exe');
const fuse = 'NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2';

function peHeader(data) {
  if (data.toString('ascii', 0, 2) !== 'MZ') throw new Error('Expected Windows executable.');
  const header = data.readUInt32LE(0x3c);
  if (data.toString('ascii', header, header + 4) !== 'PE\0\0') throw new Error('Invalid PE header.');
  const optional = header + 24;
  if (data.readUInt16LE(optional) !== 0x20b) throw new Error('Expected 64-bit PE executable.');
  return optional;
}

async function build() {
  if (process.platform !== 'win32' || process.arch !== 'x64') throw new Error('Build this EXE with Windows x64 Node.js.');
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node.js 22 or later is required.');
  if (!fs.existsSync(path.join(web, 'rx980-build.json'))) throw new Error('Run npm run build:web first.');
  fs.mkdirSync(work, { recursive: true });
  const temporary = path.join(root, '.runtime', 'exe-build-temp');
  fs.mkdirSync(temporary, { recursive: true });
  const license = path.join(work, 'NODE-LICENSE-' + process.version + '.txt');
  if (!fs.existsSync(license)) {
    const response = await fetch('https://raw.githubusercontent.com/nodejs/node/' + process.version + '/LICENSE');
    if (!response.ok) throw new Error('Could not retrieve the matching Node.js license: ' + response.status);
    const text = await response.text();
    if (!text.includes('Node.js is licensed') || !text.includes('Permission is hereby granted')) throw new Error('Invalid Node.js license.');
    fs.writeFileSync(license, text);
  }
  const assets = { 'legal/NODE-LICENSE.txt': license, 'legal/LICENSE': path.join(root, 'LICENSE'),
    'legal/THIRD-PARTY-NOTICES.md': path.join(root, 'THIRD-PARTY-NOTICES.md') };
  function collect(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) collect(file);
      else if (entry.isFile()) assets['web/' + path.relative(web, file).split(path.sep).join('/')] = file;
      else throw new Error('Do not package links or special files: ' + file);
    }
  }
  collect(web);
  const blob = path.join(work, 'rx980.blob');
  const config = path.join(work, 'sea-config.json');
  fs.writeFileSync(config, JSON.stringify({ main: path.join(root, 'scripts', 'start-local.cjs'), output: blob,
    disableExperimentalSEAWarning: true, useSnapshot: false, useCodeCache: false,
    execArgvExtension: 'none', assets }, null, 2));
  const prepared = spawnSync(process.execPath, ['--experimental-sea-config', config], {
    cwd: root, env: { ...process.env, TEMP: temporary, TMP: temporary }, stdio: 'inherit', windowsHide: true,
  });
  if (prepared.error) throw prepared.error;
  if (prepared.status !== 0) throw new Error('SEA preparation failed.');
  let binary = fs.readFileSync(process.execPath);
  const optional = peHeader(binary);
  // 改写后的程序不沿用 Node 原签名；仅移除副本末尾的证书表。
  const certificate = binary.readUInt32LE(optional + 144);
  const certificateSize = binary.readUInt32LE(optional + 148);
  binary.writeBigUInt64LE(0n, optional + 144);
  if (certificate && certificate + certificateSize === binary.length) binary = binary.subarray(0, certificate);
  fs.writeFileSync(output, binary);
  await inject(output, 'NODE_SEA_BLOB', fs.readFileSync(blob), { sentinelFuse: fuse });
  binary = fs.readFileSync(output);
  const injectedOptional = peHeader(binary);
  // GUI 子系统避免双击时弹出 CMD。应用日志写入 EXE 同目录的 .runtime。
  binary.writeUInt16LE(2, injectedOptional + 68);
  binary.writeUInt32LE(0, injectedOptional + 64);
  fs.writeFileSync(output, binary);
  fs.copyFileSync(license, path.join(root, 'outputs', 'NODE-LICENSE.txt'));
  fs.copyFileSync(output, path.join(root, 'RX980.exe'));
  console.log(JSON.stringify({ executable: output, bytes: binary.length, node: process.version,
    webAssets: Object.keys(assets).length - 3 }));
}
build().catch(error => { console.error(error); process.exitCode = 1; });
