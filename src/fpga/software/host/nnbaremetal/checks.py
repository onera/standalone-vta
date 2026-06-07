"""DRAM-layout guard checks (overlap, fit) and the layout map.

These guard the generated layout against the two failure modes that corrupt a
run: two live buffers sharing DDR, or an allocation/file running past its slot or
the board's mapped DRAM. Each returns True when clean and prints a one-line
reason per violation otherwise. audit_dram.py drives them standalone; the
generator calls them as a pre-emit guard.
"""

import math
import os
from typing import Dict, List, Optional, Tuple

from .model import (
    BUFFER_TYPES,
    DependencyInfo,
    LayerInfo,
    _align_page,
    hex32,
    iter_static_buffers,
)
from .layout import scratch_addr


def _live_regions(
    layers: List[LayerInfo],
    ddr_base: int,
    cpu_scratch: Optional[List[Tuple[str, int, int]]] = None,
) -> List[Tuple[int, int, str]]:
    """Every non-empty DDR region as (start, end, label): VTA buffers, CPU
    scratch, and the isolation-check golden regions (present only after
    --emit-layer-check)."""
    regions: List[Tuple[int, int, str]] = []
    for label, addr, size in cpu_scratch or []:
        if size > 0:
            regions.append((addr, addr + size, f"cpu-scratch {label}"))
    for i, layer in enumerate(layers):
        for bt in BUFFER_TYPES:
            m = layer.mem[bt]
            if m.size:
                start = ddr_base + m.offset
                regions.append((start, start + m.size, f"L{i} {layer.suffix} {bt}"))
        if layer.in_ref_size:
            regions.append(
                (
                    layer.in_ref_addr,
                    layer.in_ref_addr + layer.in_ref_size,
                    f"L{i} {layer.suffix} INREF",
                )
            )
        if layer.out_ref_size:
            regions.append(
                (
                    layer.out_ref_addr,
                    layer.out_ref_addr + layer.out_ref_size,
                    f"L{i} {layer.suffix} OUTREF",
                )
            )
    return regions


def check_buffer_overlaps(
    layers: List[LayerInfo],
    ddr_base: int,
    cpu_scratch: Optional[List[Tuple[str, int, int]]] = None,
) -> bool:
    """No two live DDR regions may overlap."""
    regions = _live_regions(layers, ddr_base, cpu_scratch)
    conflicts = []
    for j in range(len(regions)):
        s1, e1, l1 = regions[j]
        for k in range(j + 1, len(regions)):
            s2, e2, l2 = regions[k]
            if s1 < e2 and s2 < e1:
                conflicts.append(
                    f"  {l1} [0x{s1:08X}-0x{e1:08X}) overlaps "
                    f"{l2} [0x{s2:08X}-0x{e2:08X})"
                )
    if conflicts:
        print(f"[overlap] FAIL - {len(conflicts)} overlap(s):")
        print("\n".join(conflicts))
        return False
    print(f"[overlap] OK ({len(regions)} regions)")
    return True


def check_binary_fits(layers: List[LayerInfo], comp_dir: str) -> bool:
    """Each static binary (INSN/UOP/WGT/ACC) must fit its allocated slot."""
    bad = []
    checked = 0
    for i, layer, bt, m in iter_static_buffers(layers):
        path = layer.bin_files[bt]
        if not os.path.isfile(path):
            continue
        checked += 1
        size = os.path.getsize(path)
        if size > m.size:
            bad.append(f"  L{i} {layer.suffix} {bt}: file {size} B > slot {m.size} B")
    if bad:
        print(f"[binfit] FAIL - {len(bad)} overflow(s):")
        print("\n".join(bad))
        return False
    print(f"[binfit] OK ({checked} files)")
    return True


def check_cpu_output_fits(
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    cpu_out: Dict[str, int],
    block_size: int,
    inp_elem_bytes: int = 1,
) -> bool:
    """CPU-side outputs must fit the VTA region they feed. im2row writes
    vta_inp_t elements into INP (byte size scales with inp_elem_bytes); qadd/
    concat/quant write compact int8 into the next VTA consumer's INP/ACC."""
    bad = []
    for k, (_, processor, name) in enumerate(dep_info.execution_order):
        ld = dep_info.layers.get(name)
        if not ld:
            continue
        if processor == "vta":
            if not (ld.deps and ld.deps[0] == "image" and ld.reshape_info == "im2row"):
                continue
            idx = suffix_to_idx.get(name, -1)
            if idx < 0:
                continue
            out_h = (ld.tensor_h + ld.pad[0] + ld.pad[2] - ld.kh) // ld.sh + 1
            out_w = (ld.tensor_w + ld.pad[1] + ld.pad[3] - ld.kw) // ld.sw + 1
            tiled = math.ceil(ld.kh * ld.kw * ld.tensor_ch / block_size) * block_size
            need = out_h * out_w * tiled * inp_elem_bytes
            have = layers[idx].mem["INP"].size
            if need > have:
                bad.append(f"  im2row {name}: {need} B > INP {have} B")
            continue
        if processor not in ("qadd", "concat", "quant"):
            continue
        consumer = None
        for j in range(k + 1, len(dep_info.execution_order)):
            _, proc, cname = dep_info.execution_order[j]
            if proc != "vta":
                continue
            vld = dep_info.layers.get(cname)
            if not vld or name not in vld.deps:
                continue
            idx = suffix_to_idx.get(cname, -1)
            if idx >= 0:
                consumer = (idx, "INP" if vld.reshape_info == "im2row" else "ACC")
            break
        if consumer is None:
            continue
        idx, buf = consumer
        need = ld.out_ch * ld.out_h * ld.out_w
        have = layers[idx].mem[buf].size
        if need > have:
            bad.append(f"  {processor} {name}: {need} B > {buf} {have} B")
    if bad:
        print(f"[cpufit] FAIL - {len(bad)} overflow(s):")
        print("\n".join(bad))
        return False
    print("[cpufit] OK")
    return True


def check_memory_fit(
    layers: List[LayerInfo],
    ddr_base: int,
    max_addr: int,
    comp_dir: str,
    cpu_scratch: Optional[List[Tuple[str, int, int]]] = None,
) -> bool:
    """Every allocation (page-aligned) plus the input_nn scratch must end below
    max_addr."""
    regions = list(_live_regions(layers, ddr_base, cpu_scratch))
    raw_phys = scratch_addr(layers, ddr_base)
    input_nn = os.path.join(comp_dir, "input_nn.bin")
    if os.path.isfile(input_nn) and os.path.getsize(input_nn):
        sz = os.path.getsize(input_nn)
        regions.append((raw_phys, raw_phys + sz, "input_nn scratch"))
    high = ddr_base
    bad = []
    for start, end, label in regions:
        end = start + _align_page(end - start)
        high = max(high, end)
        if end > max_addr:
            bad.append(f"  {label}: end 0x{end:08X} > max 0x{max_addr:08X}")
    print(f"[memfit] base 0x{ddr_base:08X}  high 0x{high:08X}  max 0x{max_addr:08X}")
    if bad:
        print(f"[memfit] FAIL - {len(bad)} overflow(s):")
        print("\n".join(bad))
        return False
    print(f"[memfit] OK ({max_addr - high} B free)")
    return True


def print_summary(layers: List[LayerInfo], ddr_base: int) -> None:
    """Compact DRAM map (* = runtime buffer, not pre-loaded)."""
    print(f"\nDRAM map (base {hex32(ddr_base)}):")
    for i, layer in enumerate(layers):
        for bt in BUFFER_TYPES:
            m = layer.mem[bt]
            tag = "*" if bt in ("INP", "OUT") else " "
            print(
                f"  L{i:<2} {bt:<4} {hex32(ddr_base + m.offset)} {hex32(m.size):>10} {tag}"
            )
