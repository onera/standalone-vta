# Quantization-Aware Training

This package trains PyTorch models with PT2E Quantization-Aware Training (QAT),
exports quantized ONNX graphs, and connects them to the standalone VTA compiler.
Supported architectures are LeNet5, VGG16, ResNet18, and GoogLeNet.

## Run the pipeline

Run commands from the repository root using the Pixi `training` environment.
For a short CPU run with LeNet5 and FashionMNIST:

```bash
pixi run -e training python -m src.training.train \
  --config src/training/configs/lenet5.yaml \
  --device cpu --epochs 1 --max-steps-per-epoch 3 --skip-vta
```

The first run may download the dataset. Command-line options override the YAML
configuration. Use `--max-steps-per-epoch 0` for full epochs; the step limit
otherwise applies to both training and validation. Inspect available options:

```bash
pixi run -e training python -m src.training.train --help
```

By default, outputs are written to `training_output/<model_name>/`:

| File | Content |
| --- | --- |
| `config.yaml` | Effective training configuration |
| `q_model_state_dict.pth` | Converted model state dictionary |
| `vta_cnn_qdq.onnx` | ONNX graph with quantize/dequantize operations |
| `vta_cnn_qlinear.onnx` | Graph converted to QLinear operators for the compiler |

`--skip-onnx-verify` skips output comparisons with ONNX Runtime. Without
`--skip-vta`, the pipeline also invokes VTA compilation and simulation.

## Quantization configuration

[`prepare_qat_model`](quantization/pt2e_utils.py) exports the FP32 model with a
dynamic batch dimension, then prepares it with TorchAO PT2E and the ExecuTorch
XNNPACK quantizer:

```python
quantizer = XNNPACKQuantizer().set_global(
    get_symmetric_quantization_config(is_qat=True)
)
qat_model = prepare_qat_pt2e(exported_model, quantizer)
```

`is_qat=True` is required: the configuration helper defaults to PTQ observers.
Calling `prepare_qat_pt2e` alone does not select QAT fake quantization.
See the quantizer configuration section of the
[TorchAO PT2E QAT tutorial](https://docs.pytorch.org/ao/stable/pt2e_quantization/pt2e_quant_qat.html).

The current configuration uses static INT8 quantization:

| Tensor | Scheme | Integer range |
| --- | --- | --- |
| Activations | Per-tensor affine | `[-128, 127]` |
| Weights | Per-tensor symmetric | `[-127, 127]` |

Activation zero-points are not forced to zero. Fake quantization simulates
rounding and clipping while retaining floating-point training and gradients.
The backend uses moving-average observers through
`FusedMovingAvgObsFakeQuantize`. Batch sizes used for export must satisfy the
dynamic-shape constraints; the pipeline sets bounds from 1 to the configured
training batch size.

## Training and validation

[`train_model`](engine/trainer.py) manages observer updates separately from
the exported model's training/evaluation mode:

| Phase | Observer updates | Fake quantization |
| --- | --- | --- |
| Training | Enabled at the start of each training phase | Enabled |
| Validation | Disabled for the entire phase | Enabled |

Observers estimate the ranges used to determine scales and zero-points.
Validation therefore uses fixed quantization parameters and does not calibrate
the model on validation data. The next training phase re-enables updates.
PT2E's `move_exported_model_to_train` and `move_exported_model_to_eval` manage
exported training/evaluation behavior; evaluation mode alone does not disable
observers.

The trainer restores the best validation state when one is selected, including
the quantization buffers stored in the state dictionary.

The TorchAO tutorial also describes optionally freezing observers and BatchNorm
running statistics after selected epochs. This permanent training freeze is
not currently implemented. Adding it would require a schedule that prevents
the training phase from re-enabling observers after the freeze threshold.

## Conversion and numerical scope

After training, `convert_quantized_model` switches exported evaluation behavior
and calls `convert_pt2e`. The pipeline then exports the converted graph to ONNX
and converts QDQ patterns to QLinear operators.

XNNPACK provides the current quantization policy. It does not guarantee that
training simulates every VTA accumulator, rounding, or requantization detail.
The [quantized arithmetic contract](../../doc/QUANTIZED_ARITHMETIC_CONTRACT.md)
describes the compiler/runtime reference behavior and its validation limits.
Numerical equivalence across PyTorch, ONNX, NumPy, and VTA must be checked
separately; successful export alone does not establish it.

Models trained with the earlier configuration lacking `is_qat=True` need a new
training or fine-tuning run with fake quantization enabled before their results
can be interpreted as QAT results.

## Regression tests

```bash
pixi run -e training python -m pytest -p no:rerunfailures \
  tests/training/test_quantization.py \
  tests/training/test_trainer.py \
  tests/training/test_onnx_conversion.py -q
```

The checks cover enabled fake quantization, gradient propagation and optimizer
updates, conversion, and observer freezing/resumption over two epochs.
The ONNX conversion test checks artifact creation, not output equivalence.
`-p no:rerunfailures` allows these tests to run in environments where that
optional plugin's socket initialization is unavailable.
