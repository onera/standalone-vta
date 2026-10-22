"""Executable characterization of the QDQ-to-QLinear conversion subset."""

from pathlib import Path
from typing import List, Optional

import numpy as np
import onnx
import onnxruntime as ort
import pytest
from onnx import TensorProto, helper, numpy_helper

from src.training.onnx_utils import convert_qdq_to_qlinear_onnx


def _make_model(
    operation: str, relu: bool, zero_point: int, scale: float,
    bias: Optional[float] = None,
) -> onnx.ModelProto:
    """Builds a scalar-quantized motif with float external boundaries.

    Args:
        operation: Float operator enclosed by DQ and Q nodes.
        relu: Whether Conv or Add is followed by a ReLU.
        zero_point: Output INT8 zero-point.
        scale: Output scale; all input scales are one.
        bias: Optional float convolution bias.

    Returns:
        Checked model with one float input and one float output.
    """
    constants = {
        "xs": np.array(1, np.float32), "xz": np.array(0, np.int8),
        "ys": np.array(scale, np.float32), "yz": np.array(zero_point, np.int8),
    }
    nodes: List[onnx.NodeProto] = [
        helper.make_node("QuantizeLinear", ["x", "xs", "xz"], ["xq"]),
        helper.make_node("DequantizeLinear", ["xq", "xs", "xz"], ["xd"]),
    ]
    inputs = ["xd"]
    attributes = {}
    shape = [1, 1, 1, 4]
    if operation in ("Conv", "Add", "Concat"):
        constants["other"] = np.ones((1, 1, 1, 1) if operation == "Conv" else shape, np.int8)
        nodes.append(helper.make_node("DequantizeLinear", ["other", "xs", "xz"], ["other_dq"]))
        inputs.append("other_dq")
    if bias is not None:
        constants["bias"] = np.array([bias], np.float32)
        inputs.append("bias")
    if operation == "Concat":
        attributes = {"axis": 1}
        shape = [1, 2, 1, 4]
    elif operation == "MaxPool":
        attributes = {"kernel_shape": [1, 2], "strides": [1, 2]}
        shape = [1, 1, 1, 2]
    elif operation == "Flatten":
        attributes = {"axis": 1}
        shape = [1, 4]
    nodes.append(helper.make_node(operation, inputs, ["result"], name="operation", **attributes))
    if relu:
        nodes.append(helper.make_node("Relu", ["result"], ["activated"], name="activation"))
    nodes.extend([
        helper.make_node("QuantizeLinear", ["activated" if relu else "result", "ys", "yz"], ["yq"]),
        helper.make_node("DequantizeLinear", ["yq", "ys", "yz"], ["y"]),
    ])
    graph = helper.make_graph(
        nodes, "conversion_semantics",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 1, 1, 4])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, shape)],
        [numpy_helper.from_array(value, name) for name, value in constants.items()],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)], ir_version=10)
    onnx.checker.check_model(model)
    return model


@pytest.mark.parametrize("operation,relu,zero_point,scale,bias", [
    ("Conv", False, 0, 1.0, None),
    ("Conv", False, 0, 1.0, 1.0),
    ("Add", False, 0, 1.0, None),
    ("Concat", False, 0, 1.0, None),
    ("MaxPool", False, 0, 1.0, None),
    ("Flatten", False, 0, 1.0, None),
    ("Relu", False, 0, 1.0, None),
    ("Conv", True, -128, 1.0, None),
    ("Add", True, -128, 1.0, None),
])
def test_conversion_preserves_supported_examples(
    tmp_path: Path, operation: str, relu: bool, zero_point: int,
    scale: float, bias: Optional[float],
) -> None:
    """Checks graph validity, external ABI and exact outputs on controlled values.

    Args:
        tmp_path: Per-test artifact directory supplied by pytest.
        operation: Float operator to convert.
        relu: Whether to append an activation before quantization.
        zero_point: Output zero-point.
        scale: Output quantization scale.
        bias: Optional float convolution bias.
    """
    _compare_conversion(tmp_path, operation, relu, zero_point, scale, bias)


def _compare_conversion(
    path: Path, operation: str, relu: bool, zero_point: int,
    scale: float, bias: Optional[float],
) -> None:
    """Asserts equivalent real outputs after accounting for the INT8 boundaries.

    Args:
        path: Directory for generated ONNX graphs.
        operation: Operator enclosed by quantization boundaries.
        relu: Whether to append a ReLU.
        zero_point: Output zero-point.
        scale: Output quantization scale.
        bias: Optional float convolution bias.
    """
    qdq_path, linear_path = path / "qdq.onnx", path / "qlinear.onnx"
    onnx.save(_make_model(operation, relu, zero_point, scale, bias), qdq_path)
    convert_qdq_to_qlinear_onnx(str(qdq_path), str(linear_path))
    converted = onnx.load(linear_path)
    onnx.checker.check_model(converted, full_check=True)
    assert converted.graph.input[0].name == "input"
    assert converted.graph.output[0].name == "output"
    assert converted.graph.input[0].type.tensor_type.elem_type == TensorProto.INT8
    assert converted.graph.output[0].type.tensor_type.elem_type == TensorProto.INT8
    if operation in ("Add", "Concat"):
        assert any(n.domain == "com.microsoft" for n in converted.graph.node)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    original = ort.InferenceSession(str(qdq_path), options, providers=["CPUExecutionProvider"])
    converted_session = ort.InferenceSession(str(linear_path), options, providers=["CPUExecutionProvider"])
    values = np.array([-4, -1, 1, 4], np.float32).reshape(1, 1, 1, 4)
    expected = original.run(None, {"x": values})[0]
    # Input scale is 1 and zero-point is 0, so these integer inputs are exact.
    actual_q = converted_session.run(None, {"input": values.astype(np.int8)})[0]
    actual = (actual_q.astype(np.float32) - zero_point) * np.float32(scale)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("operation,relu,zero_point,scale,bias", [
    ("Conv", True, 0, 1.0, None),
    ("Conv", True, 7, 1.0, None),
    ("Add", True, 0, 1.0, None),
    ("Add", True, 7, 1.0, None),
    ("MaxPool", False, 0, 2.0, None),
    ("Flatten", False, 0, 2.0, None),
    ("Relu", False, 7, 1.0, None),
    ("Relu", False, -128, 1.0, None),
    ("Conv", False, 0, 0.25, 0.5),
])
@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Known conversion limits: ReLU removal, missing requantization or bias rounding",
)
def test_conversion_known_numerical_limits(
    tmp_path: Path, operation: str, relu: bool, zero_point: int,
    scale: float, bias: Optional[float],
) -> None:
    """Records expected equivalence failures until conversion is hardened.

    Args:
        tmp_path: Per-test artifact directory supplied by pytest.
        operation: Operator whose unsupported case is demonstrated.
        relu: Whether the failing case removes a ReLU.
        zero_point: Output zero-point.
        scale: Output scale, which may differ from the input scale.
        bias: Optional bias not exactly representable in accumulator units.
    """
    _compare_conversion(tmp_path, operation, relu, zero_point, scale, bias)
