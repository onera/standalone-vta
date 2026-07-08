"""DRAM address and allocation logic for VTA/CPU buffers."""

import os
from typing import Dict, List, Optional, Tuple

from .model import (
    BUFFER_TYPES,
    DependencyInfo,
    LayerInfo,
    _PAGE,
    _align_page,
    hex32,
    safe_c_name,
)


def scratch_addr(layers: List[LayerInfo], ddr_base: int) -> int:
    """Return the first page-aligned DDR address after all VTA allocations."""
    max_end = ddr_base
    for layer in layers:
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            end = ddr_base + m.offset + m.size
            if end > max_end:
                max_end = end
    return _align_page(max_end)


def _out_addr(
    layer_name: str,
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    cpu_out: Optional[Dict[str, int]] = None,
) -> int:
    """DDR address where layer_name wrote its output.

    Checks VTA OUT buffers first, then the pre-resolved cpu_out map
    (which covers CPU ops that write to VTA INP/ACC or to CPU scratch).
    """
    idx = suffix_to_idx.get(layer_name, -1)
    if idx >= 0:
        return ddr_base + layers[idx].mem["OUT"].offset
    if cpu_out is not None:
        return cpu_out.get(layer_name, 0)
    return 0


def _find_vta_consumer_addr(
    layer_name: str,
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    start_after: int,
) -> int:
    """Scan consumers of layer_name; return a VTA buffer address only when a CPU
    op may write that buffer directly, else 0 (caller allocates scratch).

    A CPU op's output is compact int8.  It must NEVER be written straight into a
    VTA buffer that the hardware reads at a wider element width:
      - im2row consumer: INP expects im2row layout -> 0, NN_STEP_IM2ROW converts.
      - int32 consumer (maxpool/ALU): ACC is int32 -> 0, NN_STEP_INT32_CHAIN
        widens the scratch int8 into the int32 ACC (writing int8 here would be
        read back as garbage int32).
    Both VTA-consumer cases therefore return 0; the routing is kept explicit
    rather than collapsed so the reason is documented at the decision point.
    """
    for k in range(start_after, len(dep_info.execution_order)):
        _, proc, name = dep_info.execution_order[k]
        ld = dep_info.layers.get(name)
        if not ld or layer_name not in ld.deps:
            continue
        if proc == "vta":
            idx = suffix_to_idx.get(name, -1)
            if idx >= 0:
                # im2row -> INP via NN_STEP_IM2ROW; int32 -> ACC via
                # NN_STEP_INT32_CHAIN.  Either way the producer writes scratch.
                return 0
        # CPU consumer: keep scanning - a later VTA consumer may exist
    return 0


def _build_cpu_out_addrs(
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    comp_dir: str,
) -> Tuple[Dict[str, int], int, List[Tuple[str, int, int]]]:
    """Pre-resolve every CPU op's output DDR address.

    For ops that write into a VTA layer's INP/ACC the VTA address is used
    (shared buffer, no extra allocation).  For ops whose output feeds only
    other CPU ops a fresh page-aligned scratch region is allocated above
    the VTA + raw-input footprint.

    dequant is excluded: its output is a CPU-allocated float* not in DDR.

    Returns (cpu_out, alloc_top, cpu_scratch) where alloc_top is the first free
    page-aligned address above all VTA buffers, the raw-input scratch, and
    CPU-op scratch; cpu_scratch is the list of (label, addr, n_bytes) regions
    freshly allocated here (not aliasing a VTA buffer).
    """
    raw_phys = scratch_addr(layers, ddr_base)
    input_nn_path = os.path.join(comp_dir, "input_nn.bin")
    raw_size = os.path.getsize(input_nn_path) if os.path.isfile(input_nn_path) else 0
    alloc_ptr = raw_phys + max(_align_page(raw_size), _PAGE)

    cpu_out: Dict[str, int] = {}
    # Freshly-allocated scratch regions (label, addr, n_bytes) - the ones that
    # do NOT alias a VTA INP/ACC buffer.  Surfaced so the overlap/memory-fit
    # checks can include them.
    cpu_scratch: List[Tuple[str, int, int]] = []

    for k, (_, processor, layer_name) in enumerate(dep_info.execution_order):
        # dequant/convtranspose produce a CPU-allocated float* (the run_nn
        # float_buf), not a DDR buffer, so they need no DDR output address.
        if processor in ("vta", "dequant", "convtranspose"):
            continue
        ld = dep_info.layers.get(layer_name)
        if not ld:
            continue

        vta_addr = _find_vta_consumer_addr(
            layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1
        )
        if vta_addr != 0:
            cpu_out[layer_name] = vta_addr
        elif processor in ("qadd", "concat", "quant"):
            # No VTA consumer: allocate a scratch DDR region.  quant included so a
            # requantizing quant (e.g. after a convtranspose) or a terminal quant
            # writes its compact int8 output to a real, readable address rather
            # than 0.  Its output is consumed either by a downstream VTA layer
            # (via im2row from this scratch) or read back as the network output.
            n_bytes = ld.out_ch * ld.out_h * ld.out_w
            cpu_out[layer_name] = alloc_ptr
            cpu_scratch.append((layer_name, alloc_ptr, n_bytes))
            alloc_ptr += _align_page(n_bytes)
            print(
                f"[gen] CPU scratch alloc: {layer_name} -> "
                f"{hex32(cpu_out[layer_name])} ({n_bytes} bytes)"
            )
        # quant with no VTA consumer is unusual; leave address as 0 (warning below)

    # alloc_ptr is the first free page-aligned address above all VTA buffers,
    # the raw-input scratch, and any CPU-op scratch - the safe base for the
    # isolation-check golden regions.
    return cpu_out, alloc_ptr, cpu_scratch


def _build_cpu_param_addrs(
    dep_info: DependencyInfo,
    comp_dir: str,
    alloc_base: int,
) -> Tuple[Dict[str, Dict[str, int]], List[Tuple[str, str, int, int]], int]:
    """Allocate DDR for CPU-op *parameter* blobs (currently the float weights and
    bias of each convtranspose op).

    Unlike the inter-layer activation scratch handled by _build_cpu_out_addrs,
    these are read-only model parameters: they are loaded into DRAM by the same
    static-load path as the VTA INSN/UOP/WGT/ACC buffers (ELF .incbin + Tcl dow)
    and read by the CPU op at run time.  The PL never touches them.

    Returns (ct_params, blobs, alloc_top):
      ct_params: layer_name -> {"wgt_addr", "bias_addr", "has_bias"}
      blobs:     list of (section_label, abs_bin_path, addr, size) for the
                 loaders (emit_load) and the overlap/fit checks
      alloc_top: first free page-aligned address above these blobs
    """
    alloc = _align_page(alloc_base)
    ct_params: Dict[str, Dict[str, int]] = {}
    blobs: List[Tuple[str, str, int, int]] = []
    ct_idx = 0
    for _, processor, name in dep_info.execution_order:
        if processor != "convtranspose":
            continue
        # node_cpu writes flat float32 "weight{suffix}.bin" / "accumulator{suffix}.bin"
        # (no _block sibling - consumed directly as flat float by run_convtranspose).
        wpath = os.path.join(comp_dir, f"weight{name}.bin")
        bpath = os.path.join(comp_dir, f"accumulator{name}.bin")
        wsize = os.path.getsize(wpath) if os.path.isfile(wpath) else 0
        bsize = os.path.getsize(bpath) if os.path.isfile(bpath) else 0
        if wsize == 0:
            print(f"WARNING: convtranspose '{name}' weight bin missing: {wpath}")
        safe = safe_c_name(name, ct_idx)
        ct_idx += 1

        wgt_addr = alloc
        blobs.append((f".ct_{safe}_wgt", os.path.abspath(wpath), wgt_addr, wsize))
        alloc += max(_align_page(wsize), _PAGE)

        has_bias = 1 if bsize > 0 else 0
        bias_addr = 0
        if has_bias:
            bias_addr = alloc
            blobs.append((f".ct_{safe}_bias", os.path.abspath(bpath), bias_addr, bsize))
            alloc += max(_align_page(bsize), _PAGE)

        ct_params[name] = {
            "wgt_addr": wgt_addr,
            "bias_addr": bias_addr,
            "has_bias": has_bias,
        }
        print(
            f"[gen] convtranspose param alloc: {name} wgt {hex32(wgt_addr)}"
            f" ({wsize} B)" + (f", bias {hex32(bias_addr)} ({bsize} B)" if has_bias else "")
        )
    return ct_params, blobs, alloc


def _cpu_out_addr(
    cpu_name: str,
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    start_after: int,
    cpu_out: Optional[Dict[str, int]] = None,
) -> int:
    """Return the DDR address where cpu_name should write its output.

    Prefers the pre-resolved cpu_out map; falls back to scanning for a VTA
    consumer (handles quant steps not entered in cpu_out).
    """
    if cpu_out is not None and cpu_name in cpu_out:
        return cpu_out[cpu_name]
    # Fallback: scan for a VTA consumer (legacy path, covers quant)
    return _find_vta_consumer_addr(
        cpu_name, dep_info, layers, ddr_base, suffix_to_idx, start_after
    )
