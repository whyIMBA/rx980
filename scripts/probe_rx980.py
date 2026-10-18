# SPDX-License-Identifier: GPL-3.0-or-later
"""RX980 cable-only GET probe, adapted from sharkfin's probe and wire modules.

Protocol source: ../sharkfin/app/src-tauri/src/{protocol,wire,derive}.rs.
Only the specific reads below are reachable. No general-purpose send endpoint.
"""
import datetime as dt
import json
from pathlib import Path
import sys
import time

import hid

ROOT = Path(__file__).resolve().parents[1]
READS = {0x8F, 0x80, 0x85, 0x86, 0x87, 0x89, 0x8A, 0x90, 0x91, 0x92, 0x97}


def packet(op, payload=()):
    if op not in READS or len(payload) > 6:
        raise ValueError("Only the fixed GET allowlist is permitted")
    data = bytearray(64)
    data[0] = op
    data[1:1 + len(payload)] = bytes(payload)
    data[7] = 255 - (sum(data[:7]) & 255)
    return bytes(data)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    devices = [d for d in hid.enumerate(0x3151, 0x4010)
               if d['usage_page'] == 0xFFFF and d['usage'] == 2]
    if len(devices) != 1:
        raise RuntimeError(f"Expected one wired RX980 settings interface, found {len(devices)}")
    info = devices[0]
    report = {"timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
              "upstream": "dniminenn/sharkfin b36c790 v0.10.0",
              "device": {k: (v.decode(errors='replace') if isinstance(v, bytes) else v)
                         for k, v in info.items()}, "reads": []}
    dev = hid.device()
    dev.open_path(info['path'])

    def read(label, op, payload=()):
        data = packet(op, payload)
        count = dev.send_feature_report(b'\x00' + data)
        if count != 65:
            raise RuntimeError(f"Short send: {count}")
        time.sleep(0.035)
        raw = bytes(dev.get_feature_report(0, 65))
        if len(raw) != 65 or raw[0] != 0:
            raise RuntimeError(f"Unexpected feature report: {raw.hex()}")
        reply = raw[1:]
        report['reads'].append({"label": label, "request": data.hex(), "reply": reply.hex()})
        print(f"{label}: {reply[:16].hex(' ')}", flush=True)
        time.sleep(0.035)
        return reply

    try:
        identify = read('identify', 0x8F)
        device_id = int.from_bytes(identify[1:5], 'little') if identify[0] == 0x8F else None
        report['device_id'] = device_id
        if device_id != 671:
            raise RuntimeError(f"Expected RX980 board id 671, got {device_id}; stopped")
        for label, op, payload in [
            ('revision', 0x80, ()), ('profile', 0x85, ()),
            ('options', 0x86, (0,)), ('lighting', 0x87, ()),
            ('family_89', 0x89, (0, 0)), ('family_8a', 0x8A, (0, 255, 0, 0)),
            ('debounce', 0x91, ()), ('sleep', 0x92, ()), ('auto_os', 0x97, ())]:
            read(label, op, payload)
    finally:
        dev.close()
        out = ROOT / 'reports' / ('probe-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('Saved', out)


if __name__ == '__main__':
    main()
