#!/usr/bin/env python3
"""Diff two tools/anytone_dump.py dumps byte by byte.

Changed bytes at the key-function slots libdmrconf assumes for the D168UV
are annotated with the slot name and the D168 function code from
lib/d168uv_codeplug.hh -- these are hypotheses the experiments test, not
confirmed facts.
"""
import argparse
import sys

# Offset within general settings (0x02500000) -> slot, per d168uv/d868uv_codeplug.hh.
SETTINGS = 0x02500000
KEY_SLOTS = {
    0x10: "PF1 short", 0x11: "PF2 short",
    0x12: "PF1 long", 0x13: "PF2 long",
    0x41: "PF1 very long", 0x42: "PF2 very long",
}
# D168UVCodeplug::GeneralSettingsElement::KeyFunction (CPS 1.07).
D168_FUNCS = (
    "Off Voltage Power Repeater Reverse Encryption Call VOX ToggleVFO SubPTT "
    "Scan WFM Alarm RecordSwitch Record SMS Dial GPSInformation Monitor ToggleMainChannel "
    "HotKey1 HotKey2 HotKey3 HotKey4 HotKey5 HotKey6 WorkAlone SkipChannel DMRMonitor SubChannel "
    "PriorityZone VFOScan MICSoundQuality LastCallReply ChannelType Ranging Roaming ChannelRanging "
    "MaxVolume Slot APRSType Zone RoamingSet APRSSet Mute CtcssDcsSet TBSTSend Bluetooth "
    "GPS ChannelName CDTScan APRSSend DIMShut GPSRoaming WXAlarm Squelch ChannelSettings SatPredict"
).split()


def load(path):
    """Return (header, {addr: byte})."""
    header, mem = "", {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header = line[1:].strip()
                continue
            addr, _, data = line.partition(" ")
            for i, b in enumerate(bytes.fromhex(data)):
                mem[int(addr, 16) + i] = b
    return header, mem


def annotate(addr, new):
    slot = KEY_SLOTS.get(addr - SETTINGS)
    if slot is None:
        return ""
    func = D168_FUNCS[new] if new < len(D168_FUNCS) else "?"
    return f"  <- {slot} = {func} (0x{new:02x}, per libdmrconf D168 table)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old")
    ap.add_argument("new")
    a = ap.parse_args()

    h_old, old = load(a.old)
    h_new, new = load(a.new)
    print(f"old: {a.old}  [{h_old}]")
    print(f"new: {a.new}  [{h_new}]")
    only = sorted(set(old) ^ set(new))
    if only:
        print(f"warning: {len(only)} addresses present in only one dump "
              f"({only[0]:08x}..{only[-1]:08x}); dumps cover different ranges", file=sys.stderr)

    changed = [addr for addr in sorted(set(old) & set(new)) if old[addr] != new[addr]]
    for addr in changed:
        print(f"{addr:08x} (+0x{addr - SETTINGS:03x})  {old[addr]:02x} -> {new[addr]:02x}"
              + annotate(addr, new[addr]))
    print(f"{len(changed)} byte(s) changed")


if __name__ == "__main__":
    main()
