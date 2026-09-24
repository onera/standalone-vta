# CONVOLUTION LOWERING: GEOMETRY, COST AND FIT
# --------------------------------------------
# Shared between the two halves of the compiler. nn_compiler decides per layer
# which lowering to emit and vta_compiler then emits it, so both have to reach
# the same verdict from the same inputs: if nn_compiler emits a CONV section
# that vta_compiler cannot lower, the build fails late with a geometry error
# instead of quietly using im2row.
#
# Only the decision lives here. Emitting the instructions is vta_compiler's
# job (operations_definition/direct_conv.py).

# Instruction field widths the emitted values have to fit in (ISA.scala /
# structures.py). Overflowing one silently truncates the field, so every value
# derived from the convolution geometry is range-checked against them.
_PAD_MAX = (1 << 4) - 1     # M_PAD_BITS
_ITER_MAX = (1 << 14) - 1   # C_ITER_BITS   (loop_out / loop_in)
_AIDX_MAX = (1 << 11) - 1   # C_AIDX_BITS   (acc index + factors)
_IIDX_MAX = (1 << 11) - 1   # C_IIDX_BITS   (inp index + factors)
_WIDX_MAX = (1 << 10) - 1   # C_WIDX_BITS   (wgt index + factors)
_SIZE_MAX = (1 << 16) - 1   # M_SIZE_BITS   (x_size / y_size)


def direct_conv_work_ratio(C, kh, kw, block_size=16):
    """GEMM work under the direct lowering relative to im2row.

    Both lowerings issue one uop execution per (output pixel, reduction block,
    output-channel block) and each does block_size^2 MACs, so the ratio is
    just how many reduction blocks each needs:

        im2row  ceil(C*kh*kw / block)   - channels and taps packed densely, so
                                          only the final block is part-empty
        direct  kh*kw * ceil(C / block) - one block per (tap, channel block),
                                          so every tap re-pays the padding of C

    They are equal when C is a multiple of block, which is the common case
    inside a network. They diverge at the input layer of an image model: C=3
    costs 4.5x and C=1 costs 12.5x, because 13 or 15 of every 16 channel lanes
    are zero and the direct form pays that once per tap.
    """
    return (kh * kw * ((C + block_size - 1) // block_size)) / \
        ((C * kh * kw + block_size - 1) // block_size)


def direct_conv_geometry(C, H, W, OC, kh, kw, sh, sw, pad, block_size=16):
    """Derive the layout constants a direct convolution needs.

    pad is (top, left, bottom, right). Activations are assumed to be in the flat
    spatial layout - tensor index of channel-block `cb` at position (y, x) is
    `(y * W + x) * IC_blocks + cb` - which is what keeps the GEMM's input index
    affine in the spatial position.
    """
    pt, pl, pb, pr = pad
    IC_b = (C + block_size - 1) // block_size
    OC_b = (OC + block_size - 1) // block_size
    H_pad, W_pad = H + pt + pb, W + pl + pr
    oH = (H_pad - kh) // sh + 1
    oW = (W_pad - kw) // sw + 1
    return {
        "IC_b": IC_b, "OC_b": OC_b,
        "H_pad": H_pad, "W_pad": W_pad,
        "oH": oH, "oW": oW,
        "pt": pt, "pl": pl, "pb": pb, "pr": pr,
    }


def direct_conv_tiles(g, kh, kw, sh, sw, inp_max, acc_max):
    """Split the output into tiles that fit the scratchpads and index fields.

    An untiled convolution needs its whole input and output resident, which
    caps it at ~2048 tensors each - far below a real feature map, so almost
    every layer of a real network has to be swept in pieces.

    Tiles are rectangles of the output. A tile of th x tw output positions
    reads a padded input window of ((th-1)*sh + kh) x ((tw-1)*sw + kw), and
    both that window and the tile's accumulators have to fit. Full-width tiles
    are preferred because then the tile's rows are contiguous in the output and
    the store is a single run; width is only split when even one output row's
    input band does not fit.

    Returns a list of (oh0, th, ow0, tw), or None if not even a 1x1 output tile
    fits - in which case the caller has to fall back to im2row.
    """
    IC_b, OC_b = g["IC_b"], g["OC_b"]
    oH, oW = g["oH"], g["oW"]

    def inp_tensors(th, tw):
        return ((th - 1) * sh + kh) * ((tw - 1) * sw + kw) * IC_b

    def acc_tensors(th, tw):
        return th * tw * OC_b

    def max_th(tw):
        th = 0
        while th + 1 <= oH and inp_tensors(th + 1, tw) <= inp_max \
                and acc_tensors(th + 1, tw) <= acc_max:
            th += 1
        return th

    # Preferred: full-width row bands.
    th = max_th(oW)
    if th >= 1:
        return [(oh0, min(th, oH - oh0), 0, oW) for oh0 in range(0, oH, th)]

    # Otherwise split the width too, taking the widest tile a single output row
    # can carry, then as many rows as still fit.
    tw = 0
    while tw + 1 <= oW and inp_tensors(1, tw + 1) <= inp_max \
            and acc_tensors(1, tw + 1) <= acc_max:
        tw += 1
    if tw < 1:
        return None
    th = max(1, max_th(tw))

    return [(oh0, min(th, oH - oh0), ow0, min(tw, oW - ow0))
            for oh0 in range(0, oH, th)
            for ow0 in range(0, oW, tw)]


def direct_conv_supported(g, kh, kw, sh, sw, H, W,
                          inp_buffer_size=None, wgt_buffer_size=None,
                          acc_buffer_size=None, uop_buffer_size=None):
    """Can this layer be lowered as a direct convolution? -> (bool, reason).

    The caller uses this to choose between the direct lowering and the im2row
    one; the _fits() checks inside the emitters are then assertions, not the
    decision.

    The layer does not have to fit on chip - direct_conv_tiles() sweeps the
    output in pieces - but some things are per-layer and cannot be tiled away:

      - the whole kernel stays resident, so WGT capacity and the 10-bit weight
        index bound the layer outright;
      - x_pad carries pad*IC_blocks in only 4 bits, so a wide-channel layer
        with spatial padding runs out of pad field however it is tiled;
      - x_stride is the full input row, W*IC_blocks, in 16 bits.

    Everything else is checked against the tiles that will actually be emitted.
    Buffer sizes are in tensors/blocks; pass None to skip a capacity check.
    """
    IC_b, OC_b = g["IC_b"], g["OC_b"]
    oH, oW = g["oH"], g["oW"]

    if oH < 1 or oW < 1:
        return False, f"degenerate output {oH}x{oW}"

    per_layer = [
        ("x_pad_left", g["pl"] * IC_b, _PAD_MAX),
        ("x_pad_right", g["pr"] * IC_b, _PAD_MAX),
        ("y_pad_top", g["pt"], _PAD_MAX),
        ("y_pad_bottom", g["pb"], _PAD_MAX),
        ("max wgt index", OC_b * IC_b * kh * kw - 1, _WIDX_MAX),
        ("LOAD INP x_stride", W * IC_b, _SIZE_MAX),
        ("dst_in", OC_b, _AIDX_MAX),
        ("src_in", sw * IC_b, _IIDX_MAX),
    ]
    for name, value, limit in per_layer:
        if value > limit:
            return False, f"{name}={value} exceeds instruction field max {limit}"

    for name, need, have in (
        ("WGT", OC_b * IC_b * kh * kw, wgt_buffer_size),
        ("UOP", OC_b * kh * kw * IC_b, uop_buffer_size),
    ):
        if have is not None and need > have:
            return False, f"{name} scratchpad needs {need} > {have} available"

    # A tile has to fit both the index fields and the scratchpads.
    inp_max = _IIDX_MAX + 1
    if inp_buffer_size is not None:
        inp_max = min(inp_max, inp_buffer_size)
    acc_max = _AIDX_MAX + 1
    if acc_buffer_size is not None:
        acc_max = min(acc_max, acc_buffer_size)

    tiles = direct_conv_tiles(g, kh, kw, sh, sw, inp_max, acc_max)
    if tiles is None:
        return False, (
            f"no tile fits: one output position already needs "
            f"{kh * kw * IC_b} INP and {OC_b} ACC tensors "
            f"(budgets {inp_max}/{acc_max})")

    # Validate the widest/tallest tile's GEMM factors; the rest are no larger.
    for tile in (tiles[0], tiles[-1]):
        _, th, _, tw = tile
        tile_W = (tw - 1) * sw + kw
        for name, value, limit in (
            ("lp_out", th, _ITER_MAX),
            ("lp_in", tw, _ITER_MAX),
            ("dst_out", tw * OC_b, _AIDX_MAX),
            ("src_out", sh * tile_W * IC_b, _IIDX_MAX),
        ):
            if value > limit:
                return False, f"{name}={value} exceeds instruction field max {limit}"

    return True, f"ok ({len(tiles)} tile(s))"
