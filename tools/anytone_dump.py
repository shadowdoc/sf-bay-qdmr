#!/usr/bin/env python3
"""Read-only memory dump from an AnyTone radio (D168UV/D878UV/D578UV).

Speaks the same serial protocol as libdmrconf (lib/anytone_interface.cc):

  "PROGRAM"                -> "QX" 06
  02                       -> 'I' model[7] bands ver[6] 06
  'R' addr(BE32) 10        -> 'W' addr(BE32) 10 data[16] sum 06
  "END"                    -> 06

sum = (addr + len + data bytes) & 0xff.  This tool never sends a write
command, and refuses any address outside ALLOWED (the general/extended
settings window), so it cannot reach channel data or calibration.

Output is a text dump, one 16-byte block per line, for tools/memdiff.py.
"""
import argparse
import datetime
import sys

import serial
from serial.tools import list_ports

# (VID, PID) pairs libdmrconf probes for AnyTone radios.
USB_IDS = {(0x2E3C, 0x5740), (0x28E9, 0x018A)}
# Settings window only: general settings at 0x02500000, extension at 0x02501400.
ALLOWED = (0x02500000, 0x02502000)
BLOCK = 16


class Radio:
    def __init__(self, port, timeout=1.0):
        self.ser = serial.Serial(port, 115200, timeout=timeout)
        self.ser.reset_input_buffer()

    def _xfer(self, cmd, rlen):
        self.ser.write(cmd)
        resp = self.ser.read(rlen)
        if len(resp) != rlen:
            raise IOError(f"timeout: sent {cmd[:8].hex()}, got {len(resp)}/{rlen} bytes: {resp.hex()}")
        return resp

    def enter(self):
        resp = self._xfer(b"PROGRAM", 3)
        if resp != b"QX\x06":
            raise IOError(f"unexpected PROGRAM response {resp.hex()}")
        info = self._xfer(b"\x02", 16)
        if info[0:1] != b"I" or info[15] != 0x06:
            raise IOError(f"unexpected identify response {info.hex()}")
        model = info[1:8].split(b"\0")[0].decode("latin1").strip()
        version = info[9:15].split(b"\0")[0].decode("latin1").strip()
        return model, info[8], version

    def read_block(self, addr):
        if not (ALLOWED[0] <= addr and addr + BLOCK <= ALLOWED[1]) or addr % BLOCK:
            raise ValueError(f"refusing read at {addr:08x}: outside {ALLOWED[0]:08x}-{ALLOWED[1]:08x} or unaligned")
        resp = self._xfer(b"R" + addr.to_bytes(4, "big") + bytes([BLOCK]), BLOCK + 8)
        if resp[0:1] != b"W" or int.from_bytes(resp[1:5], "big") != addr or resp[5] != BLOCK:
            raise IOError(f"bad read response header at {addr:08x}: {resp[:6].hex()}")
        if sum(resp[1:6 + BLOCK]) & 0xFF != resp[6 + BLOCK]:
            raise IOError(f"checksum mismatch at {addr:08x}: {resp.hex()}")
        if resp[7 + BLOCK] != 0x06:
            raise IOError(f"missing ACK at {addr:08x}: {resp.hex()}")
        return resp[6:6 + BLOCK]

    def leave(self):
        try:
            self._xfer(b"END", 1)
        finally:
            self.ser.close()


def find_port():
    hits = [p.device for p in list_ports.comports() if (p.vid, p.pid) in USB_IDS]
    if len(hits) != 1:
        all_ports = ", ".join(f"{p.device} ({p.vid or 0:04x}:{p.pid or 0:04x})" for p in list_ports.comports())
        raise SystemExit(f"expected exactly one AnyTone port, found {hits or 'none'}; ports: {all_ports or 'none'}")
    return hits[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", help="output dump file, e.g. dumps/E01-pf1-short-squelch.hex")
    ap.add_argument("--port", help="serial port (default: auto-detect by USB VID/PID)")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0x02500000)
    ap.add_argument("--length", type=lambda s: int(s, 0), default=0x100)
    ap.add_argument("--label", default="", help="free-text note stored in the dump header")
    a = ap.parse_args()

    start = a.start - a.start % BLOCK
    end = a.start + a.length
    radio = Radio(a.port or find_port())
    try:
        model, bands, version = radio.enter()
        lines = []
        for addr in range(start, end, BLOCK):
            lines.append(f"{addr:08x}  {radio.read_block(addr).hex(' ')}")
    finally:
        radio.leave()

    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"# model={model} bands={bands:#04x} version={version} time={stamp} label={a.label}\n")
        f.write("\n".join(lines) + "\n")
    print(f"{model} {version}: wrote {len(lines)} blocks {start:08x}-{end:08x} to {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
