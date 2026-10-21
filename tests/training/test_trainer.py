"""Checks that validation does not calibrate a QAT model."""

from typing import Dict, List

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from torchao.quantization.pt2e.fake_quantize import FakeQuantizeBase

from src.training.engine import train_model
from src.training.quantization import prepare_qat_model
from src.training.solver.loss import FlattenCrossEntropyLoss


def test_validation_freezes_observers_and_training_resumes_updates() -> None:
    """Checks quantization buffers and fake quantization over two full epochs."""
    torch.manual_seed(0)
    model = nn.Sequential(nn.Conv2d(1, 2, kernel_size=4))
    inputs = torch.randn(4, 1, 4, 4)
    inputs[2:] *= 10
    prepared = prepare_qat_model(model, inputs[:2], max_batch=4)
    fake_quantizers = [
        module for module in prepared.modules()
        if isinstance(module, FakeQuantizeBase)
    ]
    assert fake_quantizers
    loaders = {
        "train": DataLoader(TensorDataset(inputs, torch.zeros(4, dtype=torch.long)), batch_size=2),
        # Deliberately different validation ranges would alter active observers.
        "valid": DataLoader(
            TensorDataset(inputs[:2] * 100, torch.zeros(2, dtype=torch.long)), batch_size=2
        ),
    }
    before: Dict[str, torch.Tensor] = {}
    updates: List[bool] = []

    def check_before_forward(module: nn.Module, args: object) -> None:
        """Snapshots quantization buffers and verifies the phase flags.

        Args:
            module: Prepared QAT graph being executed.
            args: Forward arguments supplied by PyTorch.
        """
        training_phase = len(updates) % 3 < 2
        for fake_quantizer in fake_quantizers:
            assert bool(fake_quantizer.observer_enabled.item()) == training_phase
            assert bool(fake_quantizer.fake_quant_enabled.item())
        before.clear()
        before.update({
            name: buffer.clone() for name, buffer in module.named_buffers()
        })

    def check_after_forward(module: nn.Module, args: object, output: torch.Tensor) -> None:
        """Checks that validation preserves all quantization buffers.

        Args:
            module: Prepared QAT graph that was executed.
            args: Forward arguments supplied by PyTorch.
            output: Output tensor produced by the graph.
        """
        changed = any(
            not torch.equal(before[name], buffer)
            for name, buffer in module.named_buffers()
        )
        updates.append(changed)
        assert torch.isfinite(output).all()

    pre_hook = prepared.register_forward_pre_hook(check_before_forward)
    post_hook = prepared.register_forward_hook(check_after_forward)
    try:
        train_model(
            prepared,
            loaders,
            FlattenCrossEntropyLoss(),
            torch.optim.SGD(prepared.parameters(), lr=0.01),
            device="cpu",
            num_epochs=2,
        )
    finally:
        pre_hook.remove()
        post_hook.remove()

    assert updates == [True, True, False, True, True, False]
    assert all(bool(module.fake_quant_enabled.item()) for module in fake_quantizers)
