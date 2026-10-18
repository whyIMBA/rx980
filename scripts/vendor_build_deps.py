"""Prepare checksum-verified task-local Cargo sources for offline WSL builds."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / '.build/vendor'
VENDOR.mkdir(parents=True, exist_ok=True)


def download(url, target, sha):
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + '.part')
        subprocess.run(['curl.exe', '-sS', '-L', '--fail', '--retry', '3', '--max-time', '90',
                        '--output', str(part), url], check=True)
        if hashlib.sha256(part.read_bytes()).hexdigest() != sha:
            raise RuntimeError(f'Checksum mismatch: {url}')
        part.replace(target)
    return target


packages = {}
for lock in [ROOT / 'sharkfin/app/src-web/Cargo.lock', ROOT / 'sharkfin/tools/core-check/Cargo.lock']:
    for p in tomllib.loads(lock.read_text(encoding='utf-8'))['package']:
        if 'checksum' in p:
            packages[(p['name'], p['version'])] = p


def prepare(p):
    name, version = p['name'], p['version']
    dest = VENDOR / f'{name}-{version}'
    if (dest / '.cargo-checksum.json').exists():
        return
    archive = download(f'https://static.crates.io/crates/{name}/{name}-{version}.crate',
                       ROOT / 'downloads/crates' / f'{name}-{version}.crate', p['checksum'])
    with tarfile.open(archive) as tar:
        tar.extractall(VENDOR, filter='data')
    checksums = {str(f.relative_to(dest)).replace('\\', '/'): hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in dest.rglob('*') if f.is_file() and f.name != '.cargo-checksum.json'}
    (dest / '.cargo-checksum.json').write_text(json.dumps({'files': checksums, 'package': p['checksum']}), encoding='utf-8')
    print('Vendored', name, version, flush=True)


with ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(prepare, packages.values()))

tag = next(p['version'] for p in packages.values() if p['name'] == 'wasm-bindgen')
req = urllib.request.Request(f'https://api.github.com/repos/wasm-bindgen/wasm-bindgen/releases/tags/{tag}',
                             headers={'User-Agent': 'RX980-local-development'})
release = json.load(urllib.request.urlopen(req, timeout=30))
asset = next(a for a in release['assets'] if a['name'].endswith('x86_64-unknown-linux-musl.tar.gz'))
archive = download(asset['browser_download_url'], ROOT / 'downloads' / asset['name'], asset['digest'].split(':')[1])
with tarfile.open(archive) as tar:
    member = next(m for m in tar.getmembers() if m.isfile() and m.name.endswith('/wasm-bindgen'))
    (ROOT / '.toolchain/bin/wasm-bindgen').write_bytes(tar.extractfile(member).read())

linux_path = '/mnt/' + VENDOR.drive[0].lower() + str(VENDOR)[2:].replace('\\', '/')
config = '[source.crates-io]\nreplace-with = "rx980-vendor"\n\n[source.rx980-vendor]\ndirectory = ' + json.dumps(linux_path, ensure_ascii=False) + '\n'
(ROOT / '.toolchain/cargo/config.toml').write_text(config, encoding='utf-8')
print('Offline Cargo source ready;', len(packages), 'packages; wasm-bindgen', tag, flush=True)
