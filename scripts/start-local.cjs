// Local static files only. No device, command execution, upload or account API.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const sea = require('node:sea');
const { spawn } = require('node:child_process');
const packaged = sea.isSea();
const root = packaged ? path.dirname(process.execPath) : path.resolve(__dirname, '..');
const publicRoot = path.join(root, 'outputs', 'rx980-local');
const runtime = path.join(root, '.runtime');
const portArg = process.argv.find(arg => arg.startsWith('--port='));
const port = portArg ? Number(portArg.slice(7)) : 19806;
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid local port.');
const url = 'http://127.0.0.1:' + port;
const pidFile = path.join(runtime, port === 19806 ? 'server.pid' : 'server-' + port + '.pid');
const stopping = process.argv.includes('--stop');
fs.mkdirSync(runtime, { recursive: true });
fs.mkdirSync(path.join(runtime, 'temp'), { recursive: true });
process.env.TEMP = path.join(runtime, 'temp');
process.env.TMP = path.join(runtime, 'temp');
if (packaged) {
  // GUI 子系统没有控制台，保留可供排查的本地启动日志。
  const log = (...args) => fs.appendFileSync(path.join(runtime, 'launcher.log'),
    new Date().toISOString() + ' ' + args.map(String).join(' ') + '\n');
  console.log = log;
  console.error = log;
  process.on('uncaughtException', error => { log(error.stack || error); process.exit(1); });
}

function openWindow() {
  if (process.argv.includes('--no-browser')) return;
  const browser = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
  ].find(p => fs.existsSync(p));
  if (!browser) throw new Error('Edge or Chrome is required. Open ' + url + ' manually.');
  // 使用浏览器原有配置打开独立应用窗口，保留 Wetab 等扩展和主页设置。
  spawn(browser, ['--app=' + url], {
    stdio: 'ignore',
    env: process.env,
  }).on('error', e => console.error('Browser:', e.message));
}

const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json',
};
function serve(req, res) {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  if (req.url === '/rx980-status.json') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? '' : JSON.stringify({ application: 'rx980-local', pid: process.pid, root }));
    return;
  }
  try {
    const pathname = decodeURIComponent(new URL(req.url, url).pathname);
    if (packaged) {
      const key = 'web/' + (pathname === '/' ? 'index.html' : pathname.slice(1));
      const content = Buffer.from(sea.getRawAsset(key));
      res.writeHead(200, {
        'Content-Type': mime[path.extname(key)] || 'application/octet-stream',
        'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff',
      });
      res.end(req.method === 'HEAD' ? undefined : content);
      return;
    }
    const file = path.resolve(publicRoot, '.' + (pathname === '/' ? '/index.html' : pathname));
    const realRoot = fs.realpathSync(publicRoot);
    const realFile = fs.realpathSync(file);
    if (!realFile.startsWith(realRoot + path.sep) || !fs.statSync(realFile).isFile()) {
      res.writeHead(404); res.end(); return;
    }
    res.writeHead(200, {
      'Content-Type': mime[path.extname(realFile)] || 'application/octet-stream',
      'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff',
    });
    if (req.method === 'HEAD') res.end();
    else fs.createReadStream(realFile).pipe(res);
  } catch { res.writeHead(404); res.end(); }
}

function start() {
  if (packaged) sea.getRawAsset('web/rx980-build.json');
  else if (!fs.existsSync(path.join(publicRoot, 'rx980-build.json'))) throw new Error('Application build is missing.');
  const server = http.createServer(serve);
  server.on('error', e => { console.error(e.message); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => {
    console.log('RX980 local application: ' + url);
    console.log('Close the application window before closing this server console.');
    fs.writeFileSync(pidFile, String(process.pid));
    openWindow();
  });
}

const check = http.get(url + '/rx980-status.json', { timeout: 1500 }, response => {
  let body = '';
  response.on('data', c => { body += c; });
  response.on('end', () => {
    try {
      const status = JSON.parse(body.replace(/^\uFEFF/, ''));
      if (status.application !== 'rx980-local' || status.root !== root) {
        throw new Error('Port ' + port + ' is used by another folder or application. Stop its server first.');
      }
      if (stopping) {
        const expected = Number(fs.readFileSync(pidFile, 'utf8'));
        if (status.pid !== expected) throw new Error('Server identity did not match this RX980 folder.');
        process.kill(status.pid);
        console.log('RX980 local server stopped.');
      } else openWindow();
    } catch (e) { console.error(e.message); process.exitCode = 1; }
  });
});
check.on('timeout', () => check.destroy(new Error('timeout')));
check.on('error', error => {
  if (!stopping) start();
  else if (error.code === 'ECONNREFUSED') console.log('RX980 local server is not running.');
  else { console.error(error.message); process.exitCode = 1; }
});
