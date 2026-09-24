# IMPORT PACKAGES
# ---------------
try:
    from structures import *
    from instructions_template import *
    from direct_conv import *
    # Underscore-prefixed, so not covered by the star import above.
    from direct_conv import _fits, _SIZE_MAX, _IIDX_MAX, _AIDX_MAX
except ImportError:
    from operations_definition.structures import *
    from operations_definition.instructions_template import *
    from operations_definition.direct_conv import *
    from operations_definition.direct_conv import _fits, _SIZE_MAX, _IIDX_MAX, _AIDX_MAX


###############################################


# DIRECT CONVOLUTION LAYER
# ------------------------
def lower_direct_conv(g, kh, kw, sh, sw, H, W,
                      inp_dram_base, wgt_dram_base, acc_dram_base, out_dram_base,
                      uop_dram_base, block_size=16,
                      inp_buffer_size=None, acc_buffer_size=None):
    """Assemble the whole instruction stream for one direct convolution.

    The kernel and the uops are loaded once and stay resident; the output is
    swept in tiles, because a real feature map is an order of magnitude larger
    than the 2048-tensor scratchpads and the 11-bit index fields.

        LOAD UOP, LOAD WGT
        per tile:  LOAD ACC, LOAD INP, GEMM x OC_blocks, STORE
        NOP-LOAD, NOP-COMPUTE, FINISH        (drain the outstanding acks)

    The per-tile handshakes are what stop the next tile's LOAD INP from
    overwriting a window the current tile's GEMM is still reading, and the next
    LOAD ACC from landing on accumulators the current STORE has not yet drained.

    dram bases are *logical* addresses - tensor/block indices, as
    dram_allocation computes them - not byte addresses.

    Returns (insn_buffer, uop_buffer).
    """
    IC_b, OC_b = g["IC_b"], g["OC_b"]
    oW = g["oW"]

    inp_max = _IIDX_MAX + 1
    if inp_buffer_size is not None:
        inp_max = min(inp_max, inp_buffer_size)
    acc_max = _AIDX_MAX + 1
    if acc_buffer_size is not None:
        acc_max = min(acc_max, acc_buffer_size)

    tiles = direct_conv_tiles(g, kh, kw, sh, sw, inp_max, acc_max)
    if tiles is None:
        raise ValueError(
            "ERROR: no direct-convolution tile fits this geometry; the caller "
            "should have declined it via direct_conv_supported().\n\n")

    insn_buffer = []
    uop_buffer = []
    semaphore = {"LD->CMP": 0, "CMP->ST": 0, "ST->CMP": 0, "CMP->LD": 0}

    # A uop's input index steps by the width of the window the LOAD wrote, and
    # the DMA lays each row out as x_size plus the pads - the *tile's* width,
    # not the widest tile's. So a narrower edge tile has a narrower row stride
    # and needs its own kernel. Widths are few (the interior one, plus a
    # remainder at the right edge), so emit one kernel set per distinct width
    # and index into it per tile. Getting this wrong is silent: the GEMM reads
    # the right number of values from the wrong rows.
    widths = sorted({(tw - 1) * sw + kw for _, _, _, tw in tiles})
    uop_ranges = {}
    for width in widths:
        for ocb in range(OC_b):
            begin = len(uop_buffer)
            uop_buffer.extend(conv_uops(g, kh, kw, ocb, tile_W=width))
            uop_ranges[(width, ocb)] = (begin, len(uop_buffer) - begin)

    n_uop = len(uop_buffer)
    n_wgt = OC_b * IC_b * kh * kw
    _fits("LOAD UOP x_size", n_uop, _SIZE_MAX)
    _fits("LOAD WGT x_size", n_wgt, _SIZE_MAX)

    # LOAD UOP and LOAD WGT, once. The load queue is in order, so WGT is on
    # chip before the first tile's INP push releases the first GEMM; it needs
    # no handshake of its own.
    insn, semaphore = load_store_instruction(
        buffer_type="UOP", sram_base=0, dram_base=uop_dram_base,
        y_size=1, x_size=n_uop, x_stride=n_uop, semaphore=semaphore)
    insn_buffer.append(insn)

    insn, semaphore = load_store_instruction(
        buffer_type="WGT", sram_base=0, dram_base=wgt_dram_base,
        y_size=1, x_size=n_wgt, x_stride=n_wgt, semaphore=semaphore)
    insn_buffer.append(insn)

    for t_idx, tile in enumerate(tiles):
        oh0, th, ow0, tw = tile
        first = t_idx == 0
        _fits("LOAD ACC x_size", tw * OC_b, _SIZE_MAX)

        # LOAD ACC - the tile's slice of the expanded bias. Waits for the
        # previous tile's STORE to have freed the accumulators.
        insn, semaphore = load_store_instruction(
            buffer_type="ACC",
            pop_next_dep=0 if first else 1,
            sram_base=0,
            dram_base=acc_dram_base + (oh0 * oW + ow0) * OC_b,
            y_size=th, x_size=tw * OC_b, x_stride=oW * OC_b,
            semaphore=semaphore)
        insn_buffer.append(insn)

        # LOAD INP - the tile's input window. Waits for the previous tile's
        # GEMMs to have finished reading the window it is about to overwrite.
        insn, semaphore = load_inp_tile(
            g, kh, kw, sh, sw, tile, H, W, inp_dram_base, semaphore,
            pop_next_dep=0 if first else 1, push_next_dep=1, sram_base=0)
        insn_buffer.append(insn)

        tile_W = (tw - 1) * sw + kw
        for ocb in range(OC_b):
            begin, count = uop_ranges[(tile_W, ocb)]
            insn, semaphore = conv_gemm(
                g, kh, kw, sh, sw, count, semaphore, tile, uop_begin=begin,
                pop_prev_dep=1 if ocb == 0 else 0,
                push_prev_dep=1 if ocb == OC_b - 1 else 0,
                push_next_dep=1 if ocb == OC_b - 1 else 0)
            insn_buffer.append(insn)

        # STORE - one contiguous run per output row of the tile. y_size stays 1
        # because TensorStore mishandles multi-row stores in the RTL; a
        # full-width tile is a single row-sized run anyway.
        for r in range(th):
            last = r == th - 1
            insn, semaphore = load_store_instruction(
                buffer_type="OUT",
                pop_prev_dep=1 if r == 0 else 0,
                push_prev_dep=1 if last else 0,
                sram_base=r * tw * OC_b,
                dram_base=out_dram_base + ((oh0 + r) * oW + ow0) * OC_b,
                y_size=1, x_size=tw * OC_b, x_stride=tw * OC_b,
                semaphore=semaphore)
            insn_buffer.append(insn)

    # Drain the last tile's outstanding acks, then FINISH.
    if semaphore["CMP->LD"] > 0:
        insn, semaphore = nop_stage_instruction(
            module="LOAD", pop_next_dep=1, semaphore=semaphore)
        insn_buffer.append(insn)
    if semaphore["ST->CMP"] > 0:
        insn, semaphore = nop_stage_instruction(
            module="COMPUTE", pop_next_dep=1, semaphore=semaphore)
        insn_buffer.append(insn)

    insn_buffer.append(VTAMemInsn(
        opcode=3,
        pop_prev_dep=0, pop_next_dep=0, push_prev_dep=0, push_next_dep=0,
        buffer_id=0, sram_base=0x0000, dram_base=0x00000000, unused=0,
        y_size=0, x_size=0, x_stride=0,
        y_pad_top=0, y_pad_bottom=0, x_pad_left=0, x_pad_right=0))

    for key, value in semaphore.items():
        if value != 0:
            raise ValueError(
                f"ERROR: direct convolution left the {key} semaphore at "
                f"{value}; the instruction stream would deadlock.\n\n")

    return insn_buffer, uop_buffer
