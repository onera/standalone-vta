import torch
import torch.nn as nn
import torchao
from torch.export import Dim
from torchao.quantization.pt2e.quantize_pt2e import (
    prepare_qat_pt2e,
    convert_pt2e,
)
from executorch.backends.xnnpack.quantizer.xnnpack_quantizer import (
    get_symmetric_quantization_config,
    XNNPACKQuantizer,
)

def prepare_qat_model(
    model: nn.Module, 
    example_inputs: torch.Tensor,
    min_batch: int = 1,
    max_batch: int = 64
) -> nn.Module:
    """Exports model with dynamic shapes and prepares it for PT2E Quantization-Aware Training (QAT).

    Args:
        model: PyTorch FP32 module.
        example_inputs: Sample input tensor used to trace/export the model graph.
        min_batch: Minimum dynamic batch size limit.
        max_batch: Maximum dynamic batch size limit.

    Returns:
        Prepared QAT PyTorch module.
    """
    # Allow batch size to vary dynamically between min_batch (e.g. 1 for VTA) and max_batch (e.g. 64 for training)
    batch_dim = Dim("batch", min=min_batch, max=max_batch)
    dynamic_shapes = ({0: batch_dim},)

    # Export model for quantization using torch.export
    exported_model = torch.export.export(
        model, 
        (example_inputs,), 
        dynamic_shapes=dynamic_shapes
    ).module()

    # Prepare QAT model using torchao symmetric quantization
    quantizer = XNNPACKQuantizer().set_global(get_symmetric_quantization_config())
    qat_model = prepare_qat_pt2e(exported_model, quantizer)

    return qat_model

def convert_quantized_model(qat_model: nn.Module) -> nn.Module:
    """Converts a trained QAT model into a fully quantized model.

    Args:
        qat_model: Trained PT2E QAT model.

    Returns:
        Quantized PyTorch model.
    """
    torchao.quantization.pt2e.move_exported_model_to_eval(qat_model)
    q_model = convert_pt2e(qat_model)
    return q_model
