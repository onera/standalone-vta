# VTA Standalone Compiler

This directory contains the standalone VTA compiler, which is responsible for generating the binary data and instructions required to run the VTA, independently of the TVM framework.

## Subdirectories

*   `data_definition/`:  Tools for generating binary data (input tensors, weights) for VTA execution.
*   `operations_definition/`: Tools and documentation for defining and generating VTA instructions.

## Usage

The compiler is a Python-based toolchain. Refer to the `data_definition` and `operations_definition` directories for detailed instructions on usage and examples.

### Data Definition (`data_definition/`)

This tool allows you to generate binary data files for the VTA.


### Operations Definition (`operations_definition/`)

This tool provides a way to define and generate VTA instructions. See dedicated README for details.


