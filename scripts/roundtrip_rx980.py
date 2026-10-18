# SPDX-License-Identifier: GPL-3.0-or-later
"""RX980 hardware checks adapted from sharkfin's *_roundtrip examples.

Requires a complete prior backup. Saves the original before every mutation,
restores in finally, and refuses to continue if a restore cannot be verified.
"""
import datetime as dt
import json
import sys
import time
from rx980_hid import ROOT, RX980, packet, save_json


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    backups = sorted((ROOT / 'backups').glob('rx980-*.json'))
    backup = json.loads(backups[-1].read_text(encoding='utf-8'))
    if not backup.get('complete') or backup.get('device_id') != 671:
        raise RuntimeError('A complete RX980 backup is required')
    board = RX980()
    report = {'backup': str(backups[-1]), 'device_id': 671, 'results': []}
    output = ROOT / 'reports' / ('roundtrip-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')

    def check(name, get, build, changed):
        original = get()
        restore_packet = build(original)
        record = {'name': name, 'original': original.hex(), 'restore_packet': bytes(restore_packet).hex(),
                  'status': 'pending'}
        report['results'].append(record)
        save_json(output, report)
        try:
            board.test_send(build(changed))
            after = get()
            record['readback'] = after.hex()
            record['matched'] = after == changed
        finally:
            board.test_send(restore_packet)
            restored = get()
            record['restored'] = restored.hex()
            record['restoration_verified'] = restored == original
            record['status'] = 'pass' if record.get('matched') and restored == original else 'fail'
            save_json(output, report)
            print(name, record['status'], 'restored', restored == original, flush=True)
            if restored != original:
                raise RuntimeError(f'{name}: restoration failed; original and packet saved in {output}')
        time.sleep(1)
        return record['matched']

    try:
        active = board.read_echo(0x85)[1]
        baseline = [(board.matrix(p), board.matrix(p, fn=True)) for p in range(3)]
        lighting = board.read_echo(0x87)[1:8]
        changed = bytearray(lighting)
        changed[2] = 3 if lighting[2] != 3 else 2
        check('lighting_brightness', lambda: board.read_echo(0x87)[1:8],
              lambda value: packet(0x07, value, checksum=8), bytes(changed))
        check('profile', lambda: board.read_echo(0x85)[1:2],
              lambda value: packet(0x05, value), bytes([(active + 1) % 3]))

        matrix = baseline[active][0]
        # Numpad decimal, found from this board's own matrix, never a hardcoded sibling slot.
        slots = [i // 4 for i in range(0, 512, 4) if matrix[i:i+4] == bytes([0, 0, 99, 0])]
        if len(slots) != 1:
            raise RuntimeError('Numpad decimal does not identify a unique test slot')
        slot = slots[0]
        report['test_slot'] = slot
        for fn, op, name in [(False, 0x13, 'base_key'), (True, 0x15, 'fn_key')]:
            def get(fn=fn):
                raw = board.read(0x90 if fn else 0x89, [active, slot // 16])
                return raw[(slot % 16)*4:(slot % 16)*4+4]
            def build(value, op=op):
                data = packet(op, [active, slot])
                data[8:12] = value
                return data
            check(name, get, build, bytes([0, 0, 115, 0]))  # F24, never executed by this script.

        debounce = board.read_echo(0x91)[2]
        check('debounce', lambda: board.read_echo(0x91)[2:3],
              lambda value: packet(0x11, [0, value[0]]), bytes([2 if debounce != 2 else 3]))
        sleep = board.read_echo(0x92)[1:9]
        changed = bytearray(sleep)
        changed[:2] = (int.from_bytes(sleep[:2], 'little') + 30).to_bytes(2, 'little')
        def sleep_packet(value):
            data = packet(0x12)
            data[8:16] = value
            return data
        check('sleep', lambda: board.read_echo(0x92)[1:9], sleep_packet, bytes(changed))

        # Test only an unbound empty macro slot; preserve all 256 bytes.
        macro = board.macro(49)
        if any(macro):
            report['macro'] = 'skipped: slot 49 is occupied'
        else:
            original = macro
            probe = bytearray(256)
            probe[:10] = bytes([1, 0, 115, 0, 20, 0, 115, 128, 20, 0])
            def upload(blob):
                pages = max(1, (max((i for i, b in enumerate(blob) if b), default=0) // 56) + 1)
                for p in range(pages):
                    data = packet(0x16, [49, p, 56, int(p == pages-1), 0])
                    chunk = blob[p*56:(p+1)*56]
                    data[8:8+len(chunk)] = chunk
                    board.test_send(data)
                time.sleep(0.6)
            record = {'name': 'macro_slot_49', 'original': original.hex(), 'status': 'pending'}
            report['results'].append(record)
            save_json(output, report)
            try:
                upload(probe)
                after = board.macro(49)
                record['readback'] = after.hex()
                record['matched'] = after == probe
            finally:
                time.sleep(3)
                upload(original)
                restored = board.macro(49)
                record['restoration_verified'] = restored == original
                record['status'] = 'pass' if record.get('matched') and restored == original else 'fail'
                save_json(output, report)
                print('macro_slot_49', record['status'], 'restored', restored == original, flush=True)
                if restored != original:
                    raise RuntimeError('Macro restoration failed')
        final = [(board.matrix(p), board.matrix(p, fn=True)) for p in range(3)]
        report['all_profile_layers_unchanged'] = final == baseline
        report['active_profile_unchanged'] = board.read_echo(0x85)[1] == active
        report['lighting_unchanged'] = board.read_echo(0x87)[1:8] == lighting
        if not all(report[k] for k in ['all_profile_layers_unchanged', 'active_profile_unchanged', 'lighting_unchanged']):
            raise RuntimeError('Final state differs from baseline')
    finally:
        board.close()
        report['traffic'] = board.log
        save_json(output, report)
        print('Saved', output, flush=True)


if __name__ == '__main__':
    main()
