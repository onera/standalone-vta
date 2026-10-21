"""Regression checks for PT2E fake quantization during training."""

import pytest
import torch
import torch.nn as nn
from torchao.quantization.pt2e.fake_quantize import FakeQuantizeBase

from src.training.modeling import get_model
from src.training.quantization import convert_quantized_model, prepare_qat_model


@pytest.mark.parametrize("with_batch_norm", [False, True])
def test_qat_fake_quantization_training_and_conversion(with_batch_norm: bool) -> None:
    """Checks fake quantization, gradients and conversion with and without BN.

    Args:
        with_batch_norm: Whether to exercise a Conv-BN-ReLU block rather than
            the repository's LeNet5 architecture.
    """
    torch.manual_seed(0)
    if with_batch_norm:
        model = nn.Sequential(
            nn.Conv2d(1, 4, kernel_size=3, padding=1),
            nn.BatchNorm2d(4),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(4, 10, kernel_size=1),
        )
    else:
        model = get_model(
            "LeNet5", num_classes=10, in_channels=1, image_size=(28, 28)
        )
    inputs = torch.randn(4, 1, 28, 28)
    prepared = prepare_qat_model(model, inputs, max_batch=8)
    fake_quantizers = [
        module for module in prepared.modules()
        if isinstance(module, FakeQuantizeBase)
    ]
    # Observers alone permit gradients but do not simulate quantization in QAT.
    assert fake_quantizers
    assert all(bool(module.fake_quant_enabled.item()) for module in fake_quantizers)
    assert all(module.dtype == torch.int8 for module in fake_quantizers)
    assert any(module.qscheme == torch.per_tensor_affine for module in fake_quantizers)
    assert any(module.qscheme == torch.per_tensor_symmetric for module in fake_quantizers)

    optimizer = torch.optim.SGD(prepared.parameters(), lr=0.01)
    weights_before = [parameter.detach().clone() for parameter in prepared.parameters()]
    loss = prepared(inputs).square().mean()
    loss.backward()
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in prepared.parameters()
    )
    optimizer.step()
    assert any(
        not torch.equal(before, after)
        for before, after in zip(weights_before, prepared.parameters())
    )

    converted = convert_quantized_model(prepared)
    assert not any(isinstance(module, FakeQuantizeBase) for module in converted.modules())
    assert any("quantize_per_tensor" in str(node.target) for node in converted.graph.nodes)
    with torch.no_grad():
        for batch_size in (1, 4):
            output = converted(inputs[:batch_size])
            assert output.shape == (batch_size, 10, 1, 1)
            assert torch.isfinite(output).all()
