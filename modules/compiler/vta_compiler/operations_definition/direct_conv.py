# IMPORT PACKAGES
# ---------------
import os
import sys

try:
    from structures import *
    from instructions_template import *
except ImportError:
    from operations_definition.structures import *
    from operations_definition.instructions_template import *

# One definition of the lowering-cost model, shared with nn_compiler, which
# uses it to choose between the two lowerings.
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.conv_layout import (
    _AIDX_MAX,
    _IIDX_MAX,
    _ITER_MAX,
    _PAD_MAX,
    _SIZE_MAX,
    _WIDX_MAX,
    direct_conv_geometry,
    direct_conv_supported,
    direct_conv_tiles,
    direct_conv_work_ratio,
)


###############################################

# Instruction field widths that the emitted values have to fit in (ISA.scala /
# structures.py). Overflowing one silently truncates the field, so every value
# derived from the convolution geometry is range-checked up front and an
# unsupported geometry raises instead.
def _fits(name, value, limit):
    if value > limit:
        raise ValueError(
            f"ERROR: direct convolution needs {name}={value}, which does not fit "
            f"the {limit}-max instruction field. Geometry unsupported; use the "
            f"im2row lowering for this layer.\n\n"
        )
    return value


def direct_conv_profitable(C, kh, kw, vta_cycles, im2row_us,
                           cycle_ns=10.0, block_size=16):
    """Is direct conv a net win for this layer? -> (bool, gain_us).

    Direct conv trades the CPU's im2row pass for extra GEMM work whenever C is
    not a multiple of the block, so a legal lowering can still be slower.

    vta_cycles and im2row_us are the layer's measured cost under the current
    lowering; cycle_ns is the VTA clock period (10ns at 100MHz). The estimate
    is deliberately pessimistic - it ignores that direct conv also cuts INP
    DRAM traffic by about kh*kw, which claws back part of the extra work.
    """
    extra_us = vta_cycles * cycle_ns / 1000.0 * \
        (direct_conv_work_ratio(C, kh, kw, block_size) - 1.0)
    gain = im2row_us - extra_us
    return gain > 0.0, gain


# DIRECT CONVOLUTION LOWERING
# ---------------------------
def conv_uops(g, kh, kw, ocb, tile_W=None):
    """The micro-op kernel for one output-channel-block.

    One uop per (dy, dx, input-channel-block); the GEMM's two-level loop then
    sweeps output rows and columns over them.

    tile_W is the padded width of the input window actually resident in the
    scratchpad. It is the tile's width, not the layer's, because the input
    index is relative to the window the LOAD wrote - which is what makes the
    same uop kernel valid for every tile.
    """
    IC_b = g["IC_b"]
    width = g["W_pad"] if tile_W is None else tile_W
    uops = []
    for dy in range(kh):
        for dx in range(kw):
            for icb in range(IC_b):
                dst = _fits("uop dst_idx", ocb, _AIDX_MAX)
                src = _fits("uop src_idx",
                            (dy * width + dx) * IC_b + icb, _IIDX_MAX)
                wgt = _fits("uop wgt_idx",
                            ((ocb * IC_b + icb) * kh + dy) * kw + dx, _WIDX_MAX)
                uops.append(VTAUop(dst_idx=dst, src_idx=src, wgt_idx=wgt))
    return uops


def tile_inp_window(g, kh, kw, sh, sw, tile, H, W):
    """Where one tile's input window sits, and how much of it is padding.

    Returns (row0, n_rows, ypad_t, ypad_b, col0, n_cols, xpad_l, xpad_r) in
    input-image coordinates: row0/col0 index the real feature map, and the pads
    are the parts of the window that fall outside it. Interior tiles come back
    with every pad zero - only tiles touching a true image border carry any,
    which is what keeps the DMA from inventing padding mid-image.
    """
    oh0, th, ow0, tw = tile
    pt, pl = g["pt"], g["pl"]

    band_rows = (th - 1) * sh + kh
    band_cols = (tw - 1) * sw + kw

    # window in padded coordinates -> input coordinates
    r_start, r_end = oh0 * sh - pt, oh0 * sh - pt + band_rows
    c_start, c_end = ow0 * sw - pl, ow0 * sw - pl + band_cols

    ypad_t, ypad_b = max(0, -r_start), max(0, r_end - H)
    xpad_l, xpad_r = max(0, -c_start), max(0, c_end - W)

    row0, col0 = max(0, r_start), max(0, c_start)
    n_rows = min(H, r_end) - row0
    n_cols = min(W, c_end) - col0
    return row0, n_rows, ypad_t, ypad_b, col0, n_cols, xpad_l, xpad_r


def load_inp_tile(g, kh, kw, sh, sw, tile, H, W, inp_dram_base, semaphore,
                  pop_next_dep=0, push_next_dep=0, sram_base=0):
    """One LOAD bringing a tile's input window on chip, border zero-filled.

    The DMA walks
        sram[i*(x_size+xpad_l+xpad_r) + j] <- dram[base + i*x_stride + j]
    so mapping i to the input row and j to (column, channel-block) flattened
    lands the window in the scratchpad in flat spatial layout, with any part
    of it that falls outside the image zeroed by the hardware.
    """
    IC_b = g["IC_b"]
    row0, n_rows, ypad_t, ypad_b, col0, n_cols, xpad_l, xpad_r = \
        tile_inp_window(g, kh, kw, sh, sw, tile, H, W)

    return load_store_instruction(
        buffer_type="INP",
        pop_prev_dep=0, pop_next_dep=pop_next_dep,
        push_prev_dep=0, push_next_dep=push_next_dep,
        sram_base=sram_base,
        dram_base=inp_dram_base + (row0 * W + col0) * IC_b,
        y_size=_fits("LOAD INP y_size", n_rows, _SIZE_MAX),
        x_size=_fits("LOAD INP x_size", n_cols * IC_b, _SIZE_MAX),
        x_stride=_fits("LOAD INP x_stride", W * IC_b, _SIZE_MAX),
        y_pad_top=_fits("LOAD INP y_pad_top", ypad_t, _PAD_MAX),
        y_pad_bottom=_fits("LOAD INP y_pad_bottom", ypad_b, _PAD_MAX),
        x_pad_left=_fits("LOAD INP x_pad_left", xpad_l * IC_b, _PAD_MAX),
        x_pad_right=_fits("LOAD INP x_pad_right", xpad_r * IC_b, _PAD_MAX),
        semaphore=semaphore,
    )


def conv_gemm(g, kh, kw, sh, sw, nb_uop, semaphore, tile, uop_begin=0,
              pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0):
    """The GEMM instruction that runs one output-channel-block over one tile.

        acc[i0*dst_out + i1*dst_in + X] += WGT[Z] . INP[i0*src_out + i1*src_in + Y]

    with i0 the output row within the tile, i1 the output column within the
    tile, and (X, Y, Z) from the uop. Every index is relative to the tile: the
    accumulators start at scratchpad 0 and so does the input window, which is
    why the same uop kernel serves every tile and only the loop bounds and the
    row stride change.
    """
    IC_b, OC_b = g["IC_b"], g["OC_b"]
    _, th, _, tw = tile
    tile_W = (tw - 1) * sw + kw
    return gemm_instruction(
        reset=0,
        pop_prev_dep=pop_prev_dep, pop_next_dep=pop_next_dep,
        push_prev_dep=push_prev_dep, push_next_dep=push_next_dep,
        uop_begin=uop_begin, uop_end=uop_begin + nb_uop,
        lp_out=_fits("lp_out", th, _ITER_MAX),
        dst_out=_fits("dst_out", tw * OC_b, _AIDX_MAX),
        src_out=_fits("src_out", sh * tile_W * IC_b, _IIDX_MAX),
        wgt_out=0,
        lp_in=_fits("lp_in", tw, _ITER_MAX),
        dst_in=_fits("dst_in", OC_b, _AIDX_MAX),
        src_in=_fits("src_in", sw * IC_b, _IIDX_MAX),
        wgt_in=0,
        semaphore=semaphore,
    )


###############################################


if __name__ == "__main__":
    # Self-check: emit the instructions, then execute them against the ISA
    # semantics and compare with a reference direct convolution.
    import numpy as np

    B = 16

    def simulate(g, kh, kw, sh, sw, uops, gem, inp, wgt):
        """Run the emitted GEMM instruction over modelled scratchpads."""
        acc = np.zeros((g["oH"] * g["oW"] * g["OC_b"], B), dtype=np.int64)
        for i0 in range(gem.loop_out):
            for i1 in range(gem.loop_in):
                for u in uops[gem.uop_bgn:gem.uop_end]:
                    a = i0 * gem.dst_factor_out + i1 * gem.dst_factor_in + u.dst_idx
                    y = i0 * gem.src_factor_out + i1 * gem.src_factor_in + u.src_idx
                    z = i0 * gem.wgt_factor_out + i1 * gem.wgt_factor_in + u.wgt_idx
                    acc[a] += wgt[z] @ inp[y]
        return acc

    def reference(x, w, sh, sw, pad):
        pt, pl, pb, pr = pad
        C, H, W = x.shape
        OC, _, kh, kw = w.shape
        xp = np.zeros((C, H + pt + pb, W + pl + pr), dtype=np.int64)
        xp[:, pt:pt + H, pl:pl + W] = x
        oH = (H + pt + pb - kh) // sh + 1
        oW = (W + pl + pr - kw) // sw + 1
        y = np.zeros((OC, oH, oW), dtype=np.int64)
        for oc in range(OC):
            for oh in range(oH):
                for ow in range(oW):
                    y[oc, oh, ow] = sum(
                        int(xp[c, oh * sh + dy, ow * sw + dx]) * int(w[oc, c, dy, dx])
                        for c in range(C) for dy in range(kh) for dx in range(kw)
                    )
        return y

    def case(name, C, H, W, OC, kh, kw, sh, sw, pad, seed=0):
        rng = np.random.default_rng(seed)
        x = rng.integers(-8, 8, size=(C, H, W), dtype=np.int64)
        w = rng.integers(-4, 4, size=(OC, C, kh, kw), dtype=np.int64)
        g = direct_conv_geometry(C, H, W, OC, kh, kw, sh, sw, pad)
        IC_b, OC_b = g["IC_b"], g["OC_b"]

        # scratchpads as the emitted LOADs would leave them
        inp = np.zeros((g["H_pad"] * g["W_pad"] * IC_b, B), dtype=np.int64)
        for c in range(C):
            for yy in range(H):
                for xx in range(W):
                    pos = (yy + g["pt"]) * g["W_pad"] + (xx + g["pl"])
                    inp[pos * IC_b + c // B, c % B] = x[c, yy, xx]
        wgt = np.zeros((OC_b * IC_b * kh * kw, B, B), dtype=np.int64)
        for oc in range(OC):
            for c in range(C):
                for dy in range(kh):
                    for dx in range(kw):
                        blk = (((oc // B) * IC_b + c // B) * kh + dy) * kw + dx
                        wgt[blk, oc % B, c % B] = w[oc, c, dy, dx]

        sem = {"LD->CMP": 0, "CMP->ST": 0, "ST->CMP": 0, "CMP->LD": 0}
        acc = np.zeros((g["oH"] * g["oW"] * OC_b, B), dtype=np.int64)
        n_gemm = 0
        for ocb in range(OC_b):
            uops = conv_uops(g, kh, kw, ocb)
            gem, sem = conv_gemm(g, kh, kw, sh, sw, len(uops), sem)
            n_gemm += 1
            acc += simulate(g, kh, kw, sh, sw, uops, gem, inp, wgt)

        ref = reference(x, w, sh, sw, pad)
        got = np.zeros_like(ref)
        for oc in range(OC):
            for oh in range(g["oH"]):
                for ow in range(g["oW"]):
                    got[oc, oh, ow] = acc[(oh * g["oW"] + ow) * OC_b + oc // B, oc % B]
        ok = np.array_equal(ref, got)

        # the padded input load, for its field values
        ld, sem = load_inp_padded(g, 0, sem)
        sup, why = direct_conv_supported(g, kh, kw, sh, sw, **W8B)
        print(f"=== {name}: C={C} {H}x{W} -> OC={OC} k{kh}x{kw} s{sh},{sw} pad{pad}"
              f" => {g['oH']}x{g['oW']}")
        print(f"    LOAD INP: y={ld.y_size} x={ld.x_size} xstr={ld.x_stride} "
              f"pad(y {ld.y_pad_top}/{ld.y_pad_bottom} x {ld.x_pad_left}/{ld.x_pad_right})")
        wr = direct_conv_work_ratio(C, kh, kw)
        print(f"    GEMM insns: {n_gemm}  uops/insn: {kh*kw*IC_b}  bit-exact: {ok}"
              f"  vta_w8b: {'supported' if sup else 'REJECTED - ' + why}")
        print(f"    GEMM work vs im2row: {wr:.2f}x"
              + ("" if wr <= 1.01 else "  <- C is not a multiple of 16"))
        return ok and sup

    # vta_w8b capacities, in tensors/blocks/uops
    W8B = {"inp_buffer_size": 2048, "wgt_buffer_size": 1024,
           "acc_buffer_size": 2048, "uop_buffer_size": 8192}

    r = []
    r.append(case("lenet5 Conv1", 1, 28, 28, 6, 5, 5, 1, 1, (2, 2, 2, 2)))
    r.append(case("lenet5 Conv3", 6, 14, 14, 16, 5, 5, 1, 1, (0, 0, 0, 0)))
    r.append(case("lenet5 Conv5", 16, 5, 5, 120, 5, 5, 1, 1, (0, 0, 0, 0)))
    r.append(case("qlinearconv_debug", 3, 5, 5, 3, 3, 3, 1, 1, (1, 1, 1, 1)))
    r.append(case("3x3 same pad, 2 cblk", 32, 10, 10, 32, 3, 3, 1, 1, (1, 1, 1, 1)))
    r.append(case("stride-2 3x3", 16, 16, 16, 16, 3, 3, 2, 2, (1, 1, 1, 1)))
    r.append(case("asymmetric pad", 8, 9, 7, 8, 3, 3, 1, 1, (2, 1, 0, 2)))
    r.append(case("1x1 pointwise", 32, 8, 8, 16, 1, 1, 1, 1, (0, 0, 0, 0)))

    # Geometries the lowering must *decline*, so the caller falls back to im2row
    # rather than emitting a silently truncated instruction.
    print()
    rejects = [
        ("256ch 3x3 pad1 (x_pad field)", 256, 8, 8, 256, 3, 3, 1, 1, (1, 1, 1, 1)),
        ("224x224 feature map (INP capacity)", 3, 224, 224, 64, 3, 3, 1, 1, (1, 1, 1, 1)),
        ("128x128x64 output (ACC capacity)", 64, 128, 128, 64, 1, 1, 1, 1, (0, 0, 0, 0)),
    ]
    for name, C, H, W, OC, kh, kw, sh, sw, pad in rejects:
        g = direct_conv_geometry(C, H, W, OC, kh, kw, sh, sw, pad)
        sup, why = direct_conv_supported(g, kh, kw, sh, sw, **W8B)
        print(f"--- {name}: {'declined' if not sup else 'ACCEPTED (should decline!)'}"
              f" - {why}")
        r.append(not sup)

    print()
    print("ALL EXACT" if all(r) else f"{r.count(False)} case(s) FAILED")
