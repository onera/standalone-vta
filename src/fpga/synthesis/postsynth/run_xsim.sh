#!/usr/bin/env bash
#*****************************************************************************************
# run_xsim.sh - compile + run VTAPostSynthTb under Vivado xsim, either:
#   --behavioral          : the emitted behavioral VTAShell (control; should reach DONE)
#   --netlist <funcsim.v> : the post-synth gate-level VTAShell netlist (the DUT under test)
#
# Encodes the known-working file partition (the part that made "running many tests"
# confusing): the netlist leg compiles ONLY the TB-wrapper SV + the funcsim netlist + glbl,
# deliberately excluding the behavioral VTAShell.sv / Core RTL (which the netlist replaces)
# so VTAShell is not doubly defined. The behavioral leg compiles all emitted SV.
#
# Output (writes.log + xsim logs) lands in --out (one isolated dir per run). The .mem files
# are loaded via absolute $readmemh paths baked into the emitted SV, so they resolve
# regardless of the run cwd as long as the emit dir (--tb) is left in place.
#
# Prereq: source <Xilinx>/2025.2/Vivado/settings64.sh   (sets XILINX_VIVADO, xvlog/xelab/xsim)
#*****************************************************************************************
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR/../../../..")"
CAS="$REPO/src/simulators/cycle_accurate_simulator"

TB="$CAS/build/emitted/vta-postsynth-tb"   # emitVtaPostSynthTb output (TB wrapper + mem/)
OUT=""
MODE=""                                     # behavioral | netlist
NETLIST=""
LAYERS=3                                    # number of layers in the emit (sets io_layerIdx width)
TIMEOUT_NS=2000000000
WRITES="writes.log"
WAVE=0                                       # --wave: dump a Vivado .wdb instead of --runall
WAVE_NS=250000                               # bounded wave window (ns); covers reset->FNSH->wedge onset
REUSE_ELAB=0                                 # --reuse-elab: skip xvlog+xelab, run the cached snapshot

usage() { sed -n '2,18p' "$0"; exit "${1:-1}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --behavioral)    MODE=behavioral; shift ;;
    --netlist)       MODE=netlist; NETLIST="$2"; shift 2 ;;
    --tb)            TB="$2"; shift 2 ;;
    --out)           OUT="$2"; shift 2 ;;
    --layers)        LAYERS="$2"; shift 2 ;;
    --timeout-ns)    TIMEOUT_NS="$2"; shift 2 ;;
    --writes)        WRITES="$2"; shift 2 ;;
    --wave)          WAVE=1; shift ;;
    --wave-ns)       WAVE=1; WAVE_NS="$2"; shift 2 ;;
    --reuse-elab)    REUSE_ELAB=1; shift ;;
    -h|--help)       usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done

[[ -n "$MODE" ]] || { echo "ERROR: pass --behavioral or --netlist <funcsim.v>" >&2; usage 1; }
[[ -n "$OUT"  ]] || { echo "ERROR: pass --out <dir>" >&2; usage 1; }
[[ -n "${XILINX_VIVADO:-}" ]] || { echo "ERROR: XILINX_VIVADO unset - source Vivado settings64.sh first" >&2; exit 1; }
command -v xvlog >/dev/null || { echo "ERROR: xvlog not on PATH - source Vivado settings64.sh" >&2; exit 1; }
[[ -d "$TB" ]] || { echo "ERROR: TB emit dir not found: $TB (run ./mill ... emitVtaPostSynthTb)" >&2; exit 1; }
[[ -f "$TB/VTAPostSynthTb.sv" ]] || { echo "ERROR: $TB/VTAPostSynthTb.sv missing" >&2; exit 1; }
# Canonicalize to absolute paths: the run executes from inside $OUT (cd below), so any
# relative --netlist / --tb passed on the command line would no longer resolve there.
TB="$(realpath "$TB")"
if [[ "$MODE" == netlist ]]; then
  [[ -f "$NETLIST" ]] || { echo "ERROR: netlist not found: $NETLIST (run the OOC synth first)" >&2; exit 1; }
  NETLIST="$(realpath "$NETLIST")"
fi

GLBL="$XILINX_VIVADO/data/verilog/src/glbl.v"
# io_layerIdx is log2Ceil(max(nLayers,2)) bits wide; match it exactly to silence width mismatch.
BITS=$(python3 -c "import math;print(max(1,math.ceil(math.log2(max($LAYERS,2)))))")

mkdir -p "$OUT"
cd "$OUT"
echo "[run_xsim] mode=$MODE tb=$TB out=$OUT layers=$LAYERS (idxW=$BITS)"

TB_FILES=("$TB"/VTAPostSynthTb.sv "$TB"/VtaHostDriver.sv "$TB"/MultiMemAxiClient.sv "$TB"/memory_*.sv)

# Always elaborate with debug so a VCD is dumped on EVERY run (waveforms by default).
# --wave bumps to -debug all (full internal visibility) for a targeted bounded dump.
DBGFLAG="-debug typical"
[[ "$WAVE" == 1 ]] && DBGFLAG="-debug all"

# --- elaboration, with checkpoints to avoid re-doing the slow parts ---------------------
# Three caches (all per --out dir, which persists xsim.dir between runs):
#   * --reuse-elab : skip xvlog+xelab entirely, run the cached snapshot (use when ONLY run
#                    params change: watchdog/wave window). Fastest.
#   * netlist parse: the 19.8MB VTAXilinxShell_funcsim.v is re-parsed ONLY when it changes
#                    (re-synth); a stamp file caches it. So sim_top/probe edits re-parse just
#                    the tiny TB wrapper, not the netlist.
#   * the run's wave.vcd/wave.wdb are themselves the offline-analysis checkpoint (inspect the
#                    wedge in Vivado/GTKWave without re-simulating).
if [[ "$REUSE_ELAB" == 1 && -d xsim.dir/snap ]]; then
  echo "[run_xsim] --reuse-elab: skipping xvlog+xelab, running the cached snapshot"
elif [[ "$MODE" == behavioral ]]; then
  xvlog -d ENABLE_INITIAL_MEM_ -d "LAYERIDX_W=$BITS" -sv "$SCRIPT_DIR/sim_top.sv" "$TB"/*.sv
  xelab sim_top $DBGFLAG -s snap --timescale 1ns/1ps
else
  # Always recompile the small TB wrapper + sim_top (cheap). Cache the big netlist parse.
  xvlog -d ENABLE_INITIAL_MEM_ -d "LAYERIDX_W=$BITS" -sv "$SCRIPT_DIR/sim_top.sv" "${TB_FILES[@]}"
  nlstamp="$NETLIST $(stat -c %Y "$NETLIST" 2>/dev/null)"
  if [[ -f .nlxvlog.stamp && "$(cat .nlxvlog.stamp)" == "$nlstamp" && -d xsim.dir/work ]]; then
    echo "[run_xsim] netlist unchanged -> reusing cached parse (xvlog skipped)"
  else
    xvlog "$NETLIST" "$GLBL"
    echo "$nlstamp" > .nlxvlog.stamp
  fi
  xelab sim_top glbl $DBGFLAG -L unisims_ver -L secureip -s snap --timescale 1ns/1ps
fi

# VCD (+ wdb) on every run: TB hierarchy (driver FSM, dbgW) + VTA top ports (s_axi_control
# read data the driver polls, debug_*/vcr probes, m_axi_gmem). Default runs to completion
# (respecting the sim_top watchdog/$finish); --wave-ns bounds the window for a quick dump.
RUNCMD="run -all"
[[ "$WAVE" == 1 ]] && RUNCMD="run ${WAVE_NS} ns"
cat > wave.tcl <<TCL
open_vcd wave.vcd
log_vcd [get_objects -recursive /sim_top/dut/driver/*]
log_vcd [get_objects /sim_top/*]
log_vcd [get_objects /sim_top/dut/*]
log_vcd [get_objects /sim_top/dut/vta/*]
${RUNCMD}
flush_vcd
close_vcd
quit
TCL
xsim snap -testplusarg "WRITES=$WRITES" -testplusarg "TIMEOUT_NS=$TIMEOUT_NS" \
      -wdb wave.wdb -tclbatch wave.tcl 2>&1 | tee sim.log
echo "[run_xsim] done -> $OUT/{$WRITES,sim.log,wave.vcd,wave.wdb}"
grep -E "SIM_TOP: (DONE|WEDGE|TIMEOUT)" sim.log || true
