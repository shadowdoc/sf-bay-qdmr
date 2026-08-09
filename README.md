# SF Bay Area QDMR

A base+overlay pattern for managing DMR codeplugs across a fleet of AnyTone
radios, built on [qdmr](https://dm3mat.darc.de/qdmr/)'s extensible YAML
codeplug format. One shared `base.yaml` defines everything common (radio
IDs, contacts, group lists, channels, zones, scan lists, APRS); small
per-radio overlays carry only the differences, mostly programmable-button
assignments. A `justfile` merges, verifies, and flashes with `dmrconf`.

This started as my own working codeplug for an AT-D878UV II, AT-D578UV II,
and AT-D168UV. It's shared here as a template: fork it, swap in your own
radio IDs and repeater list, and the same pipeline works for your fleet.

## How it works

```
codeplug/
├── base.yaml            # shared: radioIDs, contacts, groupLists,
│                         #   channels, zones, scanLists, APRS
├── overlays/
│   ├── d878uv2.yaml     # AT-D878UV II (HT) deltas
│   ├── d578uv2.yaml     # AT-D578UV II (mobile) deltas
│   └── d168uv.yaml      # AT-D168UV (HT) deltas
├── build/               # generated per-radio codeplugs (gitignored)
├── justfile             # build / flash / readback / verify-roundtrip / detect / clean
└── README.md
```

Overlays contain only the divergent subtree, typically
`settings.anytone.keySettings`. Everything else lives in `base.yaml`.

## Making it yours

`base.yaml` in this repo carries my actual contacts, channels, and zones
(Bay Area / W6PW DMR; see Data provenance below). To adapt it:

1. Change `radioIDs` to your own DMR ID and callsign.
2. Replace the `contacts`, `channels`, and `zones` with your own region's
   talk groups and repeaters.
3. Update `positioning` (the APRS system) with your own source
   callsign-SSID.
4. If you're running a radio not already covered, add a new
   `overlays/<radio>.yaml`. See "AnyTone key-function model" below for how
   to work out its physical button layout, and use the qdmr `--radio`
   identifier as the filename (`d878uv2`, `d168uv`, `d578uv2`, etc.; run
   `dmrconf --list-radios` for the full set qdmr supports).

## Prerequisites

- [qdmr / dmrconf](https://dm3mat.darc.de/qdmr/) — codeplug codec and radio I/O
- [yq](https://github.com/mikefarah/yq) (mikefarah, v4+) — YAML deep-merge
- [just](https://github.com/casey/just) — task runner
- Optional: [dyff](https://github.com/homeport/dyff) — semantic YAML diffs
  for round-trip checks

macOS: `brew install yq just dyff qdmr`. The `qdmr` formula installs both
the `qdmr` GUI and the `dmrconf` CLI.
Linux: distro packages or upstream releases.

## Usage

```bash
# Merge base + overlay and verify against device limits (no hardware needed)
just build 878

# Build, verify, and write to the connected radio
just flash 878

# Confirm what radio/port is connected
just detect

# Remove generated codeplugs
just clean
```

`878`, `168`, and `578` are short aliases for `d878uv2`, `d168uv`, and
`d578uv2` respectively (fully-qualified names work everywhere too).

Radio must be powered on in normal operating mode (not firmware-update
mode) with the programming cable connected. If auto-detect fails, or more
than one radio is connected, run `just detect` to confirm what's plugged in
and on which port, then pass it explicitly. Use the bare device name under
`/dev/`, not the full path — on macOS in particular, `dmrconf -D
/dev/cu.usbmodem14201` fails to find the device, while `-D
cu.usbmodem14201` works:

```bash
just flash 878 ttyACM0          # Linux
just flash 878 cu.usbmodem14201 # macOS
```

or set a default for the session with `export DMRCONF_DEVICE=cu.usbmodem14201`.

## Workflow notes

**Editing.** Routine changes go in `base.yaml`. Radio-specific behavior
(button mappings and similar) goes in the matching overlay. `build/` is
disposable output. Never edit it directly.

**Merge semantics.** `yq`'s `*` operator deep-merges maps but *replaces*
arrays wholesale; it cannot match list items by `id`. This holds fine while
overlays only touch settings maps, with one exception already in play:
`d878uv2.yaml` and `d578uv2.yaml` each carry their own full `positioning:`
block (AnyTone only supports one FM APRS profile per radio anyway), because
if an overlay's `positioning:` list doesn't repeat `base.yaml`'s entry in
full, the merge silently drops it instead of merging by `id`. Keep those
blocks in sync with `base.yaml` by hand unless a radio deliberately needs
to beacon differently. The first time a per-radio *channel* difference is
needed, switch the merge step to an id-aware merger rather than duplicating
list sections in overlays.

**Verification.** Every build runs `dmrconf verify --radio=<model>`, which
enforces per-device limits (frequency ranges, zone sizes) before anything
touches a radio.

**Round-trip check.** `just verify-roundtrip 878` flashes, waits, reads the
codeplug back, and semantically diffs (`dyff`) against what was written:

```bash
just verify-roundtrip 878
# equivalent to:
just flash 878
sleep 15
dmrconf read --yaml build/d878uv2-readback.yaml
dyff between build/d878uv2.yaml build/d878uv2-readback.yaml
```

The wait matters because the radio's USB serial port often takes longer
than the default 15s to reboot and re-enumerate after a write, and
`readback` fails with "device ... not found" if it runs too soon. Pass a
longer delay (`DMRCONF_ROUNDTRIP_DELAY`, or a trailing argument) if this
bites you. Fields that don't survive the round trip are values the radio or
codec normalizes. Learn them once, then ignore those diffs.

## AnyTone key-function model

`settings.anytone.keySettings` in each overlay maps physical buttons to
qdmr/AnyTone function names. See the qdmr manual's [Keypad
settings](https://static.dm3mat.de/qdmr/manual/ch04s04.html) for the full
function enum. Physical layout differs by radio:

- **D168UV** (HT): only PF1/PF2 exist (`funcKeyA`/`funcKeyB`). Everything
  else is omitted from the overlay and inherits `Off` from `base.yaml`.
- **D878UV II** (HT): P1/P2 (`funcKey1`/`funcKey2`), PF1/PF2/PF3
  (`funcKeyA`/`B`/`C`; PF3 is the orange top key). `funcKey3-6`, `funcKeyD`,
  and the knob don't exist on this radio.
- **D578UV II** (mobile): P1-P6 (`funcKey1-6`) on the control head, plus
  PF1/PF2/PF3/D and a push-knob on the hand mic (`funcKeyA-D`, `funcKnob`).

Overlays are comment-annotated with physical key labels and a one-line
description of each assigned function. Worth keeping that convention if you
add your own.

## Data provenance

`base.yaml` as committed reflects the W6PW / Bay Area DMR environment at
the time of commit. It's a real, working example, not placeholder data.
Verify against current repeater listings before relying on it, and replace
it with your own region's talk groups and repeaters if you're adapting this
for your own fleet.

## License

[MIT](LICENSE).
