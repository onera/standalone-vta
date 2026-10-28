"""Executable characterization of the QDQ-to-QLinear conversion subset."""

from pathlib import Path
from typing import List, Optional
import warnings

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
    ("Conv", True, 0, 1.0, None),
    ("Conv", True, 7, 1.0, None),
    ("Add", True, 0, 1.0, None),
    ("Add", True, 7, 1.0, None),
    ("Relu", False, 7, 1.0, None),
    ("Relu", False, -128, 1.0, None),
    ("Relu", False, 0, 2.0, None),
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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        convert_qdq_to_qlinear_onnx(str(qdq_path), str(linear_path))
    retained_relu = (relu and zero_point != -128) or (
        operation == "Relu" and (zero_point != 0 or scale != 1.0)
    )
    conversion_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert len(conversion_warnings) == int(retained_relu)
    if retained_relu:
        assert "keeping float ReLU" in str(conversion_warnings[0].message)
        assert "QDQ" in str(conversion_warnings[0].message)
    converted = onnx.load(linear_path)
    onnx.checker.check_model(converted, full_check=True)
    assert converted.graph.input[0].name == "input"
    assert converted.graph.output[0].name == "output"
    assert converted.graph.input[0].type.tensor_type.elem_type == TensorProto.INT8
    assert converted.graph.output[0].type.tensor_type.elem_type == TensorProto.INT8
    if operation in ("Add", "Concat") and (not relu or zero_point == -128):
        assert any(n.domain == "com.microsoft" for n in converted.graph.node)
    if relu:
        assert any(n.op_type == "Relu" for n in converted.graph.node) == (zero_point != -128)
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
    ("MaxPool", False, 0, 2.0, None),
    ("Flatten", False, 0, 2.0, None),
    ("Conv", False, 0, 0.25, 0.5),
])
@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="Known conversion limits: missing requantization or bias rounding",
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


@pytest.mark.parametrize("operation", ["Conv", "Add"])
@pytest.mark.parametrize("shared_tensor", ["result", "activated"])
def test_relu_rewrite_preserves_shared_outputs(
    tmp_path: Path, operation: str, shared_tensor: str,
) -> None:
    """Preserves both activation semantics and graph outputs with extra users.

    Args:
        tmp_path: Per-test artifact directory.
        operation: Arithmetic operator before the ReLU.
        shared_tensor: Pre- or post-ReLU tensor also exposed as a graph output.
    """
    model = _make_model(operation, True, -128, 1.0)
    model.graph.output.append(helper.make_tensor_value_info(
        shared_tensor, TensorProto.FLOAT, [1, 1, 1, 4],
    ))
    original_path, converted_path = tmp_path / "original.onnx", tmp_path / "converted.onnx"
    onnx.save(model, original_path)
    with pytest.warns(UserWarning, match="keeping float ReLU 'activation'"):
        convert_qdq_to_qlinear_onnx(str(original_path), str(converted_path))
    converted = onnx.load(converted_path)
    onnx.checker.check_model(converted, full_check=True)
    assert any(n.op_type == "Relu" for n in converted.graph.node)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.intra_op_num_threads = 1
    original_session = ort.InferenceSession(str(original_path), options, providers=["CPUExecutionProvider"])
    converted_session = ort.InferenceSession(str(converted_path), options, providers=["CPUExecutionProvider"])
    values = np.array([-4, -1, 1, 4], np.float32).reshape(1, 1, 1, 4)
    expected, expected_shared = original_session.run(None, {"x": values})
    actual, actual_shared = converted_session.run(None, {"input": values.astype(np.int8)})
    np.testing.assert_array_equal(actual.astype(np.float32) + 128, expected)
    np.testing.assert_array_equal(actual_shared, expected_shared)


@pytest.mark.parametrize("operation", ["Conv", "Add"])
def test_relu_rewrite_requires_constant_output_parameters(tmp_path: Path, operation: str) -> None:
    """Keeps the float activation when output scale cannot be resolved locally.

    Args:
        tmp_path: Per-test artifact directory.
        operation: Arithmetic operator before the ReLU.
    """
    model = _make_model(operation, True, -128, 1.0)
    # Resolve scale at runtime through Identity, rather than a named initializer.
    for node in model.graph.node:
        if node.op_type == "QuantizeLinear" and node.output[0] == "yq":
            node.input[1] = "runtime_scale"
    model.graph.node.insert(2, helper.make_node("Identity", ["ys"], ["runtime_scale"]))
    original_path, converted_path = tmp_path / "original.onnx", tmp_path / "converted.onnx"
    onnx.save(model, original_path)
    with pytest.warns(UserWarning, match="keeping float ReLU 'activation'"):
        convert_qdq_to_qlinear_onnx(str(original_path), str(converted_path))
    converted = onnx.load(converted_path)
    onnx.checker.check_model(converted, full_check=True)
    assert any(n.op_type == "Relu" for n in converted.graph.node)
    assert any(n.op_type == operation for n in converted.graph.node)


@pytest.mark.parametrize("per_channel", [False, True])
def test_retained_relu_preserves_padding_and_quantization_metadata(
    tmp_path: Path, per_channel: bool,
) -> None:
    """Checks that cleanup does not invalidate a rejected convolution rewrite.

    Args:
        tmp_path: Per-test artifact directory.
        per_channel: Whether to use vector output scales/zero-points.
    """
    model = _make_model("Conv", True, 0, 0.5)
    scales = np.array([0.5, 1.0], np.float32) if per_channel else np.array(0.5, np.float32)
    zeros = np.array([-128, -128], np.int8) if per_channel else np.array(0, np.int8)
    replacements = {
        "other": np.ones((2, 1, 1, 3), np.int8), "ys": scales, "yz": zeros,
    }
    for initializer in model.graph.initializer:
        if initializer.name in replacements:
            initializer.CopyFrom(numpy_helper.from_array(replacements[initializer.name], initializer.name))
    model.graph.output[0].type.tensor_type.shape.dim[1].dim_value = 2
    for node in model.graph.node:
        if node.op_type == "Conv":
            node.attribute.append(helper.make_attribute("auto_pad", "SAME_UPPER"))
        elif per_channel and len(node.input) > 1 and node.input[1] == "ys":
            node.attribute.append(helper.make_attribute("axis", 1))
    original_path, converted_path = tmp_path / "original.onnx", tmp_path / "converted.onnx"
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, original_path)
    with pytest.warns(UserWarning, match="keeping float ReLU 'activation'"):
        convert_qdq_to_qlinear_onnx(str(original_path), str(converted_path))
    converted = onnx.load(converted_path)
    onnx.checker.check_model(converted, full_check=True)
    assert any(n.op_type == "Relu" for n in converted.graph.node)
    conv = next(n for n in converted.graph.node if n.op_type == "Conv")
    assert helper.get_attribute_value(next(a for a in conv.attribute if a.name == "auto_pad")) == b"SAME_UPPER"
    if per_channel:
        assert list(next(i for i in converted.graph.initializer if i.name == "ys").dims) == [2]
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.intra_op_num_threads = 1
    original_session = ort.InferenceSession(str(original_path), options, providers=["CPUExecutionProvider"])
    converted_session = ort.InferenceSession(str(converted_path), options, providers=["CPUExecutionProvider"])
    values = np.array([-4, -1, 1, 4], np.float32).reshape(1, 1, 1, 4)
    expected = original_session.run(None, {"x": values})[0]
    actual_q = converted_session.run(None, {"input": values.astype(np.int8)})[0]
    actual = (actual_q.astype(np.float32) - zeros.reshape(1, -1, 1, 1)) * scales.reshape(1, -1, 1, 1)
    np.testing.assert_array_equal(actual, expected)
