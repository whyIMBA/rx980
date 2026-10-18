"""Build RX980 geometry against its published factory matrix and live backup.

Only physical key positions and HID usages are extracted from the installed
driver. No vendor program, image, or executable is copied into the fork.
"""
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'sharkfin'
DATA = REPO / 'app/src-tauri/data'
LAYOUTS = REPO / 'app/src/lib/layouts/vendor'

source = Path(r'C:\RXSTORM Driver\resources\app\dist\main.js').read_text(encoding='utf-8-sig')
match = re.search(r'exports\.yzw_rx980=\{.*?layout:\[(.*?)\]\}', source)
raw = re.sub(r'([,{])(keyName|value|x|y|w|h):', r'\1"\2":', '[' + match[1] + ']')
geometry = json.loads(raw)
assert len(geometry) == 98
firmware = json.loads((DATA / 'keymap-evidence.json').read_text(encoding='utf-8'))['671']
matrix = firmware['matrix']
entries = [matrix[i:i+4] for i in range(0, len(matrix), 4)]
backup = json.loads(sorted((ROOT / 'backups').glob('rx980-*.json'))[-1].read_text(encoding='utf-8'))
assert bytes.fromhex(backup['profiles'][1]['base'])[:len(matrix)] == bytes(matrix)

codes = {}
texts = {}
files = [LAYOUTS / 'Local98_Akko_3098B.json'] + sorted(LAYOUTS.glob('Local*.json'))
for file in files:
    for key in json.loads(file.read_text(encoding='utf-8')).get('keys', []):
        usage = key.get('hidUsage')
        if usage is not None and key.get('code'):
            codes.setdefault(usage, key['code'])
            texts.setdefault(usage, key.get('text', key['code']))
codes[0x65] = 'ContextMenu'
keys = []
for key in geometry:
    value = key['value']
    entry = [0, 0, value, 0] if value <= 255 else list(value.to_bytes(4, 'big'))
    slots = [i for i, e in enumerate(entries) if e == entry]
    if len(slots) != 1:
        raise RuntimeError(f"Ambiguous factory slot for {key['keyName']}: {slots}")
    usage = value if value <= 255 else None
    code = codes.get(usage) if usage is not None else 'Fn'
    if not code:
        raise RuntimeError(f'Missing DOM key code for HID usage {usage}')
    keys.append({'code': code, 'type': 'key', 'x': key['x'] + 1, 'y': -key['y'] + 1,
                 'w': key['w'], 'h': key['h'], 'text': texts.get(usage, 'Fn'),
                 'matrixIndex': slots[0], 'matrixEntry': entry, 'hidUsage': usage,
                 'consumerUsage': None})
assert len({k['matrixIndex'] for k in keys}) == 98
layout_name = 'Local98_RXSTORM_RX980'
layout = {'local': True,
          '_evidence': 'RX980 id 671 firmware v505: factory matrix from keymap-evidence.json, all bytes match hardware profile 1 read on 2026-10-18. Geometry and physical HID usages from the installed RXSTORM Driver 1.2.60 yzw_rx980 layout. Slot 77 base/Fn writes read back and restored.',
          'canvas': {'width': max(k['x'] + k['w'] for k in keys) + 1,
                     'height': max(k['y'] + k['h'] for k in keys) + 1}, 'keys': keys}
(LAYOUTS / (layout_name + '.json')).write_text(json.dumps(layout, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
override = {'_override': True, 'id': 671, 'keyLayout': layout_name, 'family': 'yc500',
            '_why': 'RX980 cable hardware verified; the legacy registry has no protocol family or geometry.',
            '_evidence': '2026-10-18: USB 3151:4010, handshake 671, firmware 5.05. 0x89 is a keymap, 0x8A is all FF. Lighting, profile, base and Fn single-slot keys, debounce, sleep, options Windows-key lock and macro slot 49 were written, read back and restored. All six profile layers matched the pre-test baseline. See docs/RX980.md.',
            '_unknown': 'Wireless writes, full RGB effect catalogue, per-key painting and physical macro playback have not been tested. GET_AUTO_OS 0x97 replays the prior reply on this firmware.',
            'features': {'knob': [], 'debounce': True, 'sleep24': True, 'sleepBT': True,
                         'magneticSwitches': False, 'screen': False, 'sideLight': False}}
extra_path = DATA / 'devices.extra.json'
extra = [d for d in json.loads(extra_path.read_text(encoding='utf-8')) if d['id'] != 671]
extra.append(override)
extra_path.write_text(json.dumps(extra, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
device_path = DATA / 'devices.json'
devices = json.loads(device_path.read_text(encoding='utf-8'))
for device in devices:
    if device['id'] == 671:
        device.update({k: v for k, v in override.items() if not k.startswith('_')})
device_path.write_text(json.dumps(devices, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('RX980 layout:', len(keys), 'keys;', len(set(k['code'] for k in keys)), 'unique codes')
print('Firmware matrix equals live profile 1; all physical keys have unique slots')
