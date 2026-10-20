"""Unit tests for the shared embedded quantized arithmetic contract."""

import sys
import unittest
from pathlib import Path

import numpy as np
from onnx import helper

COMPILER_DIR = Path(__file__).resolve().parents[1]
if str(COMPILER_DIR) not in sys.path:
    sys.path.append(str(COMPILER_DIR))

from nn_compiler.nodes.node_cpu import convtranspose, qlinearconcat
from src.compiler.utils.numpy_implementation import (
    NumPyReferenceEngine,
    float32_reciprocal,
    requantize_accumulator,
    round_and_saturate,
)


class QuantizedArithmeticContractTest(unittest.TestCase):
    """Checks rounding, saturation, and operator arithmetic edge cases."""

    def setUp(self) -> None:
        """Creates an engine instance for testing pure private operators."""
        self.engine = object.__new__(NumPyReferenceEngine)
        self.engine._last_integer_accumulator = np.empty(0, dtype=np.int32)

    def test_float32_reciprocal_and_nearest_even(self) -> None:
        """Uses float32 reciprocals and rounds positive and negative ties evenly."""
        self.assertEqual(float32_reciprocal(np.float32(0.25)), np.float32(4.0))
        scaled = np.array([-2.5, -1.5, 1.5, 2.5], dtype=np.float32)
        got = round_and_saturate(scaled, 0)
        np.testing.assert_array_equal(got, np.array([-2, -2, 2, 2], dtype=np.int8))

    def test_round_and_saturate_clamps_int8(self) -> None:
        """Clamps values after rounding and zero-point addition."""
        scaled = np.array([-1000.0, -0.5, 0.5, 1000.0], dtype=np.float32)
        got = round_and_saturate(scaled, np.int8(3))
        np.testing.assert_array_equal(got, np.array([-128, 3, 3, 127], dtype=np.int8))

    def test_rounding_neighbors_of_half_integers(self) -> None:
        """Distinguishes ties from adjacent representable float32 values."""
        ties = np.array([-2.5, -1.5, 1.5, 2.5], dtype=np.float32)
        below = np.nextafter(ties, np.float32(-np.inf))
        above = np.nextafter(ties, np.float32(np.inf))
        np.testing.assert_array_equal(
            round_and_saturate(below, 0), np.array([-3, -2, 1, 2], dtype=np.int8)
        )
        np.testing.assert_array_equal(
            round_and_saturate(above, 0), np.array([-2, -1, 2, 3], dtype=np.int8)
        )

    def test_qlinear_conv_preserves_integer_accumulator(self) -> None:
        """Checks bias, centered input padding, and output requantization."""
        node = helper.make_node(
            "QLinearConv", [], ["y"], pads=[1, 1, 0, 0], strides=[1, 1]
        )
        inputs = [
            np.array([[[[3]]]], dtype=np.int8), np.array(0.5, dtype=np.float32),
            np.array(1, dtype=np.int8),
            np.full((1, 1, 2, 2), 4, dtype=np.int8),
            np.array(0.25, dtype=np.float32), np.array(1, dtype=np.int8),
            np.array(0.5, dtype=np.float32), np.array(-1, dtype=np.int8),
            np.array([4], dtype=np.int32),
        ]
        got = self.engine._qlinear_conv(node, inputs)
        # Only the real input contributes: (3-1)*(4-1)+bias=10.
        # 10*0.25=2.5 -> nearest-even 2, then output zero-point -1 -> 1.
        np.testing.assert_array_equal(
            self.engine._last_integer_accumulator, np.array([[[[10]]]], dtype=np.int32)
        )
        np.testing.assert_array_equal(got, np.array([[[[1]]]], dtype=np.int8))

    def test_accumulator_requantization_uses_float32_multiplier(self) -> None:
        """Matches the VTA double-accumulator rescale contract."""
        accumulator = np.array([-5, -3, 3, 5, 1000], dtype=np.int32)
        got = requantize_accumulator(accumulator, np.float32(0.5), np.int8(-1))
        np.testing.assert_array_equal(got, np.array([-3, -3, 1, 1, 127], dtype=np.int8))

    def test_qlinear_add_precomputes_two_ratios(self) -> None:
        """Reproduces the QYolo half-tie with the selected embedded contract."""
        inputs = [
            np.array([[[[-39]]]], dtype=np.int8),
            np.array(0.011274928227066994, dtype=np.float32),
            np.array(-128, dtype=np.int8),
            np.array([[[[26]]]], dtype=np.int8),
            np.array(0.011537629179656506, dtype=np.float32),
            np.array(-128, dtype=np.int8),
            np.array(0.01993020437657833, dtype=np.float32),
            np.array(-128, dtype=np.int8),
        ]
        got = self.engine._qlinear_add(inputs)
        np.testing.assert_array_equal(got, np.array([[[[12]]]], dtype=np.int8))

    def test_qlinear_mul_uses_integer_product(self) -> None:
        """Computes the scalar multiply accumulator before one rescale."""
        inputs = [
            np.array([[[[-5, 5]]]], dtype=np.int8),
            np.array(0.5, dtype=np.float32),
            np.array(-1, dtype=np.int8),
            np.array([3], dtype=np.int8),
            np.array(0.25, dtype=np.float32),
            np.array(1, dtype=np.int8),
            np.array(0.25, dtype=np.float32),
            np.array(0, dtype=np.int8),
        ]
        got = self.engine._qlinear_mul(inputs)
        np.testing.assert_array_equal(got, np.array([[[[-4, 6]]]], dtype=np.int8))
        np.testing.assert_array_equal(
            self.engine._last_integer_accumulator,
            np.array([[[[-8, 12]]]], dtype=np.int32),
        )

    def test_quantize_and_dequantize_are_float32(self) -> None:
        """Checks reciprocal quantization and exact float32 dequantization."""
        quantized = self.engine._quantize_linear(
            [
                np.array([[[[-0.625, 0.625]]]], dtype=np.float32),
                np.array(0.25, dtype=np.float32),
                np.array(1, dtype=np.int8),
            ]
        )
        np.testing.assert_array_equal(quantized, np.array([[[[-1, 3]]]], dtype=np.int8))

        node = helper.make_node("DequantizeLinear", ["x", "s", "z"], ["y"])
        dequantized = self.engine._dequantize_linear(
            node,
            [
                np.array([[[[-1, 3]]]], dtype=np.int8),
                np.array(0.25, dtype=np.float32),
                np.array(1, dtype=np.int8),
            ],
        )
        np.testing.assert_array_equal(
            dequantized.view(np.uint32),
            np.array([[[[-0.5, 0.5]]]], dtype=np.float32).view(np.uint32),
        )

    def test_qlinear_concat_requantizes_each_branch_before_concat(self) -> None:
        """Uses one precomputed multiplier per concatenated input branch."""
        node = helper.make_node(
            "QLinearConcat",
            ["ys", "yz", "a", "as", "az", "b", "bs", "bz"],
            ["y"],
            domain="com.microsoft",
            axis=1,
        )
        got = self.engine._qlinear_concat(
            node,
            [
                np.array(0.5, dtype=np.float32),
                np.array(0, dtype=np.int8),
                np.array([[[[2.0]]]], dtype=np.int8),
                np.array(0.25, dtype=np.float32),
                np.array(0, dtype=np.int8),
                np.array([[[[2.0]]]], dtype=np.int8),
                np.array(1.0, dtype=np.float32),
                np.array(0, dtype=np.int8),
            ],
        )
        np.testing.assert_array_equal(got, np.array([[[[1]], [[4]]]], dtype=np.int8))

    def test_qlinear_concat_unequal_channels(self) -> None:
        """Requantizes unequal, sub-block channel branches without extra channels."""
        node = helper.make_node("QLinearConcat", [], ["y"], axis=1)
        a = np.full((1, 3, 1, 19), 5, dtype=np.int8)
        b = np.full((1, 17, 1, 19), -3, dtype=np.int8)
        got = self.engine._qlinear_concat(node, [
            np.array(0.5, np.float32), np.array(-1, np.int8),
            a, np.array(0.25, np.float32), np.array(1, np.int8),
            b, np.array(1.0, np.float32), np.array(-1, np.int8),
        ])
        expected = np.concatenate((
            np.full_like(a, 1), np.full_like(b, -5)
        ), axis=1)
        np.testing.assert_array_equal(got, expected)

    def test_compiler_concat_shape_validation(self) -> None:
        """Accepts Inception channels and rejects non-channel shape mismatches."""
        shapes = [[1, 64, 4, 4], [1, 128, 4, 4], [1, 32, 4, 4], [1, 32, 4, 4]]
        params = {"ys": np.array(0.5, np.float32), "yz": np.array(-7, np.int8)}
        inputs = [{"name": "ys", "shape": []}, {"name": "yz", "shape": []}]
        mapping = {}
        for p, shape in enumerate(shapes):
            mapping[f"x{p}"] = p
            params[f"s{p}"] = np.array(0.25, np.float32)
            params[f"z{p}"] = np.array(-3, np.int8)
            inputs.extend([
                {"name": f"x{p}", "shape": shape},
                {"name": f"s{p}", "shape": []},
                {"name": f"z{p}", "shape": []},
            ])
        node = {"op_type": "QLinearConcat", "inputs": inputs,
                "outputs": [{"name": "y", "shape": [1, 256, 4, 4]}],
                "attributes": {"axis": 1}}
        info = qlinearconcat(node, params, mapping, {}, filename="InceptionConcat")
        self.assertEqual(info["output_shape"], [1, 256, 4, 4])
        self.assertEqual(info["input_shape"], shapes[0])
        for dimension in (0, 2, 3):
            with self.subTest(dimension=dimension):
                original = shapes[1][dimension]
                shapes[1][dimension] += 1
                with self.assertRaises(ValueError):
                    qlinearconcat(node, params, mapping, {}, filename="InvalidConcat")
                shapes[1][dimension] = original
        node["outputs"][0]["shape"][1] = 255
        with self.assertRaises(ValueError):
            qlinearconcat(node, params, mapping, {}, filename="WrongOutputConcat")

    def test_maxpool_keeps_quantized_domain_and_negative_padding(self) -> None:
        """Pads with int8 minimum so padding cannot win a maximum."""
        node = helper.make_node(
            "MaxPool",
            ["x"],
            ["y"],
            kernel_shape=[2, 2],
            strides=[1, 1],
            pads=[1, 1, 0, 0],
        )
        values = np.array([[[[-8, -7], [-6, -5]]]], dtype=np.int8)
        got = self.engine._max_pool(node, [values])
        np.testing.assert_array_equal(got, np.array([[[[-8, -7], [-6, -5]]]], dtype=np.int8))

    def test_convtranspose_supported_subset_uses_float32(self) -> None:
        """Runs the group-one, unit-dilation, symmetric-stride subset."""
        node = helper.make_node(
            "ConvTranspose",
            ["x", "w", "b"],
            ["y"],
            kernel_shape=[2, 2],
            strides=[1, 1],
            pads=[0, 0, 0, 0],
        )
        got = self.engine._conv_transpose(
            node,
            [
                np.array([[[[1.0]]]], dtype=np.float32),
                np.array([[[[1.0, 2.0], [3.0, 4.0]]]], dtype=np.float32),
                np.array([0.5], dtype=np.float32),
            ],
        )
        expected = np.array([[[[1.5, 2.5], [3.5, 4.5]]]], dtype=np.float32)
        np.testing.assert_array_equal(got.view(np.uint32), expected.view(np.uint32))

    def test_compiler_rejects_unsupported_convtranspose_variants(self) -> None:
        """Rejects variants that fsim and the embedded runtime cannot reproduce."""
        base_node = {
            "op_type": "ConvTranspose",
            "inputs": [
                {"name": "x", "shape": [1, 1, 2, 2]},
                {"name": "w", "shape": [1, 1, 2, 2]},
            ],
            "outputs": [{"name": "y", "shape": [1, 1, 3, 3]}],
            "attributes": {
                "kernel_shape": [2, 2],
                "strides": [1, 1],
                "pads": [0, 0, 0, 0],
            },
        }
        variants = {
            "group": {"group": 2},
            "dilation": {"dilations": [2, 1]},
            "output_padding": {"output_padding": [1, 0]},
            "asymmetric_stride": {"strides": [2, 1]},
        }
        for name, attributes in variants.items():
            node = {
                **base_node,
                "attributes": {**base_node["attributes"], **attributes},
            }
            with self.subTest(name=name), self.assertRaises(ValueError):
                convtranspose(
                    node=node,
                    param={"w": np.ones((1, 1, 2, 2), dtype=np.float32)},
                    node_mapping={"x": 0},
                    node_info={},
                    filename="ConvTransposeValidation",
                )


if __name__ == "__main__":
    unittest.main()
