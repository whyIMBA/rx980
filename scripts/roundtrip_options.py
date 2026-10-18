# SPDX-License-Identifier: GPL-3.0-or-later
"""Toggle the Windows-key lock only, verify, restore the full option payload."""
import datetime as dt
from rx980_hid import ROOT, RX980, packet, save_json

board = RX980()
original = board.read_echo(0x86)[1:5]
record = {'device_id': 671, 'name': 'options_win_lock', 'original': original.hex()}
path = ROOT / 'reports' / ('options-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
save_json(path, record)
try:
    changed = bytearray(original)
    changed[1] ^= 1
    board.test_send(packet(0x06, changed))
    after = board.read_echo(0x86)[1:5]
    record['matched'] = after == changed
    record['readback'] = after.hex()
finally:
    try:
        board.test_send(packet(0x06, original))
        restored = board.read_echo(0x86)[1:5]
        record['restoration_verified'] = restored == original
        record['status'] = 'pass' if record.get('matched') and restored == original else 'fail'
    finally:
        board.close()
        record['traffic'] = board.log
        save_json(path, record)
print(record['status'], record['restoration_verified'])
if record['status'] != 'pass':
    raise RuntimeError('Options round-trip failed; see saved evidence')
