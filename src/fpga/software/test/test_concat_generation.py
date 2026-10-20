"""Regression tests for concat descriptors and physical output allocations."""

import contextlib
import io
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from src.fpga.software.host.nnbaremetal.emit_headers import gen_exec_plan_header
from src.fpga.software.host.nnbaremetal.layout import _build_cpu_out_addrs
from src.fpga.software.host.nnbaremetal.model import (
    DependencyInfo, LayerDep, concat_output_elements,
)


class ConcatGenerationTest(unittest.TestCase):
    """Checks that existing parent metadata reaches the embedded descriptor."""

    def setUp(self) -> None:
        """Creates unequal-channel parents with square and short-row storage."""
        a = LayerDep(
            processor="vta", reshape_info="im2row",
            offset_a=0, scale_a=1.0, offset_b=0, scale_b=1.0,
            offset_u=0, scale_u=1.0, offset_v=0, scale_v=1.0,
            tensor_ch=17, tensor_h=1, tensor_w=19,
            kh=1, kw=1, sh=1, sw=1, pad=(0, 0, 0, 0),
            out_ch=17, out_h=1, out_w=19, offset_c=0, scale_c=1.0,
            scale=1.0, nb_inp=1, deps=["image"],
        )
        b = replace(a, reshape_info="int32", out_ch=3)
        concat = replace(a, processor="concat", reshape_info="False",
                         out_ch=20, nb_inp=2, deps=["QLinearConv1", "MaxPool2"])
        self.info = DependencyInfo(
            execution_order=[(2, "concat", "QLinearConcat3")],
            layers={"QLinearConv1": a, "MaxPool2": b, "QLinearConcat3": concat},
            image_h=19, image_w=17, output_layer="QLinearConcat3",
        )

    def test_descriptor_uses_parent_channels_and_storage(self) -> None:
        """Emits 17/3 channels and 32/19 physical rows without CSV extensions."""
        with tempfile.TemporaryDirectory() as directory:
            header = Path(directory) / "nn_exec_plan.h"
            with contextlib.redirect_stdout(io.StringIO()):
                gen_exec_plan_header(
                    self.info, [], 0, directory, str(header), block_size=16,
                    cpu_out={"QLinearConv1": 0x20000000, "MaxPool2": 0x20100000,
                             "QLinearConcat3": 0x30000000},
                )
            source = header.read_text()
        self.assertIn("{ 17u, 3u, 0u, 0u }", source)
        self.assertIn("{ 32u, 19u, 0u, 0u }", source)
        self.assertIn("1024u, 2,", source)

    def test_concat_allocation_uses_configured_block_size(self) -> None:
        """Allocates padded output, rather than logical H*W*C bytes."""
        concat = self.info.layers["QLinearConcat3"]
        for block, expected in [(8, 576), (16, 1024), (32, 1024)]:
            with self.subTest(block=block), tempfile.TemporaryDirectory() as directory:
                self.assertEqual(concat_output_elements(concat, block), expected)
                with contextlib.redirect_stdout(io.StringIO()):
                    _, _, scratch = _build_cpu_out_addrs(
                        self.info, [], 0, {}, directory, block_size=block,
                    )
                self.assertEqual(scratch[0][2], expected)

    def test_generator_rejects_inconsistent_output_channels(self) -> None:
        """Rejects stale or malformed metadata before emitting a descriptor."""
        self.info.layers["QLinearConcat3"].out_ch = 21
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "channel mismatch"):
                gen_exec_plan_header(
                    self.info, [], 0, directory, str(Path(directory) / "plan.h"),
                    cpu_out={"QLinearConcat3": 0x30000000},
                )


if __name__ == "__main__":
    unittest.main()
