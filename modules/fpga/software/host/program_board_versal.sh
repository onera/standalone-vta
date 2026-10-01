#!/usr/bin/env bash
# Flash an already-built Vitis app onto a Versal board over JTAG via xsdb.
#
#   modules/fpga/software/host/program_board_versal.sh \
#       --pdi <vta_<board>.pdi> --elf <app.elf> [--jtag-cable VCK190]
#
# Paths may also come from BOARD_PDI/BOARD_ELF; the flags win. --jtag-cable
# narrows the target filters to one JTAG cable, which is required when more than
# one board is attached: `device program` otherwise fails with "Multiple devices
# found". Match it against the cable name, e.g. VCK190 or VEK280.
#
# The Zynq UltraScale+ counterpart is program_board.sh, which needs four
# artifacts (bitstream, FSBL, psu_init, app). Versal needs two: the PDI carries
# the PLM, NoC, DDR, PL and PS configuration, so there is no FSBL and no
# separate bitstream. See program_board_versal.tcl for the sequence.
#
# Env overrides: VITIS_SETTINGS (path to a settings64.sh).
set -euo pipefail

PDI="${BOARD_PDI:-}"
ELF="${BOARD_ELF:-}"
CABLE="${BOARD_JTAG_CABLE:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pdi) PDI="$2"; shift 2 ;;
        --elf) ELF="$2"; shift 2 ;;
        --jtag-cable) CABLE="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
    esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for v in PDI ELF; do
    [[ -n "${!v}" ]] || { echo "ERROR: --${v,,} not given (nor BOARD_$v)" >&2; exit 1; }
    [[ -f "${!v}" ]] || { echo "ERROR: missing ${!v}" >&2; exit 1; }
done

# program_board_versal.tcl reads these two and nothing else.
export BOARD_PDI="$PDI" BOARD_ELF="$ELF" BOARD_JTAG_CABLE="$CABLE"
echo "== pdi: $PDI"
[[ -n "$CABLE" ]] && echo "== jtag cable filter: $CABLE"
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

exec xsdb "$HERE/program_board_versal.tcl"
