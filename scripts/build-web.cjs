const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const app = path.join(root, 'sharkfin/app');
const temporary = path.join(root, '.runtime/build-temp');
fs.mkdirSync(temporary, { recursive: true });
process.env.TEMP = temporary;
process.env.TMP = temporary;
fs.mkdirSync(path.join(root, 'logs'), { recursive: true });

function run(script, args, stdio = 'inherit') {
  const result = spawnSync(process.execPath, [script, ...args], { cwd: app, stdio, env: process.env });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${path.basename(script)} failed; see logs/web-build.log`);
}
run(path.join(app, 'node_modules/typescript/bin/tsc'), ['-p', 'tsconfig.web.json', '--noEmit']);
const log = fs.openSync(path.join(root, 'logs/web-build.log'), 'w');
try { run(path.join(app, 'node_modules/vite/bin/vite.js'), ['build', '--config', 'vite.web.config.ts'], ['ignore', log, log]); }
finally { fs.closeSync(log); }
const built = path.join(app, 'dist-web');
fs.renameSync(path.join(built, 'web.html'), path.join(built, 'index.html'));
fs.writeFileSync(path.join(built, 'rx980-build.json'), JSON.stringify({
  application: 'rx980-local', version, upstream: 'sharkfin-v0.10.0-b36c790',
  deviceId: 671, firmwareTested: '5.05',
}, null, 2));
run(path.join(app, 'scripts/gen-sw.mjs'), []);
const output = path.resolve(root, 'outputs/rx980-local');
if (!output.startsWith(root + path.sep) || path.basename(output) !== 'rx980-local') {
  throw new Error('Unexpected build output path');
}
if (fs.existsSync(output)) {
  if (fs.lstatSync(output).isSymbolicLink()) throw new Error('Build output must not be a link');
  fs.rmSync(output, { recursive: true });
}
fs.cpSync(built, output, { recursive: true });
console.log('Built ' + output);
