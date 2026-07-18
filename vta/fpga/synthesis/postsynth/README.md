# Post-synthesis gate-level simulation (xsim)

Run the synthesized **`VTAXilinxShell` netlist** through a self-driving multi-layer testbench
and compare its OUT to the fsim golden. This verifies that the gate-level netlist computes the
same result as the behavioral RTL: a functional (output-correctness) check of synthesis,
**offline, without a board**.

`VTAXilinxShell` is the board-faithful top (active-low `ap_rst_n` + Xilinx AXI shims), the same
module the FPGA IP flow packages, so the netlist matches what is synthesized for hardware.
`funcsim` (mode=synth) has **no SDF / zero delay**, so any divergence it shows is a
**synthesis logic** difference (gates != RTL), not timing. That is the whole point of the flow:
it isolates synthesis-level miscompiles from place-and-route / timing effects.

## Pieces

The orchestration is Scala, run through Mill from the repo root (the former
`synth_netlist.sh` / `run_xsim.sh` / `compare_out.py` scripts have been removed). The Vivado
recipe and the xsim TB wrapper are classpath resources under
`vta/fpga/src/main/resources/synthesis/`, extracted at run time.

| piece | role |
| ----- | ---- |
| `resources/synthesis/ooc_netlist.tcl` | OOC synth/impl recipe -> `<top>_funcsim.v` (mode=synth) or `+timesim.v`+`.sdf` (mode=impl) |
| `fpga.synthesis.OocNetlist` (`./mill vta.fpga.oocNetlist`) | renders `ooc_params.tcl` from `boards/<board>.json` and runs the recipe |
| `resources/synthesis/sim_top.sv` | xsim wrapper: clock/reset, `io_dbgW` write-snoop -> `writes.log`, DONE/WEDGE/TIMEOUT |
| `fpga.synthesis.RunXsim` (`./mill vta.fpga.runXsim`) | compiles + runs xsim, `--behavioral` (control) or `--netlist <funcsim.v>` (DUT) |
| `fpga.synthesis.CompareOut` (`./mill vta.fpga.compareOut`) | strb-aware OUT compare vs `simulators_output/output<layer>.bin` |

The Chisel side (`VTAPostSynthTb`, `CompilerOutputLayout`, `VtaHostDriver`) and the shell/TB
emitters (`DebugXilinxConfigEmitter`, `DefaultPynqConfigTbEmitter`) live in `vta/hardware`.

## Runbook

Prereq: `source <Xilinx>/2025.2/Vivado/settings64.sh`.

### One-shot (chained)

`examples[<model>,<config>].postSynth` runs the whole chain (compile the model, dump the fsim
goldens, emit the shell + TB, OOC-synth, xsim behavioral + netlist, compare) into its task dest.
The board comes from `-Dvta.board.name` (default zcu104); the argument is the layer subset:

```bash
pixi run ./mill -Dvta.board.name=zcu104 \
  "examples[lenet5,vta_config].postSynth" QLinearConv1,MaxPool2,QLinearConv3
```

### By hand (per stage, from the repo root)

```bash
# 1. compile model + fsim golden + per-layer INP/ACC/OUT dumps
pixi run make -C examples compile_and_run CONFIG_FILE=vta_config.json ONNX_FILE=onnx/lenet5.onnx
( cd vta/simulator && ./build/fsim --dump-layers )      # -> simulators_output/{input,output}<layer>.bin

# 2. emit the board-faithful shell (the synth input) and the xsim TB (+ per-layer .mem)
pixi run ./mill -Dvta.config.file=vta_config.json vta.hardware.runMain vta.exporters.DebugXilinxConfigEmitter
pixi run ./mill -Dvta.config.file=vta_config.json -Dvta.layers=QLinearConv1,MaxPool2,QLinearConv3 \
  vta.hardware.emitVtaPostSynthTb

# 3. OOC-synthesize the gate-level netlist of VTAXilinxShell (minutes)
pixi run ./mill vta.fpga.oocNetlist --board zcu104 \
  --sv-dir build/emitted/vta-debug-xilinx-shell --top VTAXilinxShell \
  --out build/postsynth/vta_config-zcu104/ooc-netlist

# 4. behavioral control vs gate-level funcsim (both should reach SIM_TOP: DONE)
pixi run ./mill vta.fpga.runXsim --behavioral \
  --tb build/emitted/vta-postsynth-tb \
  --out build/postsynth/vta_config-zcu104/xsim-behav --layers 3
pixi run ./mill vta.fpga.runXsim \
  --netlist build/postsynth/vta_config-zcu104/ooc-netlist/VTAXilinxShell_funcsim.v \
  --tb build/emitted/vta-postsynth-tb \
  --out build/postsynth/vta_config-zcu104/xsim-net --layers 3

# 5. strb-aware OUT compare (for the runs that reach DONE)
pixi run ./mill vta.fpga.compareOut \
  --writes build/postsynth/vta_config-zcu104/xsim-net/writes.log \
  --layers QLinearConv1,MaxPool2,QLinearConv3 \
  --compiler-out compiler_output --golden-dir simulators_output
```

Expected for a faithful netlist: both `xsim-behav/sim.log` and `xsim-net/sim.log` reach
`SIM_TOP: DONE`, and the two `writes.log` files are byte-identical (gates == RTL). A
`SIM_TOP: WEDGE (driver watchdog) ...` (a layer that did not finish within the per-layer timeout)
or a `writes.log` divergence on the **netlist** leg while the **behavioral** leg is clean flags a
synthesis-level issue to investigate.

## Notes

- Gate-level funcsim is slow in wallclock and memory-hungry (the netlist links full Xilinx
  UNISIM). Lower `RunXsim --timeout-ns` to bound the watchdog; raise it if a healthy layer is
  being cut off.
- `CompareOut` compares the **whole** OUT buffer, including block-padding lanes. For a layer
  whose output-channel count is not a multiple of the block size (e.g. lenet5 `QLinearConv1` has
  6 channels in a block of 16), the hardware leaves the padding lanes non-zero while the fsim
  golden zeroes them, so those lanes show as mismatches even though the valid channels are
  byte-exact. The next layer ignores the padding, so this is benign; cross-check the valid lanes
  (or pick a layer whose channel count fills the block, like `QLinearConv3`) when a conv layer
  reports a partial mismatch.
- `--mode impl` (on `oocNetlist`) adds place&route + `VTAXilinxShell_timesim.v` + `.sdf` for a
  timing sim. `--mode synth` is the default and catches synthesis-logic differences without timing.
- The gate-level path is **xsim only**: Verilator cannot build stock Xilinx UNISIM (`FDRE.v` uses
  Verilog-1995 `deassign`). The behavioral control leg is `runXsim --behavioral` (also xsim); it
  shares the same TB and `writes.log` format, so it is the reference both legs are compared to.
