"""Package the local app with its matching GPL source, excluding personal backups."""
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT
OUT = ROOT / 'outputs'
VERSION = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
source = OUT / f'rx980-source-{VERSION}.zip'
names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=REPO).decode().split('\0')
with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name in sorted(set(filter(None, names))):
        file = REPO / name
        if file.is_file() and not name.startswith('HANDOFF.md'):
            archive.write(file, 'rx980/' + name)
package = OUT / f'RX980-本地版-{VERSION}.zip'
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for file in sorted((OUT / 'rx980-local').rglob('*')):
        if file.is_file():
            archive.write(file, 'RX980/outputs/rx980-local/' + file.relative_to(OUT / 'rx980-local').as_posix())
    for name in ['启动RX980.cmd', '停止RX980.cmd', 'README.md', 'scripts/start-local.cjs', 'scripts/stop-local.cjs']:
        archive.write(ROOT / name, 'RX980/' + name)
    archive.write(source, 'RX980/' + source.name)
    archive.write(REPO / 'LICENSE', 'RX980/LICENSE')
    archive.write(REPO / 'THIRD-PARTY-NOTICES.md', 'RX980/THIRD-PARTY-NOTICES.md')
    archive.writestr('RX980/安装说明.txt', '需要 Node.js 22 或以上版本，以及 Edge 或 Chrome。解压后双击“启动RX980.cmd”。源码保存在随附 ZIP 中，采用 GPL-3.0-or-later。此分发包不包含个人键盘备份、测试报告或编译工具。\n')
print(json.dumps({'package': str(package), 'bytes': package.stat().st_size,
                  'source': str(source), 'source_bytes': source.stat().st_size}, ensure_ascii=False))
