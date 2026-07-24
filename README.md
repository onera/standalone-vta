# STANDALONE-VTA

A maintained, unified, and extended Versatile Tensor Accelerator (VTA) ecosystem.

## Overview

This repository addresses the limitations of the original VTA project by providing:

- **Unified Simulation:** A consistent input format (raw binary files) for both functional (C++) and cycle-accurate (CHISEL) simulators.
- **Extended Cycle-Accurate Simulation:** Enriched cycle-accurate simulation with multiple test cases for different submodules.
- **Standalone Compiler:** An open-source, TVM-independent compiler for generating VTA binaries from JSON/ONNX representations.

This project aims to improve VTA's usability and applicability, particularly in safety-critical systems like aeronautics. VTA is an open-source hardware accelerator designed to efficiently execute matrix multiplications, a core operation in Convolutional Neural Networks (CNNs).

## Architecture & System Flow

The `standalone-vta` ecosystem is designed with a clear separation of concerns, moving from high-level models to low-level hardware simulation.

```text
+-----------------------+      +---------------------------+      +-------------------------------+
|      Input Model      |      |   Standalone VTA Compiler |      |         VTA Simulators        |
|  (ONNX or custom JSON)| ---> |       (vta/compiler/)     | ---> |   Functional (C++) for fast   |
|                       |      |  Parses, partitions, and  |      |   validation (vta/simulator)  |
|                       |      |  generates instructions.  |      | Cycle-Accurate (vta/hardware) |
+-----------------------+      +---------------------------+      +-------------------------------+
                                             |                                  ^
                                             v                                  |
                                +-------------------------+                     |
                                |     Generated Artifacts |---------------------+
                                | - instructions.bin      |
                                | - uop.bin               |
                                | - input.bin / weight.bin|
                                | - dram_state.json       |
                                +-------------------------+
```

1. **Compiler Phase**: The standalone Python compiler (`vta/compiler`) reads a neural network representation (ONNX or a custom JSON VTA IR). It performs matrix partitioning, DRAM allocation, and generates VTA-specific instructions and micro-ops.
2. **Artifact Generation**: The compiler outputs binary files (`.bin`) and memory initialization files (`.json`) into the `compiler_output/` directory (or, when driven by Mill, into the task's own output directory under `out/`).
3. **Simulation Phase**: The simulators (`vta/simulator` for the functional and Verilated/DPI backends, `vta/hardware` for the Chisel cycle-accurate one) read these artifacts to simulate the VTA execution, validating the compiler's output either functionally or cycle-accurately.

## Repository Map

- `vta/`: Core source code, one directory per module. Each has its own
  `package.mill` and is addressable as a Mill module (`vta.compiler`,
  `vta.simulator`, ...).
  - `compiler/`: Python-based VTA compiler (TVM-independent).
  - `simulator/`: Fast C++ functional simulator (and the Verilated/DPI backend).
  - `hardware/`: Chisel hardware sources - the cycle-accurate simulator, and the SystemVerilog emitted for the Verilated and FPGA flows.
  - `fpga/`: FPGA synthesis flow and the PS-side baremetal runtime software.
- `build.mill`, `util.mill`: Root Mill build - the `examples` cross modules and the shared config plumbing.
- `config/`: Contains `vta_config.json` defining the VTA hardware parameters, plus alternative configurations. See [Config Documentation](config/README.md).
- `environment_setup/`: Legacy setup files (Docker/Conda). The project now uses Pixi for package and environment management.
- `examples/`: Makefiles and sample networks to compile and simulate.
- `tutorials/`: Jupyter notebooks detailing the compiler components.
- `out/`: Mill's output tree - each task writes into its own dest directory here.
- `compiler_output/`, `simulators_output/`, `log_output/`: Default directories for generated artifacts, simulation results and run logs when driving the flow through the Makefiles rather than Mill.

## Documentation Index

Explore the detailed documentation for each component of the `standalone-vta` ecosystem:

- **Root Documentation**
  - [Project Overview & Quickstart](README.md)
  - [Configuration (`vta_config.json`)](config/README.md)
  - [Environment Setup (Legacy Docker/Conda)](environment_setup/README.md)

- **Compiler (`vta/compiler/`)**
  - [Standalone VTA Compiler](vta/compiler/vta_compiler/operations_definition/README.md)

- **Simulator (`vta/simulator/`)**
  - [Functional Simulator (C++)](vta/simulator/README.md)
- **Hardware (`vta/hardware/`)**
  - [Hardware (Chisel)](vta/hardware/README.md)
  - [Simulator Test Documentation](vta/hardware/src/test/documentation/test_documentation.md)
  - [Simulator Testbench README](vta/hardware/src/test/scala/simulatorTest/README.md)
  - [Formal Verification README](vta/hardware/src/test/scala/formal/README.md)

- **FPGA (`vta/fpga/`)**
  - [FPGA Implementation & IP Generation](vta/fpga/README.md)
  - [FPGA Runtime Software](vta/fpga/software/README.md)
- **Tutorials**
  - [Tutorials Overview](tutorials/README.md)

## Getting Started

### 1. Prerequisites

Before setting up the environment, ensure you have the following installed on your host machine:

- **Pixi** installed on your host machine ([Installation Guide](https://pixi.prefix.dev/latest/installation/)).
- **Vivado/Vitis 2025.2** installed on your host machine (only required for FPGA synthesis/implementation). Refer to the [Vitis Toolchain Setup Guide](https://toulouse-embedded-accel.github.io/HEAT/quickstarts/vitis-toolchain-setup/) for toolchain installation details.

#### Working Behind a Corporate Proxy

If you are working behind a corporate proxy, make sure to export the proxy settings and JVM options:

```bash
export http_proxy="http://<PROXY_HOST>:<PORT>"
export https_proxy="http://<PROXY_HOST>:<PORT>"
export JAVA_TOOL_OPTIONS="-Dhttp.proxyHost=<PROXY_HOST> -Dhttp.proxyPort=<PORT> -Dhttps.proxyHost=<PROXY_HOST> -Dhttps.proxyPort=<PORT>"
```

### 2. Environment Setup

Clone the repository and activate the Pixi environment:

```bash
# Clone the repository
git clone https://github.com/onera/standalone-vta.git
cd standalone-vta

# Start the environment shell
pixi shell
```

#### Hardware Implementation

If you are using the hardware implementation, you need to source the Vitis 2025.2 settings script and optionally configure your Xilinx license (especially if targeting a Versal board):

```bash
# Source Vitis 2025.2 settings
source /opt/Xilinx/Vitis/2025.2/settings64.sh

# Configure Xilinx License (if required)
export XILINXD_LICENSE_FILE=<port>@<server> # or path/to/license.lic
```

### 3. Run an Example

Once inside the environment (after running `pixi shell`), Mill drives the
full flow (Compiler -> Functional Simulator -> check, plus FPGA baremetal
codegen and Vitis workspace creation) for each (model, config) pair - config
is a Cross axis alongside the model, like `examples[lenet5]` itself:

```bash
# Compile the model (nn_compiler + vta_compiler + ONNX reference) for a
# given config - config is a required second cross value, not a flag
./mill "examples[lenet5,vta_config].compile"

# Run the (already-compiled) sim + check: fsim -> check -> vsim -> check
./mill "examples[lenet5,vta_config].run"

# Same model, a different config - independent, cached, buildable together
./mill "examples[lenet5,vta_w8b].run"

# Generate the baremetal codegen for this model/config (needs no Vivado)
./mill "examples[lenet5,vta_config].genBaremetal"

# Create/update a Vitis workspace wired to that baremetal codegen and the
# config's synthesized bitstream (needs Vivado + Vitis)
./mill "examples[lenet5,vta_config].createVitisProject" --data-loader tcl
```

`run` never re-invokes the Python compiler itself - it depends on `compile`,
which only re-runs when the model, config, or compiler sources actually
change.

Outputs are isolated per model and config in each task's Mill dest under
`out/examples/<model>/<config>/`: `compile.dest/` (compile),
`genBaremetal.dest/` (genBaremetal), `createVitisProject.dest/<board>/`
(createVitisProject). The C++/Verilator simulator (`vta.simulator[<config>]`)
is built once per config and cached, and the FPGA bitstream once per
(config, board) pair (`vta.fpga.targets[<config>,<board>]`), so switching
config, board, or adding a new example model does not rebuild everything -
`./mill examples.runAll` builds every (model, config) pair in one invocation.

An FPGA build is identified by both its config (which fixes the RTL) and its
board (which fixes the pinout and XSA), so each pair is independently
addressable and cached - flipping between boards does not re-synthesize the
other one:

```bash
./mill "vta.fpga.targets[vta_w8b,zcu104].fpgaSynth"    # bitstream + XSA
./mill "vta.fpga.targets[vta_w8b,vek280].fpgaProject"  # Vivado project only

# examples pick their board from -Dvta.board.name (default zcu104)
./mill -Dvta.board.name=vek280 "examples[lenet5,vta_w8b].createVitisProject"
```

Boards are the JSONs under `vta/fpga/boards/` (`zcu104`, `vck190`, `vek280`);
adding one there adds the cross entries with no build-file edit. The older
`-Dvta.config.file=<name>.json` global
property still selects the config for the flat, non-crossed tasks
(`vta.hardware.emitVtaSimConfig`, `vta.fpga.buildFpga`, `vta.hardware.test.unittest`,
...) used by `examples/Makefile`, `vta/simulator/Makefile`, and
`vta/fpga/software/Makefile`, which remain available for standalone use
outside Mill.

#### Vitis workspace from an existing XSA

`createVitisProject` always goes through Vivado. When a suitable XSA already
exists (a colleague's build, a GUI-made design, an archived handoff), the
separate `createVitisProjectFromXsa` command skips synthesis entirely and hands
the file straight to `create_vitis_workspace.py`:

```bash
./mill "examples[lenet5,vta_config].createVitisProjectFromXsa" \
    --xsa vta_zcu104.xsa --runner run_nn --data-loader elf
```

The two commands share only the generated headers; nothing in this one's task
graph reaches Vivado. Mill fills in the workspace directory
(`build/vitis/<model>_<config>`, kept across runs so the platform is not
rebuilt), this model's `genBaremetal` output and the app-name prefix - repeat
any of those flags to override them, since the script keeps the last
occurrence. Everything else is yours, including `--cpu` for a non-ZynqMP board
(the script defaults to `psu_cortexa53_0`).

The XSA is *not* checked against the active config: a bitstream synthesized for
a different block size than the compiled binaries will run and produce garbage.

#### SD-card file set

`genBaremetal` always emits `nn_sd_manifest.h`, so `--data-loader sd` builds
with no extra step. It does not copy the `.bin` streams themselves, which would
bloat every cached gen dir - `sdCard` stages those:

```bash
./mill "examples[lenet5,vta_config].sdCard"
```

It prints the folder to copy to the root of a FAT32 card. Files land in a
per-model subfolder (`0:/lenet5/instructions_L0.bin`), so one card can hold
several models, and the codegen is deterministic, so the staged addresses match
the app built from `genBaremetal`.

`xilffs` (FatFs) is enabled when the platform is *created*, so a workspace built
before any SD app was requested cannot build one - point `--workspace` at a
fresh directory.

#### On-board isolation debugging

`run_nn_debug` and `run_nn_cpu_debug` check every layer on the board against the
fsim goldens instead of only the final output. That needs an fsim
`--dump-layers` run, a codegen wired to those dumps, and an app built with the
debug runner; `createVitisDebugProject` chains all three:

```bash
./mill "examples[lenet5,vta_config].createVitisDebugProject"
./mill "examples[lenet5,vta_config].createVitisDebugProject" --runner run_nn_cpu_debug
```

It defaults to `--runner run_nn_debug --data-loader elf` and shares the
workspace and platform of `createVitisProject`, so it synthesizes if the
bitstream is stale. The goldens (`layerDumps`) are cached and shared with
`postSynth`. For `--data-loader sd`, stage the card with `sdCardDebug` rather
than `sdCard`: the plain set carries no goldens, and a debug run without them
has nothing to compare against.

#### Pinning options between runs

Rather than repeating `-Dvta.*` flags on every invocation, persist them:

```bash
./mill configure vta.board.name=te0803 vta.ddr.base=0x10000000
```

This writes a generated, git-ignored `.mill-jvm-opts` at the repo root, which
applies from the next `./mill` invocation onwards. Later calls merge into it,
so options not mentioned are kept:

```bash
./mill configure                 # show the options in effect
./mill configure vta.ddr.base=   # drop one option, back to its default
./mill configure --reset         # drop all of them
```

A flag still wins for a single run: `./mill -Dvta.ddr.base=0xBEEF <task>`.

Do not hand-edit `.mill-jvm-opts`. It replaces (rather than adds to) the
`//| mill-jvm-opts` header of `build.mill`, so it has to carry
`-Dchisel.project.root`, which `configure` emits for you. Any other line you
put there, such as an `-Xmx` setting for the build JVM, is preserved across
`configure` runs, but `--reset` deletes the file and everything in it.

### 4. Tab Completion

`./mill <Tab>` can complete task names and show each task's description (its
`/** ... */` doc comment in the `*.mill` build files). Completion is a shell
hook that calls `mill --tab-complete` live on every keypress, so the candidate
list always matches the current build. Enable it once per clone by sourcing the
script for your shell (use your clone's path):

```bash
# bash / zsh - add to ~/.bashrc or ~/.zshrc
source /path/to/standalone-vta/tools/completions/mill-completion.sh

# fish - add to ~/.config/fish/config.fish
source /path/to/standalone-vta/tools/completions/mill-completion.fish
```

Restart the shell (or re-`source` the rc file) and press `<Tab>` after `./mill`.

If [`fzf`](https://github.com/junegunn/fzf) is installed (it ships in the pixi
env), `<Tab>` opens a drill-down picker instead of the plain menu: the full
description shows in a preview pane, `<Tab>` descends into a module's sub-tasks
(e.g. `examples` -> model -> config), `<Left>` goes back up, and `<Enter>`
accepts the highlighted path. Without fzf it falls back to a native single-line
menu. Both rely on the `mill-fzf-level` helper beside these scripts, so keep the
three `tools/completions/` files together.

Mill also ships an installer that writes the bash/zsh hook and edits your rc
files for you: `./mill mill.tabcomplete/install`.

A task shows a description only if it has a doc comment; add a `/** ... */`
above a `def ... = Task { ... }` to describe it.
