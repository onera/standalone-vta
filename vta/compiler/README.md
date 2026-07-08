# VTA Standalone Compiler

This directory contains the standalone VTA compiler, which is responsible for generating the binary data and instructions required to run the VTA, independently of the TVM framework.

The compiler runs in two stages: `nn_compiler` lowers a quantized ONNX model to a
VTA IR, and `vta_compiler` lowers that IR to the binary streams the simulators and
the FPGA consume. Both are normally driven from `examples/Makefile`
(`make nn_compiler`, `make vta_compiler`) rather than invoked by hand.

## Subdirectories

*   `nn_compiler/`: ONNX front-end. Parses a quantized ONNX model and emits per-node
    CPU parameters plus one VTA IR JSON per layer, and `dependency.csv`. Entry point:
    `nn_compiler/vta_backend.py`. Block-size independent.
*   `vta_compiler/`: VTA IR to binaries. This is where the hardware configuration
    (block size, buffer sizes, data widths) is applied. Entry point:
    `vta_compiler/main_vta_compiler.py`. Stages run in this order:
    *   `data_definition/`: matrix padding and block splitting.
    *   `operations_definition/`: instruction and UOP generation. Owns the ISA
        bitfield layout (`structures.py`). See the
        [dedicated README](vta_compiler/operations_definition/README.md).
    *   `matrix_partitioning/`: overfit detection and GEMM tiling strategies.
    *   `dram_allocation/`: DRAM byte/logical address assignment.
    *   `toolbox/`: block-index helpers.
*   `reference_computation/`: the golden reference path. `reference_onnx.py` computes
    the ONNX reference output; `check_bin.py` compares a simulator's
    `final_output.bin` against it.
*   `utils/`: configuration parsing, JSON parsing, and output-path helpers.

## Usage

Both entry points take positional arguments (there is no flag parsing):

```bash
# Stage 1 - qONNX -> VTA IR
python nn_compiler/vta_backend.py <debug> <expand_bias> <config.json> <model.onnx>

# Stage 2 - VTA IR -> binaries
python vta_compiler/main_vta_compiler.py <debug> <summary> <dram_json> <config.json> <ir.json...>
```

`<debug>`, `<summary>` and `<dram_json>` are booleans. Stage 2 accepts a variable
number of VTA IR files.

## Outputs

Everything is written to `compiler_output/` at the repository root. The location is
resolved by `utils/find_project_root.py` and is not configurable.

The main pipeline suffixes most artifacts with the layer name (e.g.
`instructionsQLinearConv1.bin`), so the flat `instructions.bin` / `uop.bin` names
appear only when running the standalone example scripts in
`vta_compiler/operations_definition/examples/`.

| Output | Contents |
| :--- | :--- |
| `instructions<layer>.bin`, `uop<layer>.bin` | instruction / UOP streams |
| `input<layer>.bin`, `weight<layer>.bin`, `accumulator<layer>.bin`, `add_accumulator<layer>.bin` | data streams |
| `out_init.bin`, `expected_out_sram.bin` | output buffer init and expected SRAM state |
| `memory_addresses<layer>.csv`, `metadata<layer>.csv`, `layers_name.csv` | address and metadata tables |
| `dram_state.json` | full DRAM image (only when the `dram_json` argument is true) |
| `<layer>.json`, `dependency.csv`, `debug_graph.bin` | stage-1 VTA IR and graph metadata |

## ONNX operator support

The front-end offloads these operators to the VTA
(`nn_compiler/vta_backend.py`, `vta_compatible_nodes`):

* `QLinearConv`
* `QLinearMul`
* `MaxPool`
* `Relu`

These are handled but run on the CPU: `QLinearAdd`, `QuantizeLinear`,
`DequantizeLinear`, `QLinearConcat`, `ConvTranspose`. Any other operator is
silently skipped.

Note that `AveragePool` is **not** supported through the ONNX front-end
(`nn_compiler/nodes/node_pool.py` accepts `MaxPool` only), even though the
`operations_definition` examples include a hand-written average-pooling
instruction sequence. `Relu` is the only supported activation.
