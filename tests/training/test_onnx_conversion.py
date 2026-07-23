import os
import tempfile
import pytest
import torch
import torch.nn as nn
from src.training.quantization import prepare_qat_model, convert_quantized_model
from src.training.onnx_utils import convert_qdq_to_qlinear_onnx

class SimpleDummyConv(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(1, 4, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.head = nn.Conv2d(4, 2, kernel_size=28, stride=1)

    def forward(self, x):
        return self.head(self.relu(self.conv(x)))

def test_qdq_to_qlinear_conversion():
    model = SimpleDummyConv()
    example_inputs = torch.randn(16, 1, 28, 28)
    
    qat_model = prepare_qat_model(model, example_inputs)
    q_model = convert_quantized_model(qat_model)


    with tempfile.TemporaryDirectory() as tmp_dir:
        qdq_path = os.path.join(tmp_dir, "model_qdq.onnx")
        qlinear_path = os.path.join(tmp_dir, "model_qlinear.onnx")

        with torch.no_grad():
            torch.onnx.export(
                q_model,
                example_inputs,
                qdq_path,
                dynamo=True,
                opset_version=18
            )

        assert os.path.exists(qdq_path)

        convert_qdq_to_qlinear_onnx(qdq_path, qlinear_path)

        assert os.path.exists(qlinear_path)
