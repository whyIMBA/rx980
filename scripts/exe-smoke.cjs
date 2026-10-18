// 验证真实单文件 EXE 的可搬移性、静态资源和进程归属，不启动浏览器或 HID。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const root = path.resolve(__dirname, '..');
const original = path.join(root, 'outputs', 'RX980.exe');
const work = fs.mkdtempSync(path.join(root, '.runtime', 'exe-smoke-'));
const directory = path.join(work, '独立 空格目录');
const executable = path.join(directory, 'RX980.exe');
fs.mkdirSync(directory);
fs.copyFileSync(original, executable);
let server;
let port;
const report = { noBrowser: true, hardwareAccess: false, checks: [] };

function launch(args, file = executable) {
  // 清空 PATH，证明运行不依赖系统 Node、CMD 或外部启动脚本。
  const child = spawn(file, args, { cwd: work, env: { ...process.env, PATH: '' },
    windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  const done = once(child, 'close').then(([code]) => ({ code, output }));
  return { child, done };
}
async function freePort() {
  const socket = net.createServer();
  socket.listen(0, '127.0.0.1');
  await once(socket, 'listening');
  const number = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  return number;
}
async function run() {
  const binary = fs.readFileSync(original);
  const header = binary.readUInt32LE(0x3c) + 24;
  assert.equal(binary.readUInt16LE(header + 68), 2, 'EXE must use the GUI subsystem');
  report.checks.push('Windows GUI subsystem');
  port = await freePort();
  const base = 'http://127.0.0.1:' + port;
  const started = launch(['--no-browser', '--port=' + port]);
  server = started;
  let status;
  for (let attempt = 0; attempt < 80; attempt++) {
    status = await fetch(base + '/rx980-status.json').then(response => response.json()).catch(() => null);
    if (status) break;
    if (started.child.exitCode !== null) throw new Error('EXE exited: ' + JSON.stringify(await started.done));
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(status, 'EXE server did not start');
  assert.equal(status.application, 'rx980-local');
  assert.equal(status.root, directory, 'Root must resolve from EXE location, not working directory');
  assert.equal(status.pid, started.child.pid);
  report.checks.push('Standalone start with empty PATH and Unicode/space path');
  const web = path.join(root, 'outputs', 'rx980-local');
  const files = [];
  function collect(folder) {
    for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, item.name);
      if (item.isDirectory()) collect(file);
      else files.push(file);
    }
  }
  collect(web);
  for (let offset = 0; offset < files.length; offset += 16) {
    await Promise.all(files.slice(offset, offset + 16).map(async file => {
      const relative = path.relative(web, file).split(path.sep).join('/');
      const response = await fetch(base + '/' + relative.split('/').map(encodeURIComponent).join('/'));
      assert.equal(response.status, 200, relative);
      assert.deepEqual(Buffer.from(await response.arrayBuffer()), fs.readFileSync(file), relative);
    }));
  }
  assert.deepEqual(Buffer.from(await (await fetch(base)).arrayBuffer()), fs.readFileSync(path.join(web, 'index.html')));
  const head = await fetch(base, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.match(head.headers.get('content-type'), /text\/html/);
  assert.equal((await head.arrayBuffer()).byteLength, 0);
  for (const method of ['POST', 'PUT', 'DELETE']) assert.equal((await fetch(base, { method })).status, 405);
  for (const suffix of ['/missing.txt', '/..%5cREADME.md', '/legal/LICENSE', '/%ZZ']) {
    assert.equal((await fetch(base + suffix)).status, 404, suffix);
  }
  report.assetsVerified = files.length;
  report.checks.push('All embedded assets match web build; HEAD, missing paths and write rejection');
  assert.equal((await launch(['--no-browser', '--port=' + port]).done).code, 0);
  assert.equal((await (await fetch(base + '/rx980-status.json')).json()).pid, status.pid);
  report.checks.push('Repeated launch reuses server');
  const otherDirectory = path.join(work, '其他目录');
  fs.mkdirSync(otherDirectory);
  const other = path.join(otherDirectory, 'RX980.exe');
  fs.copyFileSync(original, other);
  assert.equal((await launch(['--stop', '--port=' + port], other).done).code, 1);
  assert.equal((await (await fetch(base + '/rx980-status.json')).json()).pid, status.pid);
  report.checks.push('Other folder cannot stop this server');
  assert.equal((await launch(['--stop', '--port=' + port]).done).code, 0);
  await Promise.race([started.done, new Promise((_, reject) => setTimeout(() => reject(new Error('Server did not stop')), 4000))]);
  server = null;
  assert.equal((await launch(['--stop', '--port=' + port]).done).code, 0);
  report.checks.push('Stop and repeated stop without Node');
  report.passed = true;
}
run().catch(error => { report.passed = false; report.error = error.stack; process.exitCode = 1; })
  .finally(async () => {
    if (server && server.child.exitCode === null) { server.child.kill(); await server.done; }
    fs.mkdirSync(path.join(root, 'reports'), { recursive: true });
    fs.writeFileSync(path.join(root, 'reports', 'exe-smoke.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    // 仅移除本次由 mkdtemp 创建、已退出进程的测试目录。
    if (path.dirname(work) !== path.join(root, '.runtime') || !path.basename(work).startsWith('exe-smoke-')) {
      throw new Error('Unexpected test cleanup path');
    }
    fs.rmSync(work, { recursive: true, force: true });
  });
