const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const request = http.get('http://127.0.0.1:19806/rx980-status.json', { timeout: 1500 }, response => {
  let body = '';
  response.on('data', c => { body += c; });
  response.on('end', () => {
    try {
      const status = JSON.parse(body);
      const expected = Number(fs.readFileSync(path.join(root, '.runtime/server.pid'), 'utf8'));
      if (status.application !== 'rx980-local' || status.root !== root || status.pid !== expected) {
        throw new Error('Server identity did not match this RX980 folder.');
      }
      process.kill(status.pid);
      console.log('RX980 local server stopped.');
    } catch (e) { console.error(e.message); process.exitCode = 1; }
  });
});
request.on('timeout', () => request.destroy(new Error('Server did not reply.')));
request.on('error', e => { console.log(e.code === 'ECONNREFUSED' ? 'RX980 local server is not running.' : e.message); });
