# DMR codeplug build pipeline
# Usage: just build 878 | just flash 578 | just clean
# Radio aliases: 878 -> d878uv2, 168 -> d168uv, 578 -> d578uv2
# (fully-qualified names, e.g. `just build d878uv2`, still work unchanged)
#
# Serial device: dmrconf auto-detects the radio, so most of the time you
# don't need to specify anything. If auto-detect fails or more than one
# radio is connected, pass the port explicitly as a trailing argument, e.g.
#   just flash 878 /dev/ttyACM0        (Linux)
#   just flash 878 /dev/cu.usbmodem14201   (macOS)
# or set it once for the session: `export DMRCONF_DEVICE=/dev/ttyACM0`.
# Use `just detect` to check what's connected / confirm the port.

# Optional default serial device passed to dmrconf via -D. Empty means
# "let dmrconf auto-detect". Override with DMRCONF_DEVICE or a recipe arg.
default_device := env_var_or_default("DMRCONF_DEVICE", "")

# Default pause (seconds) between writing and reading back in
# verify-roundtrip, so the radio has time to apply the codeplug and reboot
# before another comms session starts. Override with
# DMRCONF_ROUNDTRIP_DELAY or a recipe arg.
roundtrip_delay := env_var_or_default("DMRCONF_ROUNDTRIP_DELAY", "30")

# Resolve a short radio alias to the full overlay/dmrconf identifier.
# Falls through unchanged for anything not in the alias table.
_resolve name:
    #!/usr/bin/env bash
    case "{{name}}" in
        878) echo d878uv2 ;;
        168) echo d168uv ;;
        578) echo d578uv2 ;;
        *)   echo "{{name}}" ;;
    esac

# Merge base + overlay, then verify against device limits.
# (No serial device involved: verify only checks the YAML against the
# --radio model spec, it never talks to the hardware.)
build radio:
    #!/usr/bin/env bash
    set -euo pipefail
    full=$(just _resolve {{radio}})
    mkdir -p build
    yq eval-all 'select(fileIndex == 0) * select(fileIndex == 1)' \
        base.yaml "overlays/${full}.yaml" > "build/${full}.yaml"
    dmrconf verify --radio="${full}" "build/${full}.yaml"

# Build, verify, and write to the connected radio
flash radio device=default_device:
    #!/usr/bin/env bash
    set -euo pipefail
    full=$(just _resolve {{radio}})
    just build "${full}"
    dev=(); [ -n "{{device}}" ] && dev=(-D "{{device}}")
    dmrconf write "${dev[@]}" "build/${full}.yaml"

# Read the codeplug back from the radio for round-trip comparison.
# `--yaml` is passed explicitly regardless of the (now-correct) `.yaml`
# extension: dmrconf's `read` command was seen failing to auto-detect
# format from `.yml` in this project's earlier layout, so being explicit
# here is cheap insurance against relying on extension-sniffing at all.
readback radio device=default_device:
    #!/usr/bin/env bash
    set -euo pipefail
    full=$(just _resolve {{radio}})
    mkdir -p build
    dev=(); [ -n "{{device}}" ] && dev=(-D "{{device}}")
    dmrconf read --yaml "${dev[@]}" "build/${full}-readback.yaml"

# Flash, wait for the radio to apply the codeplug and reboot, read it back,
# and semantically diff against what was written (requires dyff). The
# radio isn't ready for another comms session the instant `write` returns —
# it's still committing settings and rebooting — so the delay before
# `readback` isn't optional busywork; skip it and `read` will hang or come
# back with a stale/partial codeplug.
verify-roundtrip radio device=default_device delay=roundtrip_delay:
    #!/usr/bin/env bash
    set -euo pipefail
    full=$(just _resolve {{radio}})
    just flash "${full}" "{{device}}"
    echo "Waiting {{delay}}s for the radio to apply settings and reboot..." >&2
    sleep "{{delay}}"
    just readback "${full}" "{{device}}"
    dyff between "build/${full}.yaml" "build/${full}-readback.yaml"

# Detect the connected radio - handy for confirming/finding the serial
# port before flashing, or troubleshooting a flaky auto-detect.
detect device=default_device:
    #!/usr/bin/env bash
    set -euo pipefail
    dev=(); [ -n "{{device}}" ] && dev=(-D "{{device}}")
    dmrconf detect "${dev[@]}"

# Remove all generated codeplugs
clean:
    rm -rf build
