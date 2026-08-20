# Matrix Partitioning and ACC SRAM Addressing

This directory converts compiler operations into execution `steps` that fit the
configured VTA SRAM buffers. It contains the tiling strategies used for GEMM,
two-matrix operations, and accumulator-only ALU operations.

The most important rule for accumulator reductions is:

> A logical value that remains live across steps must keep the same physical ACC
> SRAM vector address until it is stored or explicitly moved.

This rule is easy to violate because the compiler represents physical placement
with an ordered Python list. Reordering that list does not generate a hardware
copy.

## Terminology and addressing units

The compiler uses several related units. They must not be confused:

| Term | Meaning with the default configuration |
| :--- | :--- |
| Scalar lane | One `int32` accumulator value |
| ACC vector | 16 scalar lanes processed together by the Tensor ALU |
| ACC vector slot | One physical ACC SRAM address selecting one ACC vector |
| Matrix block | A logical `16 x 16` tile containing 16 ACC vectors |
| `VectorIndex` | A logical vector identifier `(block_idx, row_inside_block)` |

The default ACC SRAM capacity is computed by
[`utils/configuration.py::buffer_size()`](../../utils/configuration.py):

```text
LOG_ACC_BUFF_SIZE = 17  -> 2^17 bits of storage
LOG_ACC_WIDTH     = 5   -> 2^5 = 32 bits per scalar lane
LOG_BLOCK         = 4   -> 2^4 = 16 lanes per vector

ACC vector capacity = 2^17 / (4 bytes x 16 lanes) = 2048 vectors
ACC block capacity  = 2048 / 16 vectors per block = 128 blocks
```

Consequently, `matrix_partitioning.py` uses the 128-block capacity when it
decides whether a matrix fits as complete blocks. The accumulator-only ALU
strategy receives the 2048-vector capacity because its state is expressed as
individual `VectorIndex` values.

An ACC vector slot is not permanently associated with a logical block and row.
For example, physical slot zero can hold `(0, 2)` in one step and `(17, 6)` in a
later step.

## Compiler path

Accumulator ALU operations follow this path:

```text
ONNX operator
  -> nn_compiler VTA IR JSON
  -> toolbox/alu_operations.py
  -> matrix_partitioning.py
  -> one or more strategy steps
  -> operations_definition/instructions_generator.py
  -> LOAD ACC, LOAD UOP, ALU, and STORE OUT instructions
```

The VTA IR initially describes matrix-row indices. For a vector-vector ALU
operation, its compact form is:

```python
[
    "MAX",
    [
        [destination_row, destination_step],
        [source_row, source_step],
        iteration_count,
    ],
]
```

[`toolbox/alu_operations.py::create_alu_operations_list()`](../toolbox/alu_operations.py)
expands the iteration and converts matrix rows to logical vector identifiers.
After vectors sharing a destination have been grouped, an operation has the
following shape:

```python
[
    "MAX",
    matrix_parameters,
    [
        (
            (destination_block, destination_row_in_block),
            [
                (source_block_0, source_row_in_block_0),
                (source_block_1, source_row_in_block_1),
            ],
        )
    ],
]
```

[`utils_strategies.py::sort_alu_by_dst()`](utils_strategies.py) then flattens
operations that cover several channel blocks and sorts them so that operations
with the same logical destination are consecutive.

## Strategy step format

[`matrix_partitioning()`](matrix_partitioning.py) returns a list of
seven-element tuples:

```python
step = (
    load_A,       # step[0]
    load_B,       # step[1]
    load_X,       # step[2]
    sram_status,  # step[3]
    dram_status,  # step[4]
    store_C,      # step[5]
    operations,   # step[6]
)
```

| Field | Role |
| :--- | :--- |
| `step[0]` | Logical INP blocks to load into the input SRAM |
| `step[1]` | Logical WGT blocks to load into the weight SRAM |
| `step[2]` | ACC blocks or vectors that must be loaded during this step |
| `step[3]` | Ordered description of the logical values occupying physical ACC SRAM addresses |
| `step[4]` | Ordered output-vector state used to derive dense OUT DRAM addresses |
| `step[5]` | ACC blocks or vectors to store after the computation |
| `step[6]` | GEMM and/or ALU operations executed by the step |

For vector-wise ALU steps, the physical ACC address of a logical vector is:

```python
physical_acc_slot = sram_status.index(logical_vector)
```

This mapping is used consistently by:

- `step_load_acc()` to choose the `sram_base` of a LOAD ACC instruction;
- `step_compute()` to generate `VTAUop.dst_idx` and `VTAUop.src_idx`;
- `step_store()` to choose the `sram_base` of a STORE OUT instruction.

`step[2]` and `step[3]` are therefore different concepts. `step[2]` says what
must be transferred from DRAM in the current step. `step[3]` describes the full
logical-to-physical mapping assumed while the step executes. A live destination
can be present in `step[3]` but absent from `step[2]` when it was loaded and
partially reduced by a previous step.

For vector-wise stores, `step[4]` is the ordered `idx_to_store` list. The OUT
address is dense even when the selected ACC vectors are sparse:

```python
out_address = out_dram_base + dram_status.index(destination_vector)
```

## Accumulator-only ALU strategy

[`alu_strategies.py::alu_strategy()`](alu_strategies.py) groups operations by
destination. For each destination it reserves physical ACC vector slot zero and
uses the remaining slots for sources:

```text
ACC slot 0     current live destination
ACC slots 1.. current sources
```

If all sources fit, the destination is loaded, fully reduced, and stored in one
step. If they do not fit, the reduction is split into segments:

1. The first segment loads the destination and its first sources.
2. Intermediate segments keep the destination in physical slot zero and load
   only replacement sources.
3. The final segment stores the destination.
4. Slot zero can then be reused for another independent destination.

The strategy deliberately preserves repeated sources in the operation stream,
because repetition can be semantically significant for operations such as ADD.
Only the SRAM load list is deduplicated.

## Worked example: VGG16 `MaxPool3`

The first VGG16 MaxPool consumes a `1 x 64 x 28 x 28` tensor and produces a
`1 x 64 x 14 x 14` tensor. The compiler represents the input accumulator as a
`784 x 64` matrix:

```text
784 spatial rows x 64 channels
= 49 block rows x 4 channel blocks
= 196 logical 16 x 16 blocks
```

Because 196 blocks exceed the 128-block ACC capacity, this layer takes the
over-capacity ALU path. The output contains:

```text
14 x 14 spatial destinations x 4 channel vectors = 784 destination vectors
```

Consider the `2 x 2` window whose flattened input rows are `2`, `3`, `30`, and
`31`. For channels `0..15`, these rows become:

| Spatial value | Logical vector | Logical block of origin |
| :--- | :--- | :--- |
| Top-left destination | `(0, 2)` | Block 0 |
| Top-right source | `(0, 3)` | Block 0 |
| Bottom-left source | `(4, 14)` | Block 4 |
| Bottom-right source | `(4, 15)` | Block 4 |

The four spatial values come from only two logical `16 x 16` blocks, but they
are four distinct vectors. The vector-wise strategy compacts those vectors into
four physical ACC slots:

```python
sram_status = [
    (0, 2),   # physical ACC vector slot 0: destination
    (0, 3),   # physical ACC vector slot 1: source
    (4, 14),  # physical ACC vector slot 2: source
    (4, 15),  # physical ACC vector slot 3: source
]
```

The generated UOPs are:

```text
MAX(dst=0, src=1)
MAX(dst=0, src=2)
MAX(dst=0, src=3)
```

Each UOP compares 16 channels in parallel. After the three UOPs, physical ACC
slot zero contains the pooled result for channels `0..15` and is stored. The
same process is repeated for channel blocks `1`, `2`, and `3`.

Therefore, for one spatial `2 x 2` window with 64 channels, the current strategy
uses four destination reductions, twelve vector MAX UOPs, and four vector
stores. This is a scheduling choice; the mathematical requirement remains
three comparisons per output value.

## Historical MaxPool corruption

The previous over-capacity ALU strategy allowed several live destinations in a
single step. At a partition boundary it compacted only the Python description:

```python
sram_status = store_C.copy()
```

No LOAD, STORE, ALU, or other hardware instruction moved the already-computed
values to the new indices. In the first VGG16 `MaxPool3` boundary, destination
`(0, 2)` was physically located at ACC vector slot 4, while the next step
described it at slot 1. Subsequent UOPs and stores therefore addressed unrelated
data.

The corrected implementation enforces this invariant:

> A live ALU destination remains in physical ACC vector slot zero until its
> final store.

The focused regression tests are in
[`tests/compiler/test_alu_strategy.py`](../../../../tests/compiler/test_alu_strategy.py).
The broader investigation history and layer-by-layer numerical results are
preserved in
[`doc/vta_maxpool_bugs_analysis.md`](../../../../doc/vta_maxpool_bugs_analysis.md).

## Correctness and performance considerations

The current destination-at-slot-zero strategy favors a simple, verifiable
mapping. Independent destinations are stored before slot zero is reused. This
is conservative: a future strategy could retain several destinations and
process more work between stores, provided that every live destination keeps a
stable physical slot and that newly loaded sources cannot overwrite it.

Any such optimization should preserve the following properties:

1. Every `VTAUop` address is within the configured ACC vector capacity.
2. Every logical vector in an operation is present in that step's
   `sram_status`.
3. Live values retain their physical slots across step boundaries.
4. A destination is stored only after its complete ordered reduction.
5. Sparse logical output selections are mapped to dense OUT addresses in the
   order of `idx_to_store`.
