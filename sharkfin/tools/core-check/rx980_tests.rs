// SPDX-License-Identifier: GPL-3.0-or-later
use std::cell::{Cell, RefCell};

use crate::protocol::{family_cmds, packet, Checksum};
use crate::wire::{block_on, Node, Wire, WireError};

#[derive(Debug, PartialEq)]
enum Event {
    Send(u8),
    Sleep(u64),
    Read,
}

#[derive(Default)]
struct Board {
    id: Cell<u32>,
    op: Cell<u8>,
    auto_os: bool,
    events: RefCell<Vec<Event>>,
}

impl Node for Board {
    fn device_id(&self) -> u32 {
        self.id.get()
    }
    fn identified(&self, id: u32) {
        self.id.set(id);
    }
    fn relay(&self) -> bool {
        false
    }
    fn set_relay(&self, _: bool) {}
    fn selected(&self) -> bool {
        false
    }
    fn set_selected(&self, _: bool) {}
    fn now_ms(&self) -> f64 {
        0.0
    }
    async fn sleep_ms(&self, ms: u64) {
        self.events.borrow_mut().push(Event::Sleep(ms));
    }
    async fn raw_send(&self, data: &[u8; 64]) -> Result<(), WireError> {
        self.op.set(data[0]);
        self.events.borrow_mut().push(Event::Send(data[0]));
        Ok(())
    }
    async fn raw_read(&self) -> Result<[u8; 64], WireError> {
        self.events.borrow_mut().push(Event::Read);
        let mut reply = [0; 64];
        reply[0] = self.op.get();
        if reply[0] == 0x8f {
            reply[1..5].copy_from_slice(&671u32.to_le_bytes());
        }
        if reply[0] == 0x97 && !self.auto_os {
            reply[0] = 0x92;
        }
        Ok(reply)
    }
}

#[test]
fn rx980_identify_sets_write_timing_before_next_read() {
    let board = Board::default();
    assert_eq!(block_on(board.identify()).unwrap(), 671);
    board.events.borrow_mut().clear();
    block_on(board.send(&packet(0x07, &[], Checksum::Bit8))).unwrap();
    block_on(board.roundtrip(0x87, &[], Checksum::Bit7)).unwrap();
    assert_eq!(
        board.events.borrow().as_slice(),
        &[
            Event::Send(0x07),
            Event::Sleep(2000),
            Event::Send(0x87),
            Event::Sleep(10),
            Event::Read,
        ]
    );
}

#[test]
fn other_boards_and_reads_keep_existing_timing() {
    for (id, op) in [(0, 7), (1967, 7), (671, 0x87), (671, 0x89)] {
        let board = Board::default();
        board.id.set(id);
        block_on(board.send(&packet(op, &[], Checksum::Bit7))).unwrap();
        assert_eq!(board.events.borrow().as_slice(), &[Event::Send(op)]);
    }
}

#[test]
fn stale_auto_os_reply_never_reaches_write_opcode() {
    let board = Board::default();
    assert!(block_on(crate::ops::write_auto_os(
        &board,
        family_cmds("yc500").unwrap(),
        true
    ))
    .is_err());
    assert!(!board.events.borrow().contains(&Event::Send(0x17)));
}

#[test]
fn supported_auto_os_keeps_existing_write_path() {
    let board = Board {
        auto_os: true,
        ..Board::default()
    };
    block_on(crate::ops::write_auto_os(
        &board,
        family_cmds("yc500").unwrap(),
        true,
    ))
    .unwrap();
    assert!(board.events.borrow().contains(&Event::Send(0x17)));
}

#[test]
fn rx980_picture_slots_match_its_own_factory_firmware() {
    let layout: serde_json::Value = serde_json::from_str(include_str!(
        "../../app/src/lib/layouts/vendor/Local98_RXSTORM_RX980.json"
    ))
    .unwrap();
    let evidence: serde_json::Value = serde_json::from_str(include_str!(
        "../../app/src-tauri/data/keymap-evidence.json"
    ))
    .unwrap();
    let matrix = evidence["671"]["matrix"].as_array().unwrap();
    let keys = layout["keys"].as_array().unwrap();
    assert_eq!(keys.len(), 98);
    for key in keys {
        let slot = key["matrixIndex"].as_u64().unwrap() as usize;
        assert_eq!(
            key["matrixEntry"].as_array().unwrap().as_slice(),
            &matrix[slot * 4..slot * 4 + 4]
        );
    }
}
