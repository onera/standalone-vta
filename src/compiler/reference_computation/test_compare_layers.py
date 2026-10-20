"""Tests for dtype-aware, bit-exact layer dump comparison."""

import contextlib
import io
import unittest

import numpy as np

from src.compiler.reference_computation.compare_layers import compare_layer_outputs


class FloatLayerComparisonTest(unittest.TestCase):
    """Checks fractional, nonfinite, and signed-zero comparison behavior."""

    def compare(self, reference: np.ndarray, simulated: np.ndarray) -> bool:
        """Runs the comparator while capturing its diagnostic report.

        Args:
            reference: Reference NCHW array.
            simulated: Simulator NCHW array.

        Returns:
            Comparator result, with diagnostics suppressed during unit tests.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            return compare_layer_outputs(reference, simulated, "ConvTranspose2", 1)

    def test_equal_float32_values_match(self) -> None:
        """Accepts identical fractional float32 tensors."""
        values = np.array([[[[-0.25, 0.125, 1.5]]]], dtype=np.float32)
        self.assertTrue(self.compare(values, values.copy()))

    def test_one_ulp_difference_fails(self) -> None:
        """Rejects an adjacent float32 value even below integer precision."""
        values = np.array([[[[0.125]]]], dtype=np.float32)
        adjacent = np.nextafter(values, np.float32(np.inf))
        self.assertFalse(self.compare(values, adjacent))

    def test_signed_zero_difference_fails(self) -> None:
        """Checks signed zero by its representation, not numerical equality."""
        positive = np.array([[[[0.0]]]], dtype=np.float32)
        negative = np.array([[[[-0.0]]]], dtype=np.float32)
        self.assertFalse(self.compare(positive, negative))

    def test_nonfinite_bit_patterns(self) -> None:
        """Accepts identical NaN payloads and rejects a different payload."""
        bits = np.array([[[[0x7FC00001, 0x7F800000]]]], dtype=np.uint32)
        values = bits.view(np.float32)
        self.assertTrue(self.compare(values, values.copy()))
        other = bits.copy()
        other.flat[0] = 0x7FC00002
        self.assertFalse(self.compare(values, other.view(np.float32)))

    def test_dtype_and_shape_mismatches_fail(self) -> None:
        """Rejects incompatible dump interpretations without broadcasting."""
        values = np.array([[[[0.5]]]], dtype=np.float32)
        self.assertFalse(self.compare(values, values.astype(np.float64)))
        self.assertFalse(self.compare(values, values.reshape(1)))


if __name__ == "__main__":
    unittest.main()
