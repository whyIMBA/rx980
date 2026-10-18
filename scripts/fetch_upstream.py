"""Fetch pinned upstream binaries and record their published SHA-256 digests."""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / 'downloads'
DOWNLOADS.mkdir(exist_ok=True)


def fetch(url, filename, expected):
    target = DOWNLOADS / filename
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        temporary = target.with_suffix(target.suffix + '.part')
        subprocess.run(['curl.exe', '--location', '--fail', '--retry', '3',
                        '--connect-timeout', '15', '--max-time', '180',
                        '--output', str(temporary), url], check=True)
        data = temporary.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise RuntimeError(f'{filename}: SHA-256 mismatch')
        target.write_bytes(data)
        temporary.unlink()
    print(filename, expected, flush=True)
    return target


req = urllib.request.Request('https://api.github.com/repos/dniminenn/sharkfin/releases/tags/v0.10.0',
                             headers={'User-Agent': 'RX980-local-development'})
release = json.load(urllib.request.urlopen(req, timeout=30))
records = []
for asset in release['assets']:
    if asset['name'] not in ['sharkfin-web-v0.10.0.tar.gz', 'sharkfin_0.10.0_x64-setup.exe']:
        continue
    path = fetch(asset['browser_download_url'], asset['name'], asset['digest'].split(':')[1])
    records.append({k: asset[k] for k in ['name', 'digest', 'browser_download_url']})
    if path.suffix == '.gz':
        target = ROOT / 'upstream-web'
        target.mkdir(exist_ok=True)
        with tarfile.open(path) as archive:
            archive.extractall(target, filter='data')
(DOWNLOADS / 'provenance.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')

url = 'https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init'
digest = urllib.request.urlopen(url + '.sha256', timeout=30).read().decode().split()[0]
fetch(url, 'rustup-init-linux', digest)
