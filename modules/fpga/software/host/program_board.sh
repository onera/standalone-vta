#!/usr/bin/env bash
# Flash an already-built Vitis app onto a board over JTAG via xsdb.
#
#   modules/fpga/software/host/program_board.sh \
#       --bit <bitstream.bit> --elf <app.elf> --fsbl <fsbl.elf> --psinit <psu_init.tcl>
#
# Paths may also come from BOARD_BIT/BOARD_ELF/BOARD_FSBL/BOARD_PSINIT; the
# flags win.
#
# Env overrides: VITIS_SETTINGS (path to a settings64.sh).
set -euo pipefail

BIT="${BOARD_BIT:-}"
ELF="${BOARD_ELF:-}"
FSBL="${BOARD_FSBL:-}"
PSINIT="${BOARD_PSINIT:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bit)    BIT="$2";    shift 2 ;;
        --elf)    ELF="$2";    shift 2 ;;
        --fsbl)   FSBL="$2";   shift 2 ;;
        --psinit) PSINIT="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
    esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for v in BIT ELF FSBL PSINIT; do
    [[ -n "${!v}" ]] || { echo "ERROR: --${v,,} not given (nor BOARD_$v)" >&2; exit 1; }
    [[ -f "${!v}" ]] || { echo "ERROR: missing ${!v}" >&2; exit 1; }
done

# program_board.tcl reads these four and nothing else.
export BOARD_BIT="$BIT" BOARD_ELF="$ELF" BOARD_FSBL="$FSBL" BOARD_PSINIT="$PSINIT"
echo "== app: $ELF"

# --- source Vitis --------------------------------------------------------------
SETTINGS="${VITIS_SETTINGS:-}"
if [[ -z "$SETTINGS" ]]; then
    for c in /opt/Xilinx/*/Vitis/settings64.sh /tools/Xilinx/*/Vitis/settings64.sh; do
        [[ -f "$c" ]] && SETTINGS="$c" && break
    done
fi
[[ -n "$SETTINGS" && -f "$SETTINGS" ]] || { echo "ERROR: no Vitis settings64.sh (set VITIS_SETTINGS)"; exit 1; }
# settings64.sh reads unset variables (PYTHONPATH), so it cannot run under -u.
set +u
# shellcheck disable=SC1090
source "$SETTINGS"
set -u
echo "== xsdb: $(command -v xsdb)"

exec xsdb "$HERE/program_board.tcl"
