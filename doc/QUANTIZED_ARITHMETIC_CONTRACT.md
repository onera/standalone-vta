# Bit-Exact Quantized Arithmetic Contract

## Purpose

This document defines the numerical contract shared by the standalone NumPy
reference, the functional simulator, and the ARM PS-side runtime. The embedded
implementation is authoritative when several floating-point decompositions are
mathematically equivalent. ONNX Runtime is a secondary interoperability check;
it is not the bit-exact oracle because kernels, graph optimizations, and
execution providers may use different intermediate arithmetic.

All commands and validation scripts must be run through Pixi.

## Common rules

- ONNX scales and precomputed effective multipliers are IEEE-754 `float32`.
- Element-wise divisions are forbidden. A reciprocal or effective multiplier
  is computed once per layer or input branch.
- Quantized CPU operations use explicit `float32` intermediate variables and
  `nearbyintf`, with round-to-nearest, ties-to-even.
- VTA integer accumulators are requantized as
  `nearbyint(double(accumulator) * double(multiplier_float32))`.
- The output zero-point is added after rounding, followed by saturation to the
  destination integer type.
- Build recipes disable floating-point contraction (`-ffp-contract=off`);
  do not add `fast-math` or reassociation flags. Named intermediate variables
  alone do not prevent a C++ compiler from contracting products and sums.
- C++ `nearbyint`/`nearbyintf` obey the active floating-point rounding mode.
  Nearest-even therefore assumes the default `FE_TONEAREST` environment remains
  active on the host and ARM. These functions do not set the rounding mode.

## Operator contract

| Operator | Required evaluation order |
| --- | --- |
| `QLinearConv` | Accumulate centered integer products and bias in `int32`; compute `(sA*sB)/sC` as `float32`; apply the VTA double-accumulator rescale. |
| `QLinearMul` | Require one scalar operand; compute `(A-zA)*(B-zB)` in `int32`; apply `float32((sA*sB)/sC)` through the VTA double-accumulator rescale. |
| `QLinearAdd` | `invC=float32(1/sC)`; `mA=float32(sA*invC)`; `mB=float32(sB*invC)`; `termA=float32((A-zA)*mA)`; `termB=float32((B-zB)*mB)`; `scaled=float32(termA+termB)`; round, add `zC`, saturate. |
| `QLinearConcat` | For each branch compute `mX=float32(sX*float32(1/sC))`; requantize that branch with one `float32` multiplication per value before concatenation. |
| `QuantizeLinear` | `inv=float32(1/scale)`; `scaled=float32(x*inv)`; round, add zero-point, saturate. Embedded output is `int8`. |
| `DequantizeLinear` | `centered=float32(q)-float32(zp)`; result is `float32(centered*scale)`. |
| `MaxPool` | Compare values directly in their quantized integer domain. Spatial padding is `-128`; no requantization is applied. |
| `ConvTranspose` | Accumulate products in explicit `float32` scalar loop order, then add bias in `float32`. |

`format_input`, `im2row`, and `int32_chain` are exact layout/type conversion
operations and do not introduce a quantization rounding step.

## Supported embedded subset

- `QLinearMul`: exactly one dynamic tensor and one single-element initializer.
- `QLinearConcat`: batch one, channel axis (`axis=1`), two to four inputs
  sharing N/H/W. Each branch may have a different channel count, including
  counts that are not multiples of the VTA block size.
- `ConvTranspose`: `group=1`, dilation `(1,1)`, `output_padding=(0,0)`, and
  equal height/width strides.
- Quantized activations are `int8`. The NumPy convolution can broadcast
  per-output-channel effective scales, but the fsim/embedded execution
  descriptors carry a single multiplier per layer. Three-backend validation
  in this document covers scalar scales only.

The arithmetic contract concerns logical tensor values. It does not establish
general layout parity of all runtime descriptors. In particular, the current
embedded QAdd traverses two flat buffers without shape/layout metadata, whereas
fsim reconstructs each logical tensor. Residual inputs with different physical
row padding (such as ResNet-18's MaxPool/Conv pair) need additional runtime
layout support before claiming three-backend parity on that topology.
Concat supports partial spatial/channel blocks and mixtures of square-padded
and short-row MaxPool input layouts. Output uses square-block padding; padding
cells are physical zero and are excluded from logical requantization.

Integer accumulators are assumed to stay within int32 and intermediate scales
and products to remain finite. Extremely large rounded values can exceed the
C++ integer conversion range before the existing saturation step; such inputs
are outside the validated range. Scales are expected to be positive and finite;
current runtime guards check zero, not every invalid scale.

### Concat layout and generated descriptors

`dependency.csv` retains its existing format. Each concat parent row contains
its own output C/H/W; the concat's input C/H/W fields describe only the first
branch. Both fsim and the header generator recover the remaining branch shapes
through the ordered parent names, preserving their quantization scale/ZP order.

`NnConcatStep` replaces the single shared `n_ch_per_inp` with `channels[4]`,
`stored_rows[4]`, and `n_out_elems`. Physical input rows are `H*W` for canonical
VTA MaxPool producers and `round_up(H*W, B)` for square-block producers. For a
short final row-block, each channel block's stride uses that short height;
assuming a full `B*B` stride would read the wrong input channels.

The runtime precomputes one float32 multiplier per branch, then repacks only
logical channels into the cumulative output-channel offset. Input channel
padding is never inserted between branches. It writes to the blocked output
directly without allocating reconstructed tensors. Output storage and cache
flush size are both `round_up(H*W, B) * round_up(sum(C), B)` int8 bytes; scratch
allocation and buffer-fit checks use that same count.

Regenerate bare-metal headers with `pixi run make -C src/fpga/software gen`
after updating the driver. Existing `nn_exec_plan.h` files are incompatible
with the revised concat descriptor and must not be reused with the new runtime.

The compiler must reject unsupported variants rather than silently emitting a
model that fsim or the board evaluates differently.

## Validation

```bash
pixi run python -m unittest \
  src.compiler.reference_computation.test_quantized_arithmetic \
  src.compiler.reference_computation.test_compare_layers \
  src.fpga.software.test.test_concat_generation -v
pixi run make -C src/fpga/software test-cpu-ops
pixi run python src/compiler/reference_computation/compare_layers.py \
  examples/onnx/qyolo.onnx
```

The trained QLinear models can be checked individually with the same pipeline:

```bash
pixi run python src/compiler/reference_computation/compare_layers.py \
  training_output/LeNet5/vta_cnn_qlinear.onnx
pixi run python src/compiler/reference_computation/compare_layers.py \
  training_output/VGG16/vta_cnn_qlinear.onnx
pixi run python src/compiler/reference_computation/compare_layers.py \
  training_output/ResNet18/vta_cnn_qlinear.onnx
pixi run python src/compiler/reference_computation/compare_layers.py \
  training_output/GoogLeNet/vta_cnn_qlinear.onnx
```

The Python tests cover ties, saturation, non-zero zero-points, and every
supported arithmetic operator. The host CPU-op test compiles the real embedded
driver and compares it with fsim. `compare_layers.py` compares logical outputs
and, for VTA convolution/multiply layers with a 32-bit OUT path, reports the raw
integer accumulator comparison before requantization. With `--dump-layers`,
the simulator also exports `DequantizeLinear` and `ConvTranspose` outputs as
logical NCHW float32 files using the same `fsim_out_<layer>.bin` naming scheme.
The comparator selects the dtype from the operator, validates the byte count,
and checks float32 bit patterns without tolerance (including signed zero and
NaN payloads). Missing dumps fail instead of silently skipping a layer.
An accumulator mismatch makes the comparison fail even when clipping hides
the difference in the final int8 output. Block size and OUT width come from
the same hardware configuration used by the compilation pipeline.

### Validation evidence and limits

The current `training_output/<model>/vta_cnn_qlinear.onnx` files were checked
using `config/vta_config.json` (block size 16, 32-bit INP/WGT/ACC/OUT). Each
successful run compares every logical output and every available convolution
accumulator for the pipeline-generated input. This is an exact regression test
for that input, not an exhaustive proof over all possible activations.

| Model | Input shape (NCHW) | NumPy/fsim layer outputs | Pre-rescale accumulators | FPGA validation |
| --- | --- | --- | --- | --- |
| LeNet-5 | `1x1x28x28` | PASS: 7/7 | PASS: 5/5 | PASS |
| VGG16 | `1x1x28x28` | PASS: 20/20 | PASS: 16/16 | Not reported |
| ResNet-18 | `1x1x224x224` | PASS: 30/30 | PASS: 21/21 | Not reported |
| GoogLeNet | `1x1x28x28` | PASS: 80/80 | PASS: 58/58 | Not reported |

GoogLeNet's first Inception concatenation receives tensors shaped
`[1,64,4,4]`, `[1,128,4,4]`, `[1,32,4,4]`, and `[1,32,4,4]`. All nine Inception
concats pass NumPy/fsim validation, including later stages with just four or
one spatial positions. Bare-metal generation succeeds with per-parent channel
counts and padded scratch sizes, and passes allocation-overlap, binary-fit,
and CPU-output-fit checks. This is host validation of the generated plan and
CPU kernel, not a complete GoogLeNet execution on FPGA.

Host concat tests compare the real embedded kernel with fsim on unequal
channels (including 3/17/5), short and square input layouts, partial output
blocks, nonzero zero-points, and saturation. Sentinel bytes check that the
kernel respects the declared physical output size. Generator tests verify
branch metadata, shape checks, and allocation sizes for multiple block sizes.

The LeNet-5 FPGA result above is a maintainer-reported hardware validation;
the automated runs in this table were performed on the host. The FPGA result
applies to LeNet-5; the other models have separate validation status.

For the complete QYolo model, all 149 layer dumps passed, including exact
float32 representations for
`DequantizeLinear84`, `ConvTranspose85`, `DequantizeLinear102`, and
`ConvTranspose103`. The isolated `qyolo_qconvtranspose.onnx` graph also passed
all three nodes (dequantization, float convolution, and requantization).
The host CPU-op tests exercise the real driver source, including exact float
bit comparisons for DequantizeLinear and ConvTranspose; these are host results,
not measurements from ARM hardware. Board validation beyond the reported
LeNet-5 result remains outstanding.

The NumPy source documents each operator's evaluation order. Unit tests cover
adjacent float32 values around half-integers and convolution accumulation,
bias, centered padding, and requantization. Existing random host
tests mainly cover layout operations and ConvTranspose; quantized CPU-op tests
are targeted cases and are not exhaustive over scale/input combinations.

Golden outputs must be regenerated after changing this contract. Values close
to a half-integer may legitimately differ from older references even when the
real-valued formula is unchanged.

For QYolo `QLinearAdd24` at NCHW coordinate `(0,45,6,10)`, the selected
two-ratio contract evaluates the pre-round value to exactly `139.5f` and
therefore produces quantized value `12` by ties-to-even. This is intentional;
the former NumPy decomposition produced `139.49998f` and value `11`.
