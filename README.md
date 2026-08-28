# STANDALONE-VTA

A maintained, unified, and extended Versatile Tensor Accelerator (VTA) ecosystem.

## Overview

This repository addresses the limitations of the original VTA project by providing:

- **Standalone Compiler:** An open-source, TVM-independent compiler for generating VTA binaries from JSON/ONNX representations.
- **Unified Simulation:** A consistent input format (raw binary files) for both functional (C++) and cycle-accurate (CHISEL) simulators.
- **Extended Cycle-Accurate Simulation:** Enriched cycle-accurate simulation with multiple test cases for different submodules.
- **FPGA Implementation:** A one-command Vivado flow from the same Chisel sources to a bitstream and XSA for several Xilinx boards, with a baremetal ARM runtime that executes the same binaries on hardware.

This project aims to improve VTA's usability and applicability, particularly in safety-critical systems like aeronautics. VTA is an open-source hardware accelerator designed to efficiently execute matrix multiplications, a core operation in Convolutional Neural Networks (CNNs).

## Architecture & System Flow

The `standalone-vta` ecosystem is designed with a clear separation of concerns:
one compiler front-end feeding three interchangeable execution back-ends (a fast
C++ model, the real Chisel RTL, and silicon on an FPGA), all parameterized by a
single hardware configuration file.

```mermaid
flowchart TB
    subgraph inputs ["Inputs"]
        onnx["ONNX model<br/>examples/onnx/*.onnx"]
        ir["Raw VTA IR fixture<br/>examples/vta_ir/*.json"]
        cfg[("VTA hardware configuration<br/>config/NAME.json")]
    end

    subgraph comp ["modules/compiler - Python, TVM-free"]
        nnc["NN compiler<br/>qONNX to VTA IR<br/>+ per-node CPU params"]
        vtac["VTA compiler<br/>partitioning, DRAM allocation,<br/>ISA encoding"]
        nnc --> vtac
    end

    art["VTA binaries"]

    subgraph hw ["modules/hardware - Chisel"]
        rtl["VTA RTL"]
        catest["Cycle-accurate<br/>ScalaTest"]
        sv["Emitted<br/>SystemVerilog"]
        rtl --> catest
        rtl --> sv
    end

    subgraph simg ["modules/simulator - C++"]
        fsim["fsim - FunctionalDevice<br/>behavioral C++ model"]
        vsim["vsim - VerilatedDevice<br/>Verilator + DPI over the real RTL"]
    end

    subgraph fpga ["modules/fpga"]
        synth["synthesis - Vivado<br/>IP packaging, bitstream, XSA"]
        bmgen["software - baremetal codegen<br/>run_nn steps + Vitis apps"]
    end

    board(["FPGA board<br/>zcu104, vek280, vck190"])

    ref["ONNX reference<br/>input_nn.bin + reference.bin"]
    check{{"check<br/>against reference.bin, or fsim vs vsim"}}

    onnx --> nnc
    onnx --> ref
    art -.-> ref
    ir --> vtac
    vtac --> art

    cfg -.-> comp
    cfg -.-> hw
    cfg -.-> simg
    cfg -.-> fpga

    art --> fsim
    art --> vsim
    art --> bmgen
    sv --> vsim
    sv --> synth
    synth --> board
    bmgen --> board

    fsim --> check
    vsim --> check
    board --> check
    ref --> check


    classDef input fill:#eef1f5,stroke:#7a8698,stroke-width:1px,color:#1e2733
    classDef step fill:#ffffff,stroke:#7a8698,stroke-width:1px,color:#1e2733
    classDef data fill:#dde6f4,stroke:#3d6299,stroke-width:1.5px,color:#122744
    classDef result fill:#eef1f5,stroke:#3d6299,stroke-width:1.5px,color:#122744

    class onnx,ir,cfg input
    class nnc,vtac,rtl,catest,fsim,vsim,synth,bmgen step
    class art,ref,sv data
    class board,check result

    style inputs fill:none,stroke:#aab3c0,stroke-dasharray:4 4
    style comp fill:none,stroke:#aab3c0
    style hw fill:none,stroke:#aab3c0
    style simg fill:none,stroke:#aab3c0
    style fpga fill:none,stroke:#aab3c0
```

Three things the diagram does not show:

- **`config/<name>.json` is the single source of truth.** The same file
  parameterizes the compiler, the generated C++ config header, the Chisel
  elaboration and the synthesized bitstream, and all four must agree. Mill
  enforces that by construction, since the config is a cross key rather than a
  flag (the exception is importing a pre-built XSA, which it cannot check).
- **The instruction and micro-op streams are the contract.** The compiler
  encodes them, the Chisel RTL and the C++ model decode them, and the PS
  software copies them verbatim. Their bit layout is fixed by the ISA and must
  match across all three.
- **All three back-ends run the same binaries.** `fsim` is the fast check,
  `vsim` runs them through the real RTL under Verilator, and the board runs them
  on silicon. ONNX models also get a golden output from ONNX Runtime to check
  against; the raw IR fixtures have no golden, so `fsim` is compared to `vsim`
  instead.

## Repository Map

| Path                                              | What it is                                                                                            | Docs                                                                             |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `modules/compiler/`                               | ONNX or VTA IR to VTA binaries. Python, TVM-independent.                                              | [readme](modules/compiler/README.md)                                             |
| `modules/simulator/`                              | `fsim` (C++ model) and `vsim` (Verilator + DPI over the RTL).                                         | [readme](modules/simulator/README.md)                                            |
| `modules/hardware/`                               | Chisel RTL: the cycle-accurate tests, and the SystemVerilog emitted for `vsim` and the FPGA.          | [readme](modules/hardware/README.md)                                             |
| `modules/fpga/`                                   | Vivado synthesis and the ARM PS baremetal runtime.                                                    | [synthesis](modules/fpga/README.md), [software](modules/fpga/software/README.md) |
| `config/`                                         | Hardware parameters: `vta_config.json` and alternatives.                                              | [readme](config/README.md)                                                       |
| `examples/`                                       | `onnx/` models and `vta_ir/` fixtures, the axes the pipelines are crossed over.                       |                                                                                  |
| `tutorials/`                                      | Notebooks walking through the compiler internals.                                                     | [readme](tutorials/README.md)                                                    |
| `Makefile`, `build.mill`, `modules/pipeline.mill` | The build: a `make` front end over Mill, the cross keys, and the per-(model, config) pipeline traits. | [MILL.md](MILL.md)                                                               |
| `out/`                                            | Mill's output tree, one directory per task.                                                           |                                                                                  |

Each module is addressable as a Mill module (`modules.compiler`,
`modules.simulator`, ...). The `compiler_output/`, `reference_output/`,
`simulators_output/` and `log_output/` directories only appear when driving the
per-module Makefiles instead of Mill; everything Mill builds lands in `out/`.

Going deeper on the hardware: [test documentation](modules/hardware/src/test/documentation/test_documentation.md),
[testbench](modules/hardware/src/test/scala/simulatorTest/README.md),
[formal verification](modules/hardware/src/test/scala/formal/README.md).

## Getting Started

### 1. Setup

The only prerequisite is [Pixi](https://pixi.prefix.dev/latest/installation/),
which pins the whole toolchain:

```bash
git clone https://github.com/onera/standalone-vta.git
cd standalone-vta
pixi shell
```

The FPGA flows additionally need Vivado/Vitis 2025.2 on the host
([setup guide](https://toulouse-embedded-accel.github.io/HEAT/quickstarts/vitis-toolchain-setup/)),
sourced before use, plus a license for Versal boards:

```bash
source /opt/Xilinx/Vitis/2025.2/settings64.sh
export XILINXD_LICENSE_FILE=<port>@<server>   # or path/to/license.lic
```

<details>
<summary>Behind a corporate proxy</summary>

```bash
export http_proxy="http://<PROXY_HOST>:<PORT>"
export https_proxy="http://<PROXY_HOST>:<PORT>"
export JAVA_TOOL_OPTIONS="-Dhttp.proxyHost=<PROXY_HOST> -Dhttp.proxyPort=<PORT> -Dhttps.proxyHost=<PROXY_HOST> -Dhttps.proxyPort=<PORT>"
```

</details>

### 2. Quickstart

The root `Makefile` wraps the Mill build, so a first run needs no knowledge of
Mill. Run it from the repository root, inside the Pixi environment.

```bash
make            # or `make help`: list every target and the current settings
```

| Target            | What it does                                                                            |
| ----------------- | --------------------------------------------------------------------------------------- |
| `make compile`    | Compile the ONNX model to VTA binaries (`nn_compiler` + `vta_compiler`).                |
| `make fsim`       | Run the functional (C++) simulation and check it against the ONNX reference.            |
| `make vsim`       | Run the cycle-accurate (Verilated RTL) simulation and check it the same way.            |
| `make synthesis`  | Run the Vivado synthesis for the target board (bitstream + XSA).                        |
| `make baremetal`  | Create the Vitis workspace with the baremetal applications.                             |
| `make inspect`    | Show every task available for the current model and config, with its description.       |
| `make check_onnx` | Run every model in `examples/onnx/` through the functional simulation, on `vta_config`. |
| `make check_irs`  | Run every raw VTA IR fixture through both simulators and compare them.                  |
| `make tests`      | Run the Chisel, synthesis and baremetal-codegen test suites (slow, ~20 min).            |

Each target compiles whatever it depends on if it is stale, so `make fsim` on a
fresh clone compiles the model first. A typical first run:

```bash
make fsim     # the default model and config, functional simulation
make vsim     # the same model through the Chisel RTL
```

Four variables select what is being built:

| Variable   | Default                            | Meaning                                                                  |
| ---------- | ---------------------------------- | ------------------------------------------------------------------------ |
| `ONNX`     | `examples/onnx/qyolo_pattern.onnx` | The ONNX model to compile and run. Its basename is a cache key.          |
| `CONFIG`   | `vta_config`                       | The hardware configuration, from `config/<CONFIG>.json`.                 |
| `BOARD`    | `zcu104`                           | The FPGA board, from `modules/fpga/boards/<BOARD>.json`.                 |
| `DDR_BASE` | `0x100000`                         | DDR base address baked into the baremetal codegen. Must match the board. |

```bash
make CONFIG=vta_w8b fsim
make ONNX=examples/onnx/qyolo.onnx CONFIG=vta_w8b vsim
make BOARD=vek280 CONFIG=vta_w8b synthesis
```

`make baremetal` additionally takes `RUNNER` (default `run_nn run_nn_uart`) and
`DATA_LOADER` (default `elf sd`), which choose the baremetal applications and
how the model data reaches DDR:

```bash
make RUNNER=run_nn DATA_LOADER=tcl baremetal
```

The available values are read from the filesystem: any `.onnx` under
`examples/onnx/` (or anywhere else - `ONNX` takes any path), any
`config/*.json`, any `modules/fpga/boards/*.json`.

Artifacts are cached per (model, config) and per (config, board), so switching
any of the three never rebuilds what the others produced, and switching back
finds the earlier results. Only one model is addressable at a time; building
several in one command needs the Mill entry points in [MILL.md](MILL.md).

To drop the cached artifacts:

```bash
make clean          # the current (model, config) run artifacts only
make cleaner        # every model's, every config's (the whole out/run tree)
make clean-target   # this (config, board) FPGA cache
```

### 3. Going further

The Makefile covers one model through the default pipeline. Everything else -
several models or configs side by side, the raw VTA IR fixtures, the individual
FPGA and Vitis tasks, the on-board runners, the post-synthesis gate-level check
and the Chisel test suites - is driven with `./mill` and documented in
[MILL.md](MILL.md).
