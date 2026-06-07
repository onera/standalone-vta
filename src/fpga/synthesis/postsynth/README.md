# Post-synthesis gate-level simulation (xsim)

Run the synthesized VTAShell **netlist** through a self-driving multi-layer testbench and
compare its OUT to the fsim golden. This is how the FPGA-only hang and the block-4 wrong-output
defect are reproduced **offline, without a board** — they appear in the gate-level netlist but
not in behavioral RTL.

`funcsim` (mode=synth) has **no SDF / zero delay**, so any divergence it shows is a
**synthesis logic** difference (gates ≠ RTL), not timing. That is the whole point of the flow.

## Pieces (all committed here)

| file | role |
|------|------|
| `../ooc_netlist.tcl` | OOC synth/impl of VTAShell → `VTAShell_funcsim.v` (mode=synth) or `+timesim.v`+`.sdf` (mode=impl) |
| `synth_netlist.sh` | generates `ooc_params.tcl` from `boards/<board>.json` and runs `ooc_netlist.tcl` |
| `sim_top.sv` | xsim wrapper: clock/reset, `io_dbgW` write-snoop → `writes.log`, DONE/WEDGE/TIMEOUT |
| `run_xsim.sh` | compiles + runs xsim, `--behavioral` (control) or `--netlist <funcsim.v>` (DUT) |
| `compare_out.py` | strb-aware OUT compare vs `simulators_output/output<layer>.bin` |

The Chisel side (`VTAPostSynthTb`, `CompilerOutputLayout`, `VtaHostDriver`) and the Mill emit
tasks live in `src/simulators/cycle_accurate_simulator`.

## Per-run output layout (kept isolated so runs never clobber)

```
src/fpga/synthesis/build/postsynth/<config>-<board>/
  ooc-netlist/   VTAShell_funcsim.v, post_synth.dcp, ooc_params.tcl, vivado.log
  xsim-net/      writes.log, sim.log         (gate-level run)
  xsim-behav/    writes.log, sim.log         (behavioral control run)
```
`build/` is gitignored. One dir per `<config>-<board>`; never share `writes.log` across runs.

## Runbook (default config, ZCU104, the known hang repro)

Prereqs: `source ~/Xilinx/2025.2/Vivado/settings64.sh` and the compiler venv
(`standalone-vta/src/compiler/.venv`).

```bash
REPO=$(git rev-parse --show-toplevel)
CFG=vta_config.json ; BOARD=zcu104
LAYERS=MaxPool2,QLinearConv10,QLinearConv7        # 2nd-after-MaxPool2 is where it wedges
RUN=$REPO/src/fpga/synthesis/build/postsynth/${CFG%.json}-$BOARD
CAS=$REPO/src/simulators/cycle_accurate_simulator

# 1. compile model + fsim golden + per-layer INP/ACC/OUT dumps
cd $REPO/examples && source $REPO/src/compiler/.venv/bin/activate
make compile_and_run CONFIG_FILE=../config/$CFG ONNX_FILE=onnx/deep_cnn_maxpool.onnx
( cd $REPO/src/simulators/functional_simulator && ./build/fsim --dump-layers )   # -> simulators_output/{input,output}<layer>.bin

# 2. emit the synth input (clean VTAShell) and the xsim TB (+ per-layer .mem).
#    perLayerTimeout small so the driver watchdog (=> SIM_TOP WEDGE) fires in bounded sim cycles.
cd $CAS
./mill -Dvta.config.file=$CFG emitVtaSimConfig
./mill -Dvta.config.file=$CFG -Dvta.layers=$LAYERS -Dvta.perLayerTimeout=100000 emitVtaPostSynthTb

# 3. OOC-synthesize the gate-level netlist (minutes)
bash $REPO/src/fpga/synthesis/postsynth/synth_netlist.sh --board $BOARD \
     --sv-dir $CAS/build/emitted/vta-sim-shell --out $RUN/ooc-netlist --mode synth

# 4. behavioral control (should DONE) vs gate-level funcsim (should WEDGE)
POST=$REPO/src/fpga/synthesis/postsynth
bash $POST/run_xsim.sh --behavioral                          --out $RUN/xsim-behav --layers 3
bash $POST/run_xsim.sh --netlist $RUN/ooc-netlist/VTAShell_funcsim.v --out $RUN/xsim-net --layers 3

# 5. strb-aware OUT compare (for the runs that reach DONE)
python3 $POST/compare_out.py --writes $RUN/xsim-net/writes.log --layers $LAYERS \
   --compiler-out $REPO/compiler_output --golden-dir $REPO/simulators_output
```

Expected pre-fix: `xsim-behav/sim.log` → `SIM_TOP: DONE`; `xsim-net/sim.log` →
`SIM_TOP: WEDGE (driver watchdog) layer=1 …` (wedged on the layer after MaxPool2).

## Notes

- Gate-level funcsim is slow in wallclock. Lower `-Dvta.perLayerTimeout` to bound a wedge
  (the watchdog counts **sim cycles**); raise it if a healthy layer is being cut off.
- `mode=impl` adds place&route + `VTAShell_timesim.v` + `.sdf` for a timing sim, but the known
  defects are **pre-timing** (they show in funcsim), so `mode=synth` is the default.
- Verilator cannot build stock Xilinx UNISIM (`FDRE.v` uses Verilog-1995 `deassign`); the
  gate-level path is **xsim only**. Behavioral RTL runs fine under Verilator via
  `VtaPostSynthTbSpec` if you only need the control baseline.
