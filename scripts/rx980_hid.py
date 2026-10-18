# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows hardware evidence adapter for sharkfin v0.10.0.

Packet layouts and pacing follow upstream protocol/mod.rs and wire.rs.
This module is used by diagnostics, not by the application's protocol core.
"""
import json
from pathlib import Path
import time
import hid

ROOT = Path(__file__).resolve().parents[1]
GETS = {0x8F, 0x80, 0x85, 0x86, 0x87, 0x89, 0x8A, 0x8B, 0x8C, 0x90, 0x91, 0x92, 0x97}


def packet(op, payload=(), checksum=7):
    if len(payload) > 63:
        raise ValueError('Payload too long')
    data = bytearray(64)
    data[0] = op
    data[1:1 + len(payload)] = bytes(payload)
    data[checksum] = 255 - (sum(data[:checksum]) & 255)
    return data


class RX980:
    def __init__(self):
        matches = [d for d in hid.enumerate(0x3151, 0x4010)
                   if d['usage_page'] == 0xFFFF and d['usage'] == 2]
        if len(matches) != 1:
            raise RuntimeError(f'Expected exactly one wired RX980, found {len(matches)}')
        self.info = {k: v.decode(errors='replace') if isinstance(v, bytes) else v
                     for k, v in matches[0].items()}
        self.dev = hid.device()
        self.dev.open_path(matches[0]['path'])
        self.log = []
        self.last_send = 0
        try:
            reply = self.read(0x8F)
            if reply[0] != 0x8F or int.from_bytes(reply[1:5], 'little') != 671:
                raise RuntimeError('Board identity differs from RX980 id 671')
            r89 = self.read(0x89, [0, 0])
            r8a = self.read(0x8A, [0, 255, 0, 0])
            keys = sum(r89[i:i+2] == b'\x00\x00' and 4 <= r89[i+2] <= 231 and r89[i+3] == 0
                       for i in range(0, 64, 4))
            if keys < 8 or r8a != bytes([255]) * 64:
                raise RuntimeError('Hardware replies do not establish yc500 family')
        except BaseException:
            self.dev.close()
            raise

    def close(self):
        self.dev.close()

    def _send(self, data):
        time.sleep(max(0, 0.025 - (time.monotonic() - self.last_send)))
        if len(data) != 64:
            raise ValueError('Expected 64 bytes')
        result = self.dev.send_feature_report(b'\x00' + bytes(data))
        self.last_send = time.monotonic()
        if result != 65:
            raise RuntimeError(f'Short HID send: {result}')
        self.log.append({'request': bytes(data).hex()})

    def read(self, op, payload=()):
        if op not in GETS:
            raise ValueError('Opcode is not a permitted GET')
        self._send(packet(op, payload))
        time.sleep(0.035)
        raw = bytes(self.dev.get_feature_report(0, 65))
        if len(raw) != 65 or raw[0] != 0:
            raise RuntimeError(f'Unexpected HID report length or ID: {raw.hex()}')
        reply = raw[1:]
        self.log[-1]['reply'] = reply.hex()
        return reply

    def read_echo(self, op, payload=()):
        reply = self.read(op, payload)
        if reply[0] != op:
            raise RuntimeError(f'Expected echo {op:02x}, got {reply[0]:02x}')
        return reply

    def matrix(self, profile, fn=False):
        return b''.join(self.read(0x90 if fn else 0x89, [profile, p]) for p in range(8))

    def macro(self, slot):
        return b''.join(self.read(0x8B, [slot, p]) for p in range(4))

    def test_send(self, data):
        # Only reversible settings used by the dedicated round-trip script.
        if data[0] not in {0x05, 0x06, 0x07, 0x11, 0x12, 0x13, 0x15, 0x16}:
            raise ValueError('Not a permitted round-trip write')
        self._send(data)
        # RX980 v5.05 returns an empty reply when queried 300 ms after SET.
        time.sleep(2)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
