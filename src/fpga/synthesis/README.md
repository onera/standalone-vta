# VTA FPGA synthesis

One-command, config- and board-parameterized synthesis: from a VTA hardware config
and a board definition down to a bitstream and an XSA, with no manual Vivado steps.

```
config.json + boards/<board>.json
  -> (mill)   emit Xilinx-shell RTL + package_ip.tcl      [stage 1]
  -> (vivado) package RTL as an IP-XACT IP (ip_repo/)     [stage 2]
  -> (vivado) block design -> synth -> impl -> bitstream
              -> XSA                                       [stage 3]
  -> build/vta_<board>.xsa  (+ .bit, reports, manifest.json)
```

## Quick start

```sh
source <Xilinx>/2025.2/Vivado/settings64.sh          # Vivado on PATH

make bitstream BOARD=zcu104 CONFIG=../../../config/vta_config.json
# or, equivalently:
python build_fpga.py --board zcu104 --config ../../../config/vta_config.json
```

The XSA lands in `build/vta_zcu104.xsa`. Feed it straight to the software half:

```sh
make -C ../software workspace XSA=$(pwd)/build/vta_zcu104.xsa CPU=psu_cortexa53_0
```

Useful flags:

- `make dry-run BOARD=zcu104` - print the plan and the generated `board_params.tcl`,
  run nothing (works without Xilinx tools installed).
- `make bitstream SKIP_EMIT=1` - reuse RTL already emitted under the emit dir.
- `make bitstream JOBS=8` - parallelism for synth/impl.
- `python build_fpga.py --help` - all options.

## Files

| File | Role |
|------|------|
| `build_fpga.py` | Orchestrator: runs the 3 stages, derives the IP VLNV from the emit, writes `manifest.json`. Styled on `../software/host/create_vitis_workspace.py`. |
| `build_fpga.tcl` | Board-agnostic Vivado recipe. Builds the block design, assigns addresses, runs to bitstream, exports the XSA. Parameterized entirely by a generated `board_params.tcl`. |
| `boards/<board>.json` | The only place board specifics live: part, board preset, CPU, PL clock, AXI port wiring, address map. |
| `Makefile` | Thin `make bitstream` / `dry-run` / `clean` entry. |
| `legacy/vta_zcu104.tcl` | The old 919-line `write_project_tcl` GUI dump, kept for reference. See below. |

## Adding a board

Copy an existing board JSON and change `part` / `board_part` / `cpu` / clock and
the `ps_*` / `ports` fields. A worked example ships here:

- `boards/zcu104.json` - Zynq UltraScale+ (`zynq_ultra_ps_e`), board files shipped
  with Vivado.

The AXI topology (master -> SmartConnect -> slave) and `build_fpga.tcl` stay
unchanged - a new board is a JSON file, not a script edit.

## Timing verdict

`write_bitstream` succeeds even when timing fails, so a bitstream alone is not proof
of a usable design. After implementation the flow reads the post-route timing summary,
records `timing_met` in `manifest.json`, and prints a loud warning if constraints are
not met. If you see `Timing: NOT MET`, lower `pl_clock_mhz` in the board JSON or move
to a larger/faster part before using the bitstream on hardware.

## Why this replaces `legacy/vta_zcu104.tcl`

The legacy file was a Vivado GUI export (`write_project_tcl`): 919 lines, hardcoded to
the ZCU104 part, ~270 lines of resolved `CONFIG.PSU__*` board preset, a frozen
block-design net snapshot, and ~260 lines of report boilerplate. It created the
synth/impl runs but never launched them, never wrote a bitstream, and never exported
an XSA - all of that was manual in the GUI. It also referenced a stale IP name
(`VTADefaultShell`); the current emit packages the IP as `onera:user:VTA:0.2.0`, which
the new flow reads from the emitted `package_ip.tcl` so it can never drift.

The new recipe wires the design by stable interface name and IP VLNV, so it does not
break when the RTL interface or the config changes. Keep `legacy/` until the new flow
is validated on real hardware, then remove it.
