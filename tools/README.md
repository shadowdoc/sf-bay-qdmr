# D168UV key-settings reverse engineering

Differential memory reads: change one key setting in the AnyTone CPS, write
it to the radio, then read the settings area back directly and diff. No USB
capture needed. Results go in [../EXPERIMENTS.md](../EXPERIMENTS.md).

Requires Python 3 + pyserial (`python -m pip install pyserial`).

## Tools

- `anytone_dump.py OUT` — read-only dump of 0x02500000–0x025000FF (override
  with `--start`/`--length`). Sends only `PROGRAM`, identify, `R` reads and
  `END`; it has no write command and refuses addresses outside
  0x02500000–0x02501FFF. Port is auto-detected by USB VID/PID, or pass
  `--port COM5`.
- `memdiff.py OLD NEW` — byte diff of two dumps; changes at the expected
  key slots are annotated with slot name and D168 function name.

## Per-experiment loop

1. In the CPS, change exactly one setting (see EXPERIMENTS.md) and write
   to the radio.
2. Close the CPS (or at least disconnect it) so it releases the COM port,
   and wait for the radio to finish rebooting.
3. `python tools/anytone_dump.py dumps/E01-pf1-short.hex --label "PF1 short=Squelch"`
4. `python tools/memdiff.py dumps/D0b-control.hex dumps/E01-pf1-short.hex`
   (diff against the previous experiment's dump)
5. Fill in the row in EXPERIMENTS.md.

Start with `D0` (dump only) and `D0b` (CPS write with no changes, then
dump) so bytes that change on every write can be told apart from real
changes.
