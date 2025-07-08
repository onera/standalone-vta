# standalone_vta

A maintained, unified, and extended Versatile Tensor Accelerator (VTA) ecosystem.

## Overview

This repository addresses the limitations of the original VTA project by providing:

*   **Active Maintenance:** An up-to-date and maintained VTA codebase.
*   **Unified Simulation:** A consistent input format (raw binary files) for both functional (C++) and cycle-accurate (CHISEL) simulators.
*   **Extended Cycle-Accurate Simulation:** Enriched cycle-accurate simulation with multiple test cases for different submodules.
*   **Standalone Compiler:** An open-source, TVM-independent compiler for generating VTA binaries.

This project aims to improve the VTA's usability and applicability, particularly in safety-critical systems like aeronautics.  The VTA is an open-source hardware accelerator designed to efficiently execute matrix multiplications, a core operation in Convolutional Neural Networks (CNNs).

## Repository Structure

*   `tutorials/` : Contains a Jupyter tutorial in two parts explaining and illustrating the use of the VTA compiler. (Temporary) It can be accessed here : https://mybinder.org/v2/gh/onera/standalone-vta/1a13d1d6aae5d06c3a12f96612cbc5c0d8a89f38?urlpath=lab%2Ftree%2FDocumentation%2Fcompiler_doc.ipynb
*   `compiler/`: Contains the standalone VTA compiler, data definition, and operation definition tools.
    *   `data_definition/`: Tools for generating binary data to be executed by the VTA.
    *   `operations_definition/`: Tools for generating VTA instructions.
*   `simulators/`: Contains the VTA simulators.
    *   `functional_simulator/`: A C++ simulator that models the functional behaviour of the VTA.
    *   `cycle_accurate_simulator/`: A cycle-accurate hardware description using CHISEL, along with simulation testbenches.
        * `src/main/scala/core/`: The hardware description of the VTA.
        * `src/test/scala/simulator/`: The cycle-accurate simulator with different level of simulation (e.g., TensorAlu, Compute module, TensorGemm). The cycle-accurate simulator uses JSON files located in `src/test/scala/resources/`.
        * `src/test/scala/formal/`: The formal verification of the VTA hardware description using chiseltest.
*   `Makefile`: To execute examples including compilation and simulation. The command `make list` give the list of the possible filename, then `make FILENAME=<filename>` enables to run an example. For example:
    ```
    make FILENAME=lenet5_layer1
    ```
    The result of the execution will be stored in `simulators_output/` and named `fsim_report.txt`.


## Getting Started

To get started with this repository, follow these steps:

1.  **Clone the repository:**
    ```
    git clone https://github.com/onera/standalone-vta.git
    cd standalone_vta
    ```
2.  **Explore the subprojects:** Refer to the individual `README.md` files within each subdirectory (`compiler/`, `simulators/`) for detailed instructions on building, running, and using the specific tools and simulators.


