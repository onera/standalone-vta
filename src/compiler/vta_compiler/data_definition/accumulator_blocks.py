"""Block-tiled accumulator DRAM-init export.

The raw ``accumulator{name}.bin`` / ``add_accumulator{name}.bin`` are row-major
(Ah x Bw) matrices. The LACC SRAM is block-tiled, so a byte-for-byte DRAM load
of a raw matrix leaves the trailing SRAM region uninitialized and mislays the
bias. baremetal and the post-synth flow cannot re-block at load time, so the
compiler also writes the block-tiled siblings (``..._block.bin``) that they load
directly into DRAM.
"""

import os


def export_accumulator_blocks(output_dir, name, X_blocks, Y_blocks):
    """Write the block-tiled accumulator bins next to the raw matrices."""
    x_path = os.path.join(output_dir, "accumulator" + name + "_block.bin")
    y_path = os.path.join(output_dir, "add_accumulator" + name + "_block.bin")
    with open(x_path, "wb") as f:
        for block in X_blocks:
            block.tofile(f)
    with open(y_path, "wb") as f:
        for block in Y_blocks:
            block.tofile(f)
