# SPDX-License-Identifier: GPL-3.0-or-later
"""Read and save all three base/Fn profiles, 50 macro slots and user colours."""
import datetime as dt
import sys
from rx980_hid import ROOT, RX980, save_json


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    board = RX980()
    backup = {'schema': 'rx980-hardware-backup-v1', 'device_id': 671, 'family': 'yc500',
              'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
              'device': board.info, 'settings': {}, 'profiles': [], 'macros': []}
    path = ROOT / 'backups' / ('rx980-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    try:
        for name, op in [('revision', 0x80), ('profile', 0x85), ('options', 0x86),
                         ('lighting', 0x87), ('debounce', 0x91), ('sleep', 0x92)]:
            backup['settings'][name] = board.read_echo(op).hex()
        for p in range(3):
            backup['profiles'].append({'profile': p, 'base': board.matrix(p).hex(),
                                       'fn': board.matrix(p, fn=True).hex()})
            print('Backed up base and Fn profile', p, flush=True)
        for slot in range(50):
            backup['macros'].append(board.macro(slot).hex())
            if slot % 10 == 9:
                print('Backed up macros', slot + 1, flush=True)
        backup['user_picture'] = b''.join(board.read(0x8C, [p]) for p in range(7)).hex()
        backup['complete'] = True
    finally:
        board.close()
        backup['traffic'] = board.log
        save_json(path, backup)
        print('Saved', path, flush=True)


if __name__ == '__main__':
    main()
