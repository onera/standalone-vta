# Post-synthesis gate-level simulation (xsim)

Run the synthesized **`VTAXilinxShell` netlist** through a self-driving multi-layer testbench
and compare its OUT to the fsim golden. This verifies that the gate-level netlist computes the
same result as the behavioral RTL — a functional (output-correctness) check of synthesis,
**offline, without a board**.

`VTAXilinxShell` is the board-faithful top (active-low `ap_rst_n` + Xilinx AXI shims), the same
module the FPGA IP flow packages, so the netlist matches what is synthesized for hardware.
`funcsim` (mode=synth) has **no SDF / zero delay**, so any divergence it shows is a
**synthesis logic** difference (gates ≠ RTL), not timing. That is the whole point of the flow:
it isolates synthesis-level miscompiles from place-and-route / timing effects.

## Pieces (all committed here)

| file                 | role                                                                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `../ooc_netlist.tcl` | OOC synth/impl of the chosen `--top` (here `VTAXilinxShell`) → `VTAXilinxShell_funcsim.v` (mode=synth) or `+timesim.v`+`.sdf` (mode=impl) |
| `synth_netlist.sh`   | generates `ooc_params.tcl` from `boards/<board>.json` and runs `ooc_netlist.tcl`                                                          |
| `sim_top.sv`         | xsim wrapper: clock/reset, `io_dbgW` write-snoop → `writes.log`, DONE/WEDGE/TIMEOUT                                                       |
| `run_xsim.sh`        | compiles + runs xsim, `--behavioral` (control) or `--netlist <funcsim.v>` (DUT)                                                           |
| `compare_out.py`     | strb-aware OUT compare vs `simulators_output/output<layer>.bin`                                                                           |

The Chisel side (`VTAPostSynthTb`, `CompilerOutputLayout`, `VtaHostDriver`) and the Mill emit
tasks live in `src/simulators/cycle_accurate_simulator`.

## Per-run output layout (kept isolated so runs never clobber)

```
src/fpga/synthesis/build/postsynth/<config>-<board>/
  ooc-netlist/   VTAXilinxShell_funcsim.v, post_synth.dcp, ooc_params.tcl, vivado.log
  xsim-net/      writes.log, sim.log         (gate-level run)
  xsim-behav/    writes.log, sim.log         (behavioral control run)
```

`build/` is gitignored. One dir per `<config>-<board>`; never share `writes.log` across runs.

## Runbook (worked example: default config, ZCU104, lenet5)

Prereqs: `source ~/Xilinx/2025.2/Vivado/settings64.sh` and the compiler venv
(`standalone-vta/src/compiler/.venv`).

```bash
REPO=$(git rev-parse --show-toplevel)
CFG=vta_config.json ; BOARD=zcu104
LAYERS=QLinearConv1,MaxPool2,QLinearConv3          # any subset of the model's layers
RUN=$REPO/src/fpga/synthesis/build/postsynth/${CFG%.json}-$BOARD
CAS=$REPO/src/simulators/cycle_accurate_simulator
POST=$REPO/src/fpga/synthesis/postsynth

# 1. compile model + fsim golden + per-layer INP/ACC/OUT dumps
cd $REPO/examples && source $REPO/src/compiler/.venv/bin/activate
make compile_and_run CONFIG_FILE=$CFG ONNX_FILE=onnx/lenet5.onnx        # CONFIG_FILE is the bare filename
( cd $REPO/src/simulators/functional_simulator && ./build/fsim --dump-layers )   # -> simulators_output/{input,output}<layer>.bin

# 2. emit the board-faithful shell (the synth input) and the xsim TB (+ per-layer .mem).
#    The TB instantiates VTAXilinxShell, so the netlist must be of VTAXilinxShell.
cd $CAS
./mill -Dvta.config.file=$CFG runMain vta.DebugXilinxConfig                       # -> build/emitted/vta-debug-xilinx-shell/VTAXilinxShell.sv
./mill -Dvta.config.file=$CFG -Dvta.layers=$LAYERS -Dvta.perLayerTimeout=2000000 emitVtaPostSynthTb

# 3. OOC-synthesize the gate-level netlist of VTAXilinxShell (minutes)
bash $POST/synth_netlist.sh --board $BOARD \
     --sv-dir $CAS/build/emitted/vta-debug-xilinx-shell \
     --top VTAXilinxShell --clk-port ap_clk \
     --out $RUN/ooc-netlist --mode synth

# 4. behavioral control vs gate-level funcsim (both should reach SIM_TOP: DONE)
bash $POST/run_xsim.sh --behavioral                                  --out $RUN/xsim-behav --layers 3
bash $POST/run_xsim.sh --netlist $RUN/ooc-netlist/VTAXilinxShell_funcsim.v --out $RUN/xsim-net --layers 3

# 5. strb-aware OUT compare (for the runs that reach DONE)
python3 $POST/compare_out.py --writes $RUN/xsim-net/writes.log --layers $LAYERS \
   --compiler-out $REPO/compiler_output --golden-dir $REPO/simulators_output
```

Expected for a faithful netlist: both `xsim-behav/sim.log` and `xsim-net/sim.log` reach
`SIM_TOP: DONE`, and the two `writes.log` files are byte-identical (gates == RTL). A
`SIM_TOP: WEDGE (driver watchdog) …` (a layer that did not finish within `perLayerTimeout`) or
a `writes.log` divergence on the **netlist** leg while the **behavioral** leg is clean flags a
synthesis-level issue to investigate.

## Notes

- Gate-level funcsim is slow in wallclock and memory-hungry (the netlist links full Xilinx
  UNISIM). Lower `-Dvta.perLayerTimeout` to bound a watchdog timeout (the watchdog counts
  **sim cycles**); raise it if a healthy layer is being cut off.
- `compare_out.py` compares the **whole** OUT buffer, including block-padding lanes. For a layer
  whose output-channel count is not a multiple of the block size (e.g. lenet5 `QLinearConv1` has
  6 channels in a block of 16), the hardware leaves the 10 padding lanes non-zero while the fsim
  golden zeroes them, so those lanes show as mismatches even though the valid channels are
  byte-exact. The next layer ignores the padding, so this is benign; cross-check the valid lanes
  (or pick a layer whose channel count fills the block, like `QLinearConv3`) when a conv layer
  reports a partial mismatch.
- `mode=impl` adds place&route + `VTAXilinxShell_timesim.v` + `.sdf` for a timing sim. `mode=synth`
  is the default and catches synthesis-logic differences without timing.
- The gate-level path is **xsim only**: Verilator cannot build stock Xilinx UNISIM (`FDRE.v` uses
  Verilog-1995 `deassign`). The behavioral control leg is `run_xsim.sh --behavioral` (also xsim);
  it shares the same TB and `writes.log` format, so it is the reference both legs are compared to.
