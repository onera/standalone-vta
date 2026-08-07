# VTA Configuration (`vta_config.json`)

The `standalone-vta` relies heavily on hardware parameters defined in a centralized configuration file located at `config/vta_config.json`. This configuration dictates the bit-widths, memory sizes, and structural elements of the Versatile Tensor Accelerator.

Both the compiler and the simulators read this file to ensure that generated instructions and modeled hardware limits perfectly align.

## Available configurations

`vta_config.json` is the default. The others are selected with the `CONFIG_FILE`
variable from `examples/` (e.g. `make CONFIG_FILE=vta_w8b.json fsim_inference`),
or with `CONFIG=<path>` when building the simulators directly.

| File                 | `TARGET`       | Inputs | Weights | Block | Notes                      |
| :------------------- | :------------- | :----- | :------ | :---- | :------------------------- |
| `vta_config.json`    | `sim`          | 32-bit | 32-bit  | 16x16 | Default.                   |
| `vta_w8b.json`       | `weights8b`    | 32-bit | 8-bit   | 16x16 | Narrower weight SRAM.      |
| `vta_config_8b.json` | `8b_largeBuff` | 8-bit  | 8-bit   | 16x16 | Narrower input and weights |

All three share `LOG_ACC_WIDTH=5`, `LOG_OUT_WIDTH=5` and `LOG_BLOCK=4`.

The same configuration must be used to compile the network, build the simulator,
**and** synthesize the bitstream. Mixing them silently produces wrong results.

## Configuration Parameters

| Parameter           | Type    | Description                                                                                                                                                                                                                                  |
| :------------------ | :------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TARGET`            | String  | Name of this configuration. Used as a label to distinguish configs (e.g. `"sim"`, `"weights8b"`, `"8b_largeBuff"`), not as a simulation/hardware switch.                                                                                     |
| `HW_VER`            | String  | Hardware version string (e.g., `"0.0.2"`). Helps track configuration changes.                                                                                                                                                                |
| `LOG_INP_WIDTH`     | Integer | Log2 of the data width (in bits) for inputs. Example: `5` means $2^5 = 32$-bit inputs.                                                                                                                                                       |
| `LOG_WGT_WIDTH`     | Integer | Log2 of the data width (in bits) for weights.                                                                                                                                                                                                |
| `LOG_ACC_WIDTH`     | Integer | Log2 of the data width (in bits) for accumulators.                                                                                                                                                                                           |
| `LOG_OUT_WIDTH`     | Integer | Log2 of the data width (in bits) for the store/output stream. Must be $\geq$ `LOG_ACC_WIDTH`. A 32-bit output (`5`) requires a CPU-side rescale step after every VTA layer; an 8-bit output (`3`) lets the hardware VSHX ALU do the scaling. |
| `LOG_BATCH`         | Integer | Log2 of the batch size multiplier. `0` means batch size is 1 ($2^0$). Defines the shape of hardware tensors.                                                                                                                                 |
| `LOG_BLOCK`         | Integer | Log2 of the tensor core block size. Example: `4` means a $16 \times 16$ tensor core ($2^4=16$).                                                                                                                                              |
| `LOG_UOP_BUFF_SIZE` | Integer | Log2 of the micro-op buffer size. Limits the number of uops stored on-chip.                                                                                                                                                                  |
| `LOG_INP_BUFF_SIZE` | Integer | Log2 of the input SRAM buffer size in bytes.                                                                                                                                                                                                 |
| `LOG_WGT_BUFF_SIZE` | Integer | Log2 of the weight SRAM buffer size in bytes.                                                                                                                                                                                                |
| `LOG_ACC_BUFF_SIZE` | Integer | Log2 of the accumulator SRAM buffer size in bytes.                                                                                                                                                                                           |

## Impact on System

1. **Compiler:** The compiler uses parameters like `LOG_BLOCK` and the buffer sizes to perform DRAM allocation, matrix partitioning, and cycle-aware instruction scheduling. If a matrix exceeds the block size, the compiler splits it into smaller $16\times16$ chunks (assuming `LOG_BLOCK=4`).
2. **Functional Simulator:** The C++ simulator validates if the compiler strictly adhered to buffer limits.
3. **Cycle-Accurate Simulator:** Chisel reads these parameters during elaboration to synthesize SRAMs, multipliers, and interconnects of the exact dimensions specified.

## Changing Configuration

Under Mill there is nothing to do by hand: the config is a cross key, not a
flag, so artifacts are cached per config and everything downstream of a changed
config is re-run on the next invocation.

```sh
./mill "examples.onnx[lenet5,vta_w8b].fsim"
```

On the standalone per-module Makefile path the three steps are yours:

1. Recompile any test networks using `modules/compiler` (`make -C examples nn_compiler vta_compiler CONFIG_FILE=<name>.json`).
2. Rebuild the functional simulator so the C++ macros sync: `make -C modules/simulator CONFIG=<path> build/fsim`. The generated header is produced by `modules/simulator/config/vta_config.py`, and every object file depends on it, so changing `CONFIG` triggers a rebuild.
3. Re-emit the SystemVerilog the Chisel-backed simulator is built from: `./mill -Dvta.config.file=<name>.json modules.hardware.emitVtaSimConfig`.
