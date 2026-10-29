# D168UV key-settings experiments

Goal: confirm where the D168UV stores programmable-key functions and which
byte encodes each function, to back a fix for
[hmatuschek/qdmr#1018](https://github.com/hmatuschek/qdmr/issues/1018).
Workflow is in [tools/README.md](tools/README.md).

**Hypothesis (from libdmrconf `lib/d168uv_codeplug.hh`):** key bytes live in
general settings at 0x02500000: PF1/PF2 short at +0x10/+0x11, long at
+0x12/+0x13, very long at +0x41/+0x42, encoded with the D168 `KeyFunction`
table. libdmrconf's `setFuncKeyBVeryLong` writes +0x13 instead of +0x42
(`d168uv_codeplug.cc:347`), and long/very-long use the generic enum, which
diverges from the D168 table above `Zone` (0x29).

Each experiment changes exactly one field in the CPS on top of the previous
one, writes to the radio, then dumps. Diff each dump against the previous.

| # | Key / press | CPS function | Expected (address = byte) | Dump file | Observed changes | Notes |
|---|---|---|---|---|---|---|
| D0 | — | (baseline, no CPS write) | — | `dumps/D0-baseline.hex` | +10=08 ToggleVFO, +11=13 ToggleMainChannel, +12=02 Power, +13=00 Off, +41=00 Off, +42=1d SubChannel | V100. Short/long slots match the codeplug under the D168 table; PF2 long is Off and SubChannel sits in the PF2 very-long slot (+0x42) |
| D0b | — | CPS write, nothing changed | no key bytes change | `dumps/D0b-control.hex` | 13 bytes, none at key slots: ff→00 at +3d, +54–56, +6a–6d, +ef; ff→01 at +40, +71, +d6; 04→00 at +be | ✓ key slots stable. 12 of 13 are 0xff→value: fields dmrconf left unset that the CPS fills in |
| E1 | PF1 short | Squelch | 0x02500010 = 0x37 (0x38 = D878 table) | `dumps/E01-pf1-short.hex` | **+10 08→37** ✓; also +04 43→00, +e6 ef→00, ff→00 at +14, +43–45, +b2, +b4 | Confirms (B) and the D168 table (not D878's 0x38). The non-key ff→00 changes continue, so CPS normalization isn't a one-shot; only key slots matter |
| E2 | PF1 long | VOX | 0x02500012 = 0x07 | `dumps/E02-pf1-long.hex` | **+12 02→07** ✓, nothing else | Clean single-byte diff; CPS normalization has settled |
| E3 | PF1 very long | Scan | 0x02500041 = 0x0a | `dumps/E03-pf1-vlong.hex` | **+41 00→0a** ✓, nothing else | CPS "Long Key 2" = very-long slot, confirmed by write |
| E4 | PF2 short | SMS | 0x02500011 = 0x0f | `dumps/E04-pf2-short.hex` | **+11 13→0f** ✓, nothing else | |
| E5 | PF2 long | Reverse | 0x02500013 = 0x04 | `dumps/E05-pf2-long.hex` | **+13 00→04** ✓, nothing else | +0x13 is PF2 *long* only — so libdmrconf's very-long setter writing here clobbers PF2 long |
| E6 | PF2 very long | Roaming Set | 0x02500042 = 0x2a (generic enum would give 0x2e) | `dumps/E06-pf2-vlong.hex` | **+42 1d→2a** ✓, nothing else | the #1018 slot. Radio uses the D168 code 0x2a, not the generic enum's 0x2e |

CPS key-function dropdown order (turned out *not* to be the byte value —
see "Resolved" below):

```
(CPS dropdown order, top to bottom, PF2 short; # = list position)
 0 Off              1 Voltage            2 Power              3 Repeater
 4 Reverse          5 Digital Encryption 6 Call               7 Vox
 8 V/M              9 Sub PTT           10 Scan              11 FM
12 Alarm           13 Record Switch     14 Record            15 SMS
16 Dial            17 Monitor           18 Main Channel Switch
19-24 Hot Key 1-6  25 Work Alone        26 Nuisance Delete   27 Digital monitor
28 Sub CH Switch   29 Priority Zone     30 VFO Scan          31 MIC Sound Quality
32 LastCall Replay 33 Channel Type Switch 34 Roaming         35 Max Volume
36 Slot Switch     37 Zone Select       38 Timed Roaming Set 39 Mute Timing
40 CTC/DCS Set     41 TBST Send         42 BT Wireless       43 GPS
44 Ch. Name        45 CDT Scan          46 APRS Send         47 DIM Shut
48 GPS Roaming     49 WX Alarm          50 Sq Level          51 CH Setting
52 Satellite Predicting
```

53 entries vs 58 in libdmrconf's D168 table, which also has GPSInformation
(0x11), Ranging (0x23), ChannelRanging (0x25), APRSType (0x28) and APRSSet
(0x2b). Positions match libdmrconf's byte values up to Dial (0x10), then
drift. Two hypotheses:

- **(A) position = byte**: libdmrconf's table is wrong from 0x11 up.
- **(B) CPS hides unsupported functions; bytes keep libdmrconf's numbering.**
  D0 favors (B): PF2 short = 0x13 was written by dmrconf as
  ToggleMainChannel (under (A) 0x13 = Hot Key 1), and PF2 very long = 0x1d
  = SubChannel under (B) but Priority Zone under (A).

**Resolved — (B).** CPS read of the D0 state showed PF1 Short = V/M (0x08),
PF2 Short = Main Channel Switch (0x13), PF1 Long Key 1 = Power (0x02), PF2
Long Key 1 = Off (0x00), PF1 Long Key 2 = Off (0x00), PF2 Long Key 2 = Sub
CH Switch (0x1d). 0x13 and 0x1d decode correctly only under (B). This also
confirms the CPS's "Long Key 1" is libdmrconf's long slot (+0x12/+0x13) and
"Long Key 2" is its very-long slot (+0x41/+0x42).

Expected bytes for the E rows under each hypothesis: E1 Sq Level 0x37 (B) /
0x32 (A); E6 Timed Roaming Set 0x2a (B) / 0x26 (A).

## L1 — dmrconf write path

E1–E6 pin down what the radio expects. L1 checks what libdmrconf actually
writes: `dmrconf write` of `dumps/L1-dmrconf-keytest.yaml` (base + d168uv
overlay, six PF keys changed), then dump and diff against E6.

From the source: the D168 long/very-long setters `static_cast` the generic
`AnytoneKeySettingsExtension::KeyFunction` enum (implicit values, matching
the D168 table only up to Zone = 0x29); short keys go through the inherited
D878 `KeyFunction::encode`; `setFuncKeyBVeryLong` writes `progFuncKeyBLong`.

| Slot | Key | YAML | Correct (D168) | If bug | Observed |
|---|---|---|---|---|---|
| +10 | AShort | Squelch | 0x37 | 0x38 (D878 table) | **0x38** ✗ bug — radio shows CH Setting |
| +11 | BShort | SMS | 0x0f | — (control) | 0x0f ✓ (unchanged from E4) |
| +12 | ALong | RoamingSet | 0x2a | 0x2e (generic cast) | **0x2e** ✗ bug — radio shows TBST Send |
| +13 | BLong | Reverse | 0x04 | 0x07 (BVeryLong lands here) | **0x07** ✗ bug — Reverse overwritten by VOX |
| +41 | AVeryLong | Mute | 0x2c | 0x30 (generic cast) | **0x30** ✗ bug — radio shows GPS |
| +42 | BVeryLong | VOX | 0x07 | 0x2a (untouched since E6) | **0x2a** ✗ bug — never written |

Dump: `dumps/L1-dmrconf-write.hex` (diffed against E6). All five predicted
bugs reproduced. The other 40 changed bytes are outside the key slots
(+00, +04, +1f–20, +72–ac, +e6) — dmrconf's own values for settings the
CPS had rewritten; not part of this test.

**Confirmed libdmrconf D168UV key-settings bugs (V100 firmware):**
1. `setFuncKeyBVeryLong` writes `progFuncKeyBLong` (+0x13) instead of
   `progFuncKeyBVeryLong` (+0x42): PF2 very long clobbers PF2 long, and
   +0x42 is never written.
2. Long and very-long setters `static_cast` the generic
   `AnytoneKeySettingsExtension::KeyFunction` instead of using
   `D168UVCodeplug::KeyFunction::encode`: every function above Zone (0x29)
   lands on the wrong code.
3. PF1/PF2 short keys use the inherited D878 `KeyFunction::encode`, which
   disagrees with the D168 table at least at Squelch (0x38 vs 0x37).

Source references (hmatuschek/qdmr master, read 2026-10-27):
`lib/d168uv_codeplug.cc` (A/B long + very-long accessors, `static_cast`;
`setFuncKeyBVeryLong` uses `Offset::progFuncKeyBLong()`),
`lib/d168uv_codeplug.hh` (offsets 0x12/0x13/0x41/0x42; `GeneralSettingsElement`
derives from `D878UVCodeplug::GeneralSettingsElement`; no A/B short override),
`lib/anytone_settingsextension.hh` (generic `KeyFunction`, implicit values:
… Zone=41, ZoneUp, ZoneDown, Exit, Menu, RoamingSet=46, APRSSet, Mute=48 …
Squelch=63), `lib/d878uv_codeplug.cc` (short/long accessors via
`KeyFunction::encode`).

## F1/F2 — patched dmrconf

Same `dumps/L1-dmrconf-keytest.yaml`, written with a locally built dmrconf
(fork `shadowdoc/qdmr`, checkout at `~/dev/qdmr-upstream`).

| Dump | Build | +10 | +11 | +12 | +13 | +41 | +42 |
|---|---|---|---|---|---|---|---|
| `dumps/F1-patched-long-keys.hex` | `fix-d168uv-long-keys` (bugs 1+2) | 38 ✗ (bug 3, expected) | 0f | 2a ✓ | 04 ✓ | 2c ✓ | 07 ✓ |
| `dumps/F2-patched-both-fixes.hex` | `local-d168uv-both-fixes` (bugs 1–3) | 37 ✓ | 0f | 2a ✓ | 04 ✓ | 2c ✓ | 07 ✓ |

All six key slots correct with both fixes. F1 also showed +09/+0a (squelch
level A/B) 01→02 vs L1; the YAML doesn't set squelch and the patch doesn't
touch those offsets, so it was presumably changed on the radio between dumps.

Reading the source tables (`d878uv_codeplug.hh` vs `d168uv_codeplug.hh`):
bug 3 also affects DIMShut (D878 0x36 vs D168 0x34), and WXAlarm,
ChannelSettings and SatPredict have no D878 code so encode as Off. Only
Squelch is hardware-confirmed.

**F3 — restore:** `build/d168uv.yaml` written with the both-fixes build;
`dumps/F3-restore-real-codeplug.hex` shows +10=08, +11=13, +12=02,
+13=1d (PF2 long = SubChannel, which upstream dmrconf left Off), +41=00,
+42=00. Against D0, the only key-slot differences are +13 and +42, i.e.
exactly bug 1. No CPS fix-up needed.

## Status and next steps (as of 2026-10-27)

**Radio state:** the D168UV holds the real codeplug (`build/d168uv.yaml`)
with correct keys, written by the patched dmrconf (F3). Until the fix is
released upstream, a plain `just flash 168` with Homebrew's dmrconf will
reintroduce bug 1 (PF2 long → Off); use
`~/dev/qdmr-upstream/build/cli/dmrconf` instead.

**To do:**
- Post the evidence on qdmr#1018 (bugs 1 and 2: slot table, E1–E6 + L1
  bytes, suggested fix: use `progFuncKeyBVeryLong`, and encode/decode
  long + very-long via `D168UVCodeplug::KeyFunction`). Bug 3 (short keys
  using the D878 table) is not part of #1018 — file it separately.
- Not yet checked: whether the D878 and D168 short-key tables disagree
  anywhere besides Squelch (would need one CPS write per function, or a
  read of `D878UVCodeplug::KeyFunction::encode`).
- `dmrconf verify --radio=d168uv` on the L1 file gave 368 warnings, none
  key-related: 268× channel `power: Max` not encodable (Low/High only),
  98× `groupList must refer to an instances of RXGroupList`, APRS icon
  `Car` not encodable. Presumably the same on a normal `just build 168`
  (unconfirmed); the groupList ones likely drop RX group lists on the 168
  and are worth fixing in base.yaml. Raw output: `warnings.log` (repo root).
