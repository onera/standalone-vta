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
|  (ONNX or custom JSON)| ---> |       (src/compiler/)     | ---> |        (src/simulators/)      |
|                       |      |  Parses, partitions, and  |      | Functional (C++) for fast val |
|                       |      |  generates instructions.  |      | Cycle-Accurate (Chisel) for HW|
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

1. **Compiler Phase**: The standalone Python compiler (`src/compiler`) reads a neural network representation (ONNX or a custom JSON VTA IR). It performs matrix partitioning, DRAM allocation, and generates VTA-specific instructions and micro-ops.
2. **Artifact Generation**: The compiler outputs binary files (`.bin`) and memory initialization files (`.json`) into the `compiler_output/` directory.
3. **Simulation Phase**: The simulators (`src/simulators`) read these artifacts to simulate the VTA execution, validating the compiler's output either functionally or cycle-accurately.

## Repository Map

- `src/`: Core source code.
    - `compiler/`: Python-based VTA compiler (TVM-independent).
    - `simulators/`: VTA Simulators.
        - `functional_simulator/`: Fast C++ functional simulator.
        - `cycle_accurate_simulator/`: Detailed Chisel-based hardware simulator.
- `config/`: Contains `vta_config.json` defining the VTA hardware parameters. See [Config Documentation](config/README.md).
- `environment_setup/`: Dockerfile and Conda environments. See [Setup Documentation](environment_setup/README.md).
- `examples/`: Makefiles and sample networks to compile and simulate.
- `tutorials/`: Jupyter notebooks detailing the compiler components.
- `compiler_output/` & `simulators_output/`: Default directories for generated artifacts and simulation results.

## Documentation Index

Explore the detailed documentation for each component of the `standalone-vta` ecosystem:

- **Root Documentation**
    - [Project Overview & Quickstart](README.md)
    - [Configuration (`vta_config.json`)](config/README.md)
    - [Environment Setup (Docker/Conda)](environment_setup/README.md)

- **Compiler (`src/compiler/`)**
    - [Standalone VTA Compiler](src/compiler/README.md)
    - [VTA Instructions & Operations Definition](src/compiler/vta_compiler/operations_definition/README.md)

- **Simulators (`src/simulators/`)**
    - [Simulators Architecture Overview](src/simulators/README.md)
    - [Functional Simulator (C++)](src/simulators/functional_simulator/README.md)
    - [Cycle-Accurate Simulator (Chisel)](src/simulators/cycle_accurate_simulator/README.md)
        - [Simulator Test Documentation](src/simulators/cycle_accurate_simulator/src/test/documentation/test_documentation.md)
        - [Simulator Testbench README](src/simulators/cycle_accurate_simulator/src/test/scala/simulatorTest/README.md)
        - [Formal Verification README](src/simulators/cycle_accurate_simulator/src/test/scala/formal/README.md)

- **Hardware & FPGA**
  - [FPGA Implementation & IP Generation](src/fpga/README.md)
  - [FPGA Runtime Software](src/fpga/software/README.md)
- **Tutorials**
    - [Tutorials Overview](tutorials/README.md)

## Getting Started

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/onera/standalone-vta.git
cd standalone-vta
```

It is highly recommended to use the [provided Docker environment](environment_setup/README.md) to ensure all dependencies (Python, C++, Java/Scala) are correctly installed.

### 2. Run an Example

Once inside the environment, you can use the `examples/Makefile` to run full end-to-end flows (Compiler -> Functional Simulator).

```bash
cd examples
# View available targets
make help

# Run a simple 16x16 matrix multiplication example
make matrix_16x16
```

This will:
1. Run the compiler, placing binaries in `../compiler_output/`.
2. Run the functional simulator, reading those binaries and placing logs in `../simulators_output/`.
