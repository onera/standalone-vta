# Tutorials

We present here two Jupyter notebooks, which aim to explain how to use the standalone-vta, and illustrate the data generation and manipulation in the standalone-vta/modules/compiler/vta_compiler, to be used in standalone-vta/modules/simulator. Two [marimo](https://marimo.io) notebooks run a model on an FPGA board over UART, or in the simulators.

- [Tutorial 1 : data_definition](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial1_data_definition.ipynb)
- [Tutorial 2 : operations_definition](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial2_operations_definition.ipynb)
- Tutorial 3 : `tutorial3_qyolo_uart.py` - qyolo on the board, over UART (local only, see below)
- Tutorial 4 : `tutorial4_lenet5_digit.py` - draw a digit, classify it with lenet5 (local only, see below)

## TUTORIAL 1 : using vta_compiler/data_definition

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial1_data_definition.ipynb)

This notebook focuses on the folder data_definition. It defines the data the VTA will operate on.
This part of the compiler is used to generate the binary files `input.bin`, `weight.bin`, `accumulator.bin`, `out_init.bin`, `expected_out_sram.bin`, as well as the CSV file `memory_addresses.csv`, which contain the base addresses for each data type, in standalone-vta/compiler_output. 
The binary files contain the encoded data, in accordance with VTA requirements.

## TUTORIAL 2 : using vta_compiler/operations_definition

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/onera/standalone-vta/main?urlpath=%2Fdoc%2Ftree%2Ftutorials%2Ftutorial2_operations_definition.ipynb)

This notebook focuses on the folder operations_definition. It defines the buffers for the UOP and the instructions of multiple operations done by the VTA.
This part of the compiler is used to generate the binary files `uop.bin`, `instructions.bin` in standalone-vta/compiler_output.
The binary files contain the encoded data, in a format computable by CHISEL.

## TUTORIALS 3-4 : qyolo and lenet5 on a board

These need the repository's pixi environment and Mill build, so they run
locally rather than on Binder:

```sh
pixi run -e notebooks marimo edit tutorials/tutorial3_qyolo_uart.py
pixi run -e notebooks marimo edit tutorials/tutorial4_lenet5_digit.py
```

Pick a model, VTA config and board, then an image (tutorial 3) or a drawn
digit (tutorial 4). The input can run on the board over UART
(`buildVitisApp`, `flashBoard`, `runUart`), in `fsim` or `vsim` (`runFsim`,
`runVsim`), or in `onnxruntime`. The first three execute the same compiled
binaries, so comparing them isolates a compiler, RTL or platform issue.

`runFsim` / `runVsim` take any input file instead of the reference's random
`input_nn.bin`:

```sh
pixi run ./mill 'examples.onnx[lenet5,vta_config].runFsim' \
    --input my_digit.bin --output out.bin
```

`--input` is a flat INT8 `[H*W][C]` buffer and `--output` a flat NCHW INT8
tensor. No golden check is done.
