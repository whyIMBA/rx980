"""Fetch official Rust components via Windows into the task-local rustup cache."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import urllib.request
import sys

ROOT = Path(__file__).resolve().parents[1]


def download(url, path, sha):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha:
        return path
    temp = path.with_name(path.name + '.windows-download')
    subprocess.run(['curl.exe', '-sS', '-L', '--fail', '--retry', '3', '--retry-all-errors', '--max-time', '180',
                    '--output', str(temp), url], check=True)
    if hashlib.sha256(temp.read_bytes()).hexdigest() != sha:
        raise RuntimeError(f'SHA-256 mismatch: {url}')
    temp.replace(path)
    print('Verified', url.rsplit('/', 1)[-1], flush=True)
    return path


manifest = urllib.request.urlopen('https://static.rust-lang.org/dist/channel-rust-stable.toml', timeout=30).read()
config = tomllib.loads(manifest.decode())
components = [('cargo', 'x86_64-unknown-linux-gnu'), ('rustc', 'x86_64-unknown-linux-gnu'),
              ('rust-std', 'x86_64-unknown-linux-gnu'), ('rust-std', 'wasm32-unknown-unknown')]
if '--quality' in sys.argv:
    components = [('rustfmt-preview', 'x86_64-unknown-linux-gnu'), ('clippy-preview', 'x86_64-unknown-linux-gnu')]
with ThreadPoolExecutor(max_workers=4) as pool:
    jobs = []
    for package, target in components:
        c = config['pkg'][package]['target'][target]
        jobs.append(pool.submit(download, c['xz_url'], ROOT / '.toolchain/rustup/downloads' / c['xz_hash'], c['xz_hash']))
    for j in jobs:
        j.result()
if '--quality' in sys.argv:
    sys.exit(0)
req = urllib.request.Request('https://api.github.com/repos/wasm-bindgen/wasm-pack/releases/latest',
                             headers={'User-Agent': 'RX980-local-development'})
release = json.load(urllib.request.urlopen(req, timeout=30))
asset = next(a for a in release['assets'] if 'x86_64-unknown-linux-musl.tar.gz' in a['name'])
archive = download(asset['browser_download_url'], ROOT / 'downloads' / asset['name'], asset['digest'].split(':')[1])
with tarfile.open(archive) as tar:
    member = next(x for x in tar.getmembers() if x.isfile() and x.name.endswith('/wasm-pack'))
    out = ROOT / '.toolchain/bin/wasm-pack'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(tar.extractfile(member).read())
