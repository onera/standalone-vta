"""Parsers for the compiler-output CSVs into the data model."""

import csv
import os
import sys
from typing import Dict, List, Optional, Tuple

from .model import (
    BUFFER_TYPES,
    DependencyInfo,
    LayerDep,
    LayerInfo,
    MemAddr,
    _align_page,
    layer_binfile,
    mem_addresses_path,
)


def load_memory_addresses(path: str) -> Dict[str, MemAddr]:
    """Parse a memory_addresses[SUFFIX].csv -> dict keyed by buffer type."""
    result: Dict[str, MemAddr] = {}
    with open(path, newline="") as f:
        for row in csv.reader(f):
            row = [c.strip() for c in row]
            if len(row) < 3 or not row[0]:
                continue
            buf_type = row[0].upper()
            if buf_type not in BUFFER_TYPES:
                continue
            result[buf_type] = MemAddr(offset=int(row[1], 16), size=int(row[2], 16))
    return result


def load_dependency_csv(path: str) -> DependencyInfo:
    """
    Parse dependency.csv.

    Row types (identified by whether col[0] parses as int):
      nb_steps, <N>
      <int_idx>, <processor>, <layer_name>      <- execution order
      <layer_name>, <processor>, <reshape>, ...  <- layer details
      image, <H>, <W>
      output, <layer_name>, <C>, <H>, <W>

    Column layout of layer-details rows follows fsim_nn.cc lines 353-460.
    """
    execution_order: List[Tuple[int, str, str]] = []
    layers: Dict[str, LayerDep] = {}
    image_h = image_w = 0
    output_layer = ""

    def _int(s: str, default: int = 0) -> int:
        try:
            return int(s)
        except (ValueError, IndexError):
            return default

    def _float(s: str, default: float = 0.0) -> float:
        try:
            return float(s)
        except (ValueError, IndexError):
            return default

    with open(path, newline="") as f:
        for row in csv.reader(f):
            row = [c.strip() for c in row]
            if not row or not row[0]:
                continue
            key = row[0]

            # Execution-order row: first column is an integer
            try:
                step_idx = int(key)
                if len(row) >= 3:
                    execution_order.append((step_idx, row[1], row[2]))
                continue
            except ValueError:
                pass

            if key == "nb_steps":
                continue
            if key == "image":
                image_h = _int(row[1]) if len(row) > 1 else 0
                image_w = _int(row[2]) if len(row) > 2 else 0
                continue
            if key == "output":
                output_layer = row[1] if len(row) > 1 else ""
                continue

            # Layer-details row
            if len(row) < 30:
                continue
            nb_inp = _int(row[29])
            deps = [row[30 + k] for k in range(nb_inp) if 30 + k < len(row)]

            layers[key] = LayerDep(
                processor=row[1],
                reshape_info=row[2],
                offset_a=_int(row[3]),
                scale_a=_float(row[4]),
                offset_b=_int(row[5]),
                scale_b=_float(row[6]),
                offset_u=_int(row[7]),
                scale_u=_float(row[8]),
                offset_v=_int(row[9]),
                scale_v=_float(row[10]),
                tensor_ch=_int(row[11]),
                tensor_h=_int(row[12]),
                tensor_w=_int(row[13]),
                kh=_int(row[14]),
                kw=_int(row[15]),
                sh=_int(row[16]),
                sw=_int(row[17]),
                pad=(_int(row[18]), _int(row[19]), _int(row[20]), _int(row[21])),
                out_ch=_int(row[22]),
                out_h=_int(row[23]),
                out_w=_int(row[24]),
                offset_c=_int(row[25]),
                scale_c=_float(row[26]),
                scale=_float(row[27]),
                nb_inp=nb_inp,
                deps=deps,
            )

    execution_order.sort(key=lambda x: x[0])
    return DependencyInfo(
        execution_order=execution_order,
        layers=layers,
        image_h=image_h,
        image_w=image_w,
        output_layer=output_layer,
    )


def _recompute_sizes_from_offsets(layers: List[LayerInfo], comp_dir: str) -> None:
    """Replace CSV-derived pseudo-sizes with real allocated byte sizes.

    The compiler's memory_addresses CSV stores [type, phys_offset, logical_addr].
    Column 3 (logical_addr = phys_offset / element_size) is NOT the byte size.
    Real allocated size = next_buffer.offset - this_buffer.offset (page-aligned
    by the compiler for all but the last buffer, which uses the file size).
    """
    # Collect all non-placeholder entries: (offset, layer_idx, buf_type)
    all_entries: List[Tuple[int, int, str]] = []
    for i, layer in enumerate(layers):
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            if m.offset == 0 and m.size == 0:
                continue  # placeholder for missing/zero buffer
            all_entries.append((m.offset, i, buf_type))

    if not all_entries:
        return

    all_entries.sort(key=lambda x: x[0])

    for j, (offset, i, buf_type) in enumerate(all_entries):
        if j + 1 < len(all_entries):
            # Size = gap to next allocation (page-aligned by compiler)
            layers[i].mem[buf_type].size = all_entries[j + 1][0] - offset
        else:
            # Last entry: use actual binary file size (page-aligned)
            bin_path = layer_binfile(comp_dir, buf_type, layers[i].suffix)
            if os.path.isfile(bin_path):
                layers[i].mem[buf_type].size = _align_page(os.path.getsize(bin_path))
            else:
                print(
                    f"WARNING: cannot determine size for last buffer "
                    f"layer {i} ({layers[i].suffix}) {buf_type} - no binary file found"
                )


def collect_layers(comp_dir: str, vta_suffixes: List[str]) -> List[LayerInfo]:
    """Build LayerInfo list from per-layer memory_addresses CSVs, in execution order."""
    if not vta_suffixes:
        sys.exit("ERROR: no VTA layers found in dependency.csv")

    layers: List[LayerInfo] = []
    for suffix in vta_suffixes:
        maddr_path = mem_addresses_path(comp_dir, suffix)
        if not os.path.isfile(maddr_path):
            sys.exit(f"ERROR: {maddr_path} not found (suffix '{suffix}')")
        mem = load_memory_addresses(maddr_path)
        missing = [t for t in BUFFER_TYPES if t not in mem]
        if missing:
            print(
                f"WARNING: {maddr_path} missing entries for {missing} - treating as size=0 (maxpool/no-weight layer)"
            )
            for t in missing:
                mem[t] = MemAddr(offset=0, size=0)
        bin_files = {t: layer_binfile(comp_dir, t, suffix) for t in BUFFER_TYPES}
        layers.append(LayerInfo(suffix=suffix, mem=mem, bin_files=bin_files))

    _recompute_sizes_from_offsets(layers, comp_dir)
    return layers


def find_image_layer(dep_info: DependencyInfo) -> Optional[str]:
    """Return the layer_name of the first step whose primary dep is 'image'."""
    for _, _, name in dep_info.execution_order:
        layer = dep_info.layers.get(name)
        if layer and layer.deps and layer.deps[0] == "image":
            return name
    return None
