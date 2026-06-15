#!/usr/bin/env bash
#
# clone-esp32.sh — bit-perfect clone of an existing ESP32 firmware to one or
# more new ESP32 modules. Used to provision new servo-bridge boxes without
# needing the original firmware source.
#
# Procedure:
#   1. Read the firmware off a known-good ESP32 (auto-detects flash size)
#   2. Optionally write that firmware to one or more target ESP32 modules
#
# Requires: esptool.py (installed via pip if not already available)
#
# Usage:
#   ./clone-esp32.sh read  /dev/ttyUSB0
#       Reads firmware from the ESP32 on /dev/ttyUSB0 to ./esp32_firmware_clone.bin
#
#   ./clone-esp32.sh write /dev/ttyUSB0
#       Writes ./esp32_firmware_clone.bin to the ESP32 on /dev/ttyUSB0
#
#   ./clone-esp32.sh verify /dev/ttyUSB0
#       Verifies the firmware on /dev/ttyUSB0 matches ./esp32_firmware_clone.bin
#
# Tip: identify the right /dev/ttyUSB* with:
#       ls -la /dev/serial/by-id/    # has model + serial in the symlink name
#       dmesg | grep tty             # latest connected device
#
# After flashing, the new ESP32 should be functionally identical to the source.
# Apply your physical label (servo-ID range, cable colour) to match.

set -euo pipefail

FIRMWARE_FILE="${FIRMWARE_FILE:-./esp32_firmware_clone.bin}"
BAUD="${BAUD:-460800}"

log()  { printf '\033[1;34m[esp32]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*"; }
err()  { printf '\033[1;31m[err]\033[0m %s\n'   "$*" >&2; }

# ---------------------------------------------------------------------------
# Ensure esptool.py is available
# ---------------------------------------------------------------------------
ensure_esptool() {
    if command -v esptool.py &>/dev/null; then return; fi
    if python3 -m esptool --version &>/dev/null; then
        # shellcheck disable=SC2139
        alias esptool.py="python3 -m esptool"
        return
    fi
    log "esptool not found; installing via pip..."
    pip3 install --user esptool
    if ! command -v esptool.py &>/dev/null && ! python3 -m esptool --version &>/dev/null; then
        err "esptool installation failed."
        exit 1
    fi
}

run_esptool() {
    if command -v esptool.py &>/dev/null; then
        esptool.py "$@"
    else
        python3 -m esptool "$@"
    fi
}

# ---------------------------------------------------------------------------
# Detect flash size from the chip and emit it as a hex byte-count
# ---------------------------------------------------------------------------
detect_flash_size_bytes() {
    local port="$1"
    # esptool prints something like:
    #   Detected flash size: 4MB
    local mb
    mb=$(run_esptool --port "${port}" --baud "${BAUD}" flash_id 2>&1 \
        | awk -F': ' '/Detected flash size/ { print $2 }' \
        | tr -dc '0-9')
    if [[ -z "${mb}" ]]; then
        err "Could not detect flash size on ${port}. Is the ESP32 connected and in bootloader mode?"
        return 1
    fi
    # Convert MB to bytes in hex
    printf '0x%X\n' "$(( mb * 1024 * 1024 ))"
}

# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------
cmd_read() {
    local port="$1"
    ensure_esptool
    log "Detecting flash size on ${port}..."
    local size_hex
    size_hex=$(detect_flash_size_bytes "${port}")
    log "Flash size: ${size_hex} bytes."
    log "Reading firmware to ${FIRMWARE_FILE}..."
    run_esptool --port "${port}" --baud "${BAUD}" \
        read_flash 0x0 "${size_hex}" "${FIRMWARE_FILE}"
    log "Firmware saved to ${FIRMWARE_FILE} ($(stat -c%s "${FIRMWARE_FILE}") bytes)."
}

cmd_write() {
    local port="$1"
    if [[ ! -f "${FIRMWARE_FILE}" ]]; then
        err "Firmware file ${FIRMWARE_FILE} not found. Run './clone-esp32.sh read <port>' first."
        exit 1
    fi
    ensure_esptool
    log "Verifying target flash size matches source..."
    local target_size_hex
    target_size_hex=$(detect_flash_size_bytes "${port}")
    local source_size_bytes
    source_size_bytes=$(stat -c%s "${FIRMWARE_FILE}")
    local target_size_bytes=$(( target_size_hex ))
    if [[ "${source_size_bytes}" -ne "${target_size_bytes}" ]]; then
        warn "Source firmware is ${source_size_bytes} bytes, target flash is ${target_size_bytes} bytes."
        warn "Mismatch — these ESP32 modules may not be identical hardware."
        warn "Aborting to avoid bricking the target. Investigate before retrying."
        exit 1
    fi
    log "Writing ${FIRMWARE_FILE} to ${port}..."
    run_esptool --port "${port}" --baud "${BAUD}" \
        write_flash 0x0 "${FIRMWARE_FILE}"
    log "Done. Power-cycle the ESP32 to boot into the new firmware."
}

cmd_verify() {
    local port="$1"
    if [[ ! -f "${FIRMWARE_FILE}" ]]; then
        err "Firmware file ${FIRMWARE_FILE} not found."
        exit 1
    fi
    ensure_esptool
    log "Verifying firmware on ${port} against ${FIRMWARE_FILE}..."
    run_esptool --port "${port}" --baud "${BAUD}" \
        verify_flash 0x0 "${FIRMWARE_FILE}"
    log "Verify OK."
}

usage() {
    cat <<EOF
Usage: $0 <read|write|verify> <serial-port>

  read    Read firmware from <serial-port> to ${FIRMWARE_FILE}
  write   Write ${FIRMWARE_FILE} to <serial-port>
  verify  Compare ${FIRMWARE_FILE} against the firmware on <serial-port>

Examples:
  $0 read  /dev/ttyUSB0
  $0 write /dev/ttyUSB0
  $0 verify /dev/ttyUSB0

Environment overrides:
  FIRMWARE_FILE  (default: ./esp32_firmware_clone.bin)
  BAUD           (default: 460800)
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then usage; exit 1; fi

case "$1" in
    read)   cmd_read   "$2" ;;
    write)  cmd_write  "$2" ;;
    verify) cmd_verify "$2" ;;
    *)      usage; exit 1 ;;
esac
