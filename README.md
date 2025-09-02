# standalone_vta

A maintained, unified, and extended Versatile Tensor Accelerator (VTA) ecosystem.

## Overview

This repository addresses the limitations of the original VTA project by providing:

*   **Unified Simulation:** A consistent input format (raw binary files) for both functional (C++) and cycle-accurate (CHISEL) simulators.
*   **Extended Cycle-Accurate Simulation:** Enriched cycle-accurate simulation with multiple test cases for different submodules.
*   **Standalone Compiler:** An open-source, TVM-independent compiler for generating VTA binaries.

This project aims to improve the VTA's usability and applicability, particularly in safety-critical systems like aeronautics.  The VTA is an open-source hardware accelerator designed to efficiently execute matrix multiplications, a core operation in Convolutional Neural Networks (CNNs).

## Repository Structure

*   `tutorials/` : Contains a Jupyter tutorial in two parts explaining and illustrating the use of the VTA compiler.
*   `src/`: Contains the source code of the project.
    *   `compiler/`: Contains the VTA compiler that generates the binaries from JSON file.
    *   `simulators/`: Both functional (C++) and cycle-accurate (CHISEL) simulators.
*   `examples/`: The examples to run. 
    *   `Makefile`: Use `make help`to get the different examples to run.
*   `config/vta_config.json`: The JSON file that defines the VTA hardware parameters.
*   `environment_setup\standalone-vta.yml`: The file to setup the conda environment for executing the project.


## Getting Started

To get started with this repository, follow these steps:

1.  **Clone the repository:**
    ```
    git clone https://github.com/onera/standalone-vta.git
    cd standalone_vta
    ```
2.  **Run the examples:**
    ```
    cd examples
    make help
    make matrix_16x16
    ```
    It results in two folders: `compiler_output/` and `simulators_output`.


