"""Checks ONNX comparison statistics when fewer samples are available."""

import logging
from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.training.onnx_utils import verify_onnx


def test_comparison_uses_actual_sample_count(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """Checks MSE denominators using deterministic runtime output offsets.

    Args:
        monkeypatch: Fixture replacing graph loading and runtime sessions.
        caplog: Fixture capturing comparison metrics and exhaustion warnings.
    """
    class OffsetSession:
        """Runtime stand-in adding a known offset to each output value."""

        def __init__(self, path: str) -> None:
            """Sets the output offset from the model path.

            Args:
                path: Model identifier selecting the comparison offset.
            """
            self.offset = 2.0 if path == "qdq" else 3.0

        def get_inputs(self) -> List[Any]:
            """Returns metadata for a float input.

            Returns:
                Single input descriptor.
            """
            return [SimpleNamespace(name="input", type="tensor(float)")]

        def run(self, outputs: Any, inputs: Dict[str, np.ndarray]) -> List[np.ndarray]:
            """Adds a constant offset to the identity model's output.

            Args:
                outputs: Requested outputs (unused).
                inputs: Input tensors indexed by name.

            Returns:
                Output tensor containing the known offset.
            """
            return [inputs["input"] + self.offset]

    monkeypatch.setattr(ort, "InferenceSession", OffsetSession)
    graph = SimpleNamespace(
        initializer=[], node=[SimpleNamespace(input=["unused"] * 8)],
    )
    monkeypatch.setattr(onnx, "load", lambda path: SimpleNamespace(graph=graph))
    # A parameter lets verification resolve the device; weights preserve inputs.
    model = nn.Linear(2, 2, bias=False)
    with torch.no_grad():
        model.weight.copy_(torch.eye(2))
    loader = DataLoader(TensorDataset(
        torch.tensor([[1.0, 0.0], [0.0, 1.0]]), torch.tensor([0, 1]),
    ), batch_size=2)
    with caplog.at_level(logging.INFO):
        verify_onnx(model, "qdq", "qlinear", {"test": loader}, num_samples=5)

    assert "requested=5 processed=2" in caplog.text
    assert "Processed samples=2" in caplog.text
    assert "QDQ vs PyTorch: max_abs_diff=2 mse=4" in caplog.text
    assert "QLinear vs PyTorch: max_abs_diff=3 mse=9" in caplog.text


def test_comparison_rejects_empty_test_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures empty input cannot produce misleading NaN comparison results.

    Args:
        monkeypatch: Fixture replacing unused graph loading and runtime sessions.
    """
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="input", type="tensor(float)")],
    )
    monkeypatch.setattr(ort, "InferenceSession", lambda path: session)
    graph = SimpleNamespace(initializer=[], node=[SimpleNamespace(input=["unused"] * 8)])
    monkeypatch.setattr(onnx, "load", lambda path: SimpleNamespace(graph=graph))
    with pytest.raises(ValueError, match="No test samples"):
        verify_onnx(nn.Linear(2, 2), "qdq", "qlinear", {"test": []}, num_samples=5)
