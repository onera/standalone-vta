# VTA Configuration (`vta_config.json`)

The `standalone-vta` relies heavily on hardware parameters defined in a centralized configuration file located at `config/vta_config.json`. This configuration dictates the bit-widths, memory sizes, and structural elements of the Versatile Tensor Accelerator.

Both the compiler and the simulators read this file to ensure that generated instructions and modeled hardware limits perfectly align.

## Configuration Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `TARGET` | String | Target environment. Currently usually set to `"sim"` for simulation targets. |
| `HW_VER` | String | Hardware version string (e.g., `"0.0.2"`). Helps track configuration changes. |
| `LOG_INP_WIDTH` | Integer | Log2 of the data width (in bits) for inputs. Example: `5` means $2^5 = 32$-bit inputs. |
| `LOG_WGT_WIDTH` | Integer | Log2 of the data width (in bits) for weights. Example: `5` means $2^5 = 32$-bit weights. |
| `LOG_ACC_WIDTH` | Integer | Log2 of the data width (in bits) for accumulators. Example: `5` means $2^5 = 32$-bit accumulators. |
| `LOG_BATCH` | Integer | Log2 of the batch size multiplier. `0` means batch size is 1 ($2^0$). Defines the shape of hardware tensors. |
| `LOG_BLOCK` | Integer | Log2 of the tensor core block size. Example: `4` means a $16 \times 16$ tensor core ($2^4=16$). |
| `LOG_UOP_BUFF_SIZE` | Integer | Log2 of the micro-op buffer size. Limits the number of uops stored on-chip. |
| `LOG_INP_BUFF_SIZE` | Integer | Log2 of the input SRAM buffer size in bytes. |
| `LOG_WGT_BUFF_SIZE` | Integer | Log2 of the weight SRAM buffer size in bytes. |
| `LOG_ACC_BUFF_SIZE` | Integer | Log2 of the accumulator SRAM buffer size in bytes. |

## Impact on System

1.  **Compiler:** The compiler uses parameters like `LOG_BLOCK` and the buffer sizes to perform DRAM allocation, matrix partitioning, and cycle-aware instruction scheduling. If a matrix exceeds the block size, the compiler splits it into smaller $16\times16$ chunks (assuming `LOG_BLOCK=4`).
2.  **Functional Simulator:** The C++ simulator validates if the compiler strictly adhered to buffer limits.
3.  **Cycle-Accurate Simulator:** Chisel reads these parameters during elaboration to synthesize SRAMs, multipliers, and interconnects of the exact dimensions specified.

## Changing Configuration

If you change `vta_config.json`, you must:
1. Recompile any test networks using `src/compiler`.
2. Re-run `make all` in `src/simulators/functional_simulator` if C++ macros need to sync (often handled via `config/vta_config.py`).
3. Clean and rebuild the Chisel simulators using `mill` or `sbt`.