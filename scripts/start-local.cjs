// Local static files only. No device, command execution, upload or account API.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const publicRoot = path.join(root, 'outputs', 'rx980-local');
const runtime = path.join(root, '.runtime');
const url = 'http://127.0.0.1:19806';
fs.mkdirSync(runtime, { recursive: true });
fs.mkdirSync(path.join(runtime, 'temp'), { recursive: true });
process.env.TEMP = path.join(runtime, 'temp');
process.env.TMP = path.join(runtime, 'temp');

function openWindow() {
  if (process.argv.includes('--no-browser')) return;
  const browser = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ].find(p => fs.existsSync(p));
  if (!browser) throw new Error('Edge or Chrome is required. Open ' + url + ' manually.');
  spawn(browser, ['--app=' + url, '--no-first-run',
    '--user-data-dir=' + path.join(runtime, 'browser-profile'),
    '--disk-cache-dir=' + path.join(runtime, 'browser-cache')], {
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
  if (!fs.existsSync(path.join(publicRoot, 'rx980-build.json'))) throw new Error('Application build is missing.');
  const server = http.createServer(serve);
  server.on('error', e => { console.error(e.message); process.exitCode = 1; });
  server.listen(19806, '127.0.0.1', () => {
    console.log('RX980 local application: ' + url);
    console.log('Close the application window before closing this server console.');
    fs.writeFileSync(path.join(runtime, 'server.pid'), String(process.pid));
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
        throw new Error('Port 19806 is used by another folder or application. Stop its server first.');
      }
      openWindow();
    } catch (e) { console.error(e.message); process.exitCode = 1; }
  });
});
check.on('timeout', () => check.destroy(new Error('timeout')));
check.on('error', start);
