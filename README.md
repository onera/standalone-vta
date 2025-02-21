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

*   `compiler/`: Contains the standalone VTA compiler, data definition, and operation definition tools.
    *   `data_definition/`: Tools for generating binary data to be executed by the VTA.
    *   `operations_definition/`: Tools for generating VTA instructions.
*   `simulators/`: Contains the VTA simulators.
    *   `functional_simulator/`: A C++ simulator that models the functional behaviour of the VTA.
    *   `cycle_accurate_simulator/`: A cycle-accurate hardware description using CHISEL, along with simulation testbenches.

## Getting Started

To get started with this repository, follow these steps:

1.  **Clone the repository:**
    ```
    git clone https://github.com/your-username/standalone_vta.git
    cd standalone_vta
    ```
2.  **Explore the subprojects:** Refer to the individual `README.md` files within each subdirectory (`compiler/`, `simulators/`) for detailed instructions on building, running, and using the specific tools and simulators.


