# Tutorials

We present here two Jupyter notebooks, which aim to explain how to use the standalone-vta, and illustrate the data generation and manipulation in the standalone-vta/src/compiler/vta_compiler, to be used in standalone-vta/src/simulators.

- [Tutorial 1 : data_definition](https://mybinder.org/v2/gh/onera/standalone-vta/b3aba2fd42a10fb793de7befd4ae31d99a59e8c9?urlpath=lab%2Ftree%2Ftutorials%2Ftutorial1_data_definition.ipynb)
- [Tutorial 2 : operations_definition](https://mybinder.org/v2/gh/onera/standalone-vta/b3aba2fd42a10fb793de7befd4ae31d99a59e8c9?urlpath=lab%2Ftree%2Ftutorials%2Ftutorial2_operations_definition.ipynb)

## TUTORIAL 1 : using vta_compiler/data_definition

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial1_data_definition.ipynb)

This notebook focuses on the folder data_definition. It defines the data the VTA will operate on.
This part of the compiler is used to generate the binary files `input.bin`, `weight.bin`, `out_init.bin`, `expected_out.bin`, `expected_out_sram.bin`, as well as the CSV file `memory_addresses.csv`, which contain the base addresses for each data type, in standalone-vta/compiler_output. 
The binary files contain the encoded data, in accordance with VTA requirements.

## TUTORIAL 2 : using vta_compiler/operations_definition

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial2_operations_definition.ipynb)

This notebook focuses on the folder operation_definition. It defines the buffers for the UOP and the instructions of multiple operations done by the VTA.
This part of the compiler is used to generate the binary files `uop.bin`, `instructions.bin` in standalone-vta/compiler_output.
The binary files contain the encoded data, in a format computable by CHISEL.