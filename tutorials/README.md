# Tutorials

We present here two Jupyter notebooks, which aim to explain how to use the standalone-vta, and illustrate the data generation and manipulation in the standalone-vta/compiler, to be used in standalone-vta/simulators.

- notebook on data def
- notebook on op def

## Using compiler/data_definition

badge notebook #1

This notebook focuses on the folder data_definition. It defines the data the VTA will operate on.
This part of the compiler is used to generate the binary files `input.bin`, `weight.bin`, `out_init.bin`, `expected_out.bin`, `expected_out_sram.bin`, as well as the CSV file `memory_addresses.csv`, which contain the base addresses for each data type, in standalone-vta/compiler_output. 
The binary files contain the encoded data, in accordance with VTA requirements.

## Using compiler/operations_definition

badge notebook #2

This notebook focuses on the folder operation_definition. It defines the buffers for the UOP and the instructions of multiple operations done by the VTA.
This part of the compiler is used to generate the binary files `uop.bin`, `instructions.bin` in standalone-vta/compiler_output.
The binary files contain the encoded data, in a way computable by CHISEL.