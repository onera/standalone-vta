# Tutorials

We present here two Jupyter notebooks, which aim to explain how to use the standalone-vta, and illustrate the data generation and manipulation in the standalone-vta/compiler, to be used in standalone-vta/simulators.

- /* Link NoteBook #1 to be added after merging */
- /* Link NoteBook #2 to be added after merging */

/* Temporary badge before splitting : */
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2FDocumentation%2Fcompiler_doc.ipynb)

## TUTORIAL 1 : using compiler/data_definition

/* Badge NoteBook #1 to be added after merging */

This notebook focuses on the folder data_definition. It defines the data the VTA will operate on.
This part of the compiler is used to generate the binary files `input.bin`, `weight.bin`, `out_init.bin`, `expected_out.bin`, `expected_out_sram.bin`, as well as the CSV file `memory_addresses.csv`, which contain the base addresses for each data type, in standalone-vta/compiler_output. 
The binary files contain the encoded data, in accordance with VTA requirements.

## TUTORIAL 2 : using compiler/operations_definition

/* Badge NoteBook #2 to be added after merging */

This notebook focuses on the folder operation_definition. It defines the buffers for the UOP and the instructions of multiple operations done by the VTA.
This part of the compiler is used to generate the binary files `uop.bin`, `instructions.bin` in standalone-vta/compiler_output.
The binary files contain the encoded data, in a way computable by CHISEL.