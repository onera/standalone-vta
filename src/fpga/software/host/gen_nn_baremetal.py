#!/usr/bin/env python3
"""
gen_nn_baremetal.py - Generate baremetal headers, XSDB load scripts, and
ELF-embedding artifacts from VTA compiler output directories.

Usage
-----
    python3 host/gen_nn_baremetal.py <compiler_output_dir>  \
        [--ddr-base 0x10000000]                                 \
        [--outdir   src/fpga/software/gen]                      \
        [--runner   {run_nn, run_nn_uart, test_gemm}]           \
        [--data-loader {tcl, elf}]

All generated files are written to --outdir (default: gen) with fixed names.
--runner and --data-loader are orthogonal: runner selects which .cc is compiled,
data-loader selects how static model data reaches DDR.  Omitting either flag
generates all artifacts (backward-compatible default).

Inputs consumed from <compiler_output_dir>
------------------------------------------
  dependency.csv               - full execution graph (VTA + CPU steps); defines layer order
  memory_addresses[SUFFIX].csv - per-VTA-layer DDR offset/size table
  input_nn.bin                 - raw network input (only needed for run_nn)

Only INSN, UOP, WGT, ACC are treated as static model data.
INP and OUT buffers are runtime: INP receives input_nn.bin before the first
layer, subsequent INP regions are populated by the previous VTA layer's OUT.

Outputs (all written to --outdir)
----------------------------------
Always generated:
  nn_ddr_map.h         - vta::LayerDesc array for VTA layers
  nn_exec_plan.h       - typed execution step array (VTA + CPU steps)

TCL data-loader (--data-loader tcl, or default):
  load_nn_static.tcl   - XSDB: loads INSN/UOP/WGT/ACC only (no input)
  load_nn.tcl          - XSDB: loads INSN/UOP/WGT/ACC + input_nn.bin
                         (only when --runner run_nn or no --runner)
  load_input.tcl       - XSDB: loads input_nn.bin only
                         (only when --runner run_nn or no --runner)

ELF data-loader (--data-loader elf, or default):
  nn_bin_data.S        - AArch64 assembly with .incbin for each static buffer
  nn_vta_sections.ld   - linker fragment placing each section at its DRAM address
"""

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUFFER_TYPES = ("INP", "WGT", "ACC", "OUT", "UOP", "INSN")

DEFAULT_BLOCK_SIZE = 16  # Config default; override with --config-json or --block-size


def load_block_size(
    config_json_path: Optional[str], cli_block_size: Optional[int]
) -> int:
    """Return the VTA block size (BLOCK_IN = BLOCK_OUT).

    Priority: explicit --block-size > --config-json LOG_BLOCK > DEFAULT_BLOCK_SIZE.
    """
    if cli_block_size is not None:
        return cli_block_size
    if config_json_path:
        try:
            with open(config_json_path) as f:
                cfg = json.load(f)
            log_block = cfg.get("LOG_BLOCK")
            if log_block is not None:
                return 1 << int(log_block)
            print(
                f"WARNING: LOG_BLOCK not found in {config_json_path} - using default {DEFAULT_BLOCK_SIZE}"
            )
        except Exception as e:
            print(
                f"WARNING: could not read {config_json_path}: {e} - using default {DEFAULT_BLOCK_SIZE}"
            )
    return DEFAULT_BLOCK_SIZE


# Buffers to pre-load (static model data).  INP = runtime input; OUT = runtime output.
STATIC_LOAD_ORDER = ("INSN", "UOP", "WGT", "ACC")

_PAGE = 0x1000


def _align_page(n: int) -> int:
    return ((n + _PAGE - 1) // _PAGE) * _PAGE


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MemAddr:
    """Offset and size relative to DDR base, from memory_addresses csv."""

    offset: int
    size: int


@dataclass
class LayerInfo:
    suffix: str
    mem: Dict[str, MemAddr]
    bin_files: Dict[str, str]


@dataclass
class LayerDep:
    """Per-layer entry parsed from dependency.csv."""

    processor: str  # "vta", "qadd", "concat", "dequant", "quant", "convtranspose"
    reshape_info: str  # "im2row", "int32", …
    offset_a: int
    scale_a: float
    offset_b: int
    scale_b: float
    offset_u: int
    scale_u: float
    offset_v: int
    scale_v: float
    tensor_ch: int
    tensor_h: int
    tensor_w: int
    kh: int
    kw: int
    sh: int
    sw: int
    pad: Tuple[int, int, int, int]
    out_ch: int
    out_h: int
    out_w: int
    offset_c: int
    scale_c: float
    scale: float
    nb_inp: int
    deps: List[str]


@dataclass
class DependencyInfo:
    execution_order: List[Tuple[int, str, str]]  # (step_idx, processor, layer_name)
    layers: Dict[str, LayerDep]
    image_h: int
    image_w: int
    output_layer: str


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------




def load_memory_addresses(path: str) -> Dict[str, MemAddr]:
    """Parse a memory_addresses[SUFFIX].csv → dict keyed by buffer type."""
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
      <int_idx>, <processor>, <layer_name>      ← execution order
      <layer_name>, <processor>, <reshape>, …  ← layer details
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


# ---------------------------------------------------------------------------
# File-name helpers
# ---------------------------------------------------------------------------

BIN_BASENAME: Dict[str, str] = {
    "INP": "input",
    "WGT": "weight",
    "ACC": "accumulator",
    "OUT": "out_init",
    "UOP": "uop",
    "INSN": "instructions",
}


def layer_binfile(comp_dir: str, buf_type: str, suffix: str) -> str:
    return os.path.join(comp_dir, f"{BIN_BASENAME[buf_type]}{suffix}.bin")


def mem_addresses_path(comp_dir: str, suffix: str) -> str:
    return os.path.join(comp_dir, f"memory_addresses{suffix}.csv")


def _relpath_posix(abs_path: str, base_dir: str) -> str:
    """Return a POSIX-style relative path from base_dir to abs_path."""
    return Path(os.path.relpath(abs_path, base_dir)).as_posix()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


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


def scratch_addr(layers: List[LayerInfo], ddr_base: int) -> int:
    """Return the first page-aligned DDR address after all VTA allocations."""
    page_size = 0x1000
    max_end = ddr_base
    for layer in layers:
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            end = ddr_base + m.offset + m.size
            if end > max_end:
                max_end = end
    return ((max_end + page_size - 1) // page_size) * page_size


# ---------------------------------------------------------------------------
# Address helpers for exec-plan generation
# ---------------------------------------------------------------------------


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
    """Scan all consumers of layer_name and return the VTA INP/ACC address if one exists."""
    for k in range(start_after, len(dep_info.execution_order)):
        _, proc, name = dep_info.execution_order[k]
        ld = dep_info.layers.get(name)
        if not ld or layer_name not in ld.deps:
            continue
        if proc == "vta":
            idx = suffix_to_idx.get(name, -1)
            if idx >= 0:
                if ld.reshape_info == "im2row":
                    return ddr_base + layers[idx].mem["INP"].offset
                else:
                    return ddr_base + layers[idx].mem["ACC"].offset
        # CPU consumer: keep scanning - a later VTA consumer may exist
    return 0


def _build_cpu_out_addrs(
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    comp_dir: str,
) -> Dict[str, int]:
    """Pre-resolve every CPU op's output DDR address.

    For ops that write into a VTA layer's INP/ACC the VTA address is used
    (shared buffer, no extra allocation).  For ops whose output feeds only
    other CPU ops a fresh page-aligned scratch region is allocated above
    the VTA + raw-input footprint.

    dequant is excluded: its output is a CPU-allocated float* not in DDR.
    """
    raw_phys = scratch_addr(layers, ddr_base)
    input_nn_path = os.path.join(comp_dir, "input_nn.bin")
    raw_size = os.path.getsize(input_nn_path) if os.path.isfile(input_nn_path) else 0
    alloc_ptr = raw_phys + max(_align_page(raw_size), _PAGE)

    cpu_out: Dict[str, int] = {}

    for k, (_, processor, layer_name) in enumerate(dep_info.execution_order):
        if processor in ("vta", "dequant"):
            continue
        ld = dep_info.layers.get(layer_name)
        if not ld:
            continue

        vta_addr = _find_vta_consumer_addr(
            layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1
        )
        if vta_addr != 0:
            cpu_out[layer_name] = vta_addr
        elif processor in ("qadd", "concat"):
            # No VTA consumer: allocate a scratch DDR region
            n_bytes = ld.out_ch * ld.out_h * ld.out_w
            cpu_out[layer_name] = alloc_ptr
            alloc_ptr += _align_page(n_bytes)
            print(
                f"[gen] CPU scratch alloc: {layer_name} → "
                f"{hex32(cpu_out[layer_name])} ({n_bytes} bytes)"
            )
        # quant with no VTA consumer is unusual; leave address as 0 (warning below)

    return cpu_out


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


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def hex32(v: int) -> str:
    return f"0x{v:08X}u"


def insn_count_from_file(bin_path: str, csv_size: int) -> int:
    """Instruction count from actual .bin file size (not padded CSV region size)."""
    if os.path.isfile(bin_path):
        file_bytes = os.path.getsize(bin_path)
        if file_bytes % 16 != 0:
            print(f"WARNING: {bin_path} size {file_bytes} not a multiple of 16")
        return file_bytes // 16
    print(f"WARNING: {bin_path} not found - falling back to CSV region size")
    return csv_size // 16


def safe_c_name(suffix: str, index: int) -> str:
    if not suffix:
        return f"l{index}"
    name = "".join(ch if ch.isalnum() else "_" for ch in suffix)
    return ("_" + name) if name[0].isdigit() else name


# ---------------------------------------------------------------------------
# C header: VTA LayerDesc array
# ---------------------------------------------------------------------------


def gen_header(layers: List[LayerInfo], ddr_base: int, out_path: str) -> None:
    L: List[str] = []
    L.append("/* Auto-generated by tools/gen_nn_baremetal.py - DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "vta_nn.h"')
    L.append("")
    L.append(f"#define DDR_NN_BASE   {hex32(ddr_base)}")
    L.append(f"#define NN_NUM_LAYERS {len(layers)}")
    L.append("")
    L.append("static const vta::LayerDesc nn_layers[NN_NUM_LAYERS] = {")

    for i, layer in enumerate(layers):
        m = layer.mem
        insn_count = insn_count_from_file(layer.bin_files["INSN"], m["INSN"].size)
        L.append(f'    /* layer {i}  suffix="{layer.suffix}" */')
        L.append("    {")
        L.append(f"        .ddr_base    = {hex32(ddr_base)},")
        L.append(f"        .insn_addr   = {hex32(ddr_base + m['INSN'].offset)},")
        L.append(f"        .insn_count  = {insn_count}u,")
        L.append(f"        .uop_phys    = {hex32(ddr_base + m['UOP'].offset)},")
        L.append(f"        .uop_bytes   = {hex32(m['UOP'].size)},")
        L.append(f"        .inp_phys    = {hex32(ddr_base + m['INP'].offset)},")
        L.append(f"        .inp_bytes   = {hex32(m['INP'].size)},")
        L.append(f"        .wgt_phys    = {hex32(ddr_base + m['WGT'].offset)},")
        L.append(f"        .wgt_bytes   = {hex32(m['WGT'].size)},")
        L.append(f"        .acc_phys    = {hex32(ddr_base + m['ACC'].offset)},")
        L.append(f"        .acc_bytes   = {hex32(m['ACC'].size)},")
        L.append(f"        .out_phys    = {hex32(ddr_base + m['OUT'].offset)},")
        L.append(f"        .out_bytes   = {hex32(m['OUT'].size)},")
        L.append(f"        .reloc_src   = 0x00000000u,")
        L.append(f"        .reloc_dst   = 0x00000000u,")
        L.append(f"        .reloc_bytes = 0x00000000u,")
        L.append(f"    }}" + ("," if i < len(layers) - 1 else ""))

    L.append("};")
    L.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] C header written to {out_path}")


# ---------------------------------------------------------------------------
# Execution plan header (VTA + CPU steps from dependency.csv)
# ---------------------------------------------------------------------------


def gen_exec_plan_header(
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    comp_dir: str,
    out_path: str,
    block_size: int = DEFAULT_BLOCK_SIZE,
) -> None:
    suffix_to_idx = {layer.suffix: i for i, layer in enumerate(layers)}
    cpu_out = _build_cpu_out_addrs(dep_info, layers, ddr_base, suffix_to_idx, comp_dir)
    num_steps = len(dep_info.execution_order)

    L: List[str] = []
    L.append("/* Auto-generated by tools/gen_nn_baremetal.py - DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "vta_cpu_ops.h"')
    L.append("")

    # Build the extra FORMAT_INPUT step for any VTA layer whose dep is "image".
    # These are injected just before the corresponding VTA step.
    # Map: layer_name → (raw_addr, step params)
    format_input_steps: Dict[str, Dict] = {}
    raw_phys = scratch_addr(layers, ddr_base)
    for _, processor, layer_name in dep_info.execution_order:
        if processor != "vta":
            continue
        ld = dep_info.layers.get(layer_name)
        if not ld or not ld.deps or ld.deps[0] != "image":
            continue
        idx = suffix_to_idx.get(layer_name, -1)
        if idx < 0 or ld.reshape_info != "im2row":
            continue
        out_h = (ld.tensor_h + ld.pad[0] + ld.pad[2] - ld.kh) // ld.sh + 1
        out_w = (ld.tensor_w + ld.pad[1] + ld.pad[3] - ld.kw) // ld.sw + 1
        format_input_steps[layer_name] = {
            "raw_addr": raw_phys,
            "inp_addr": ddr_base + layers[idx].mem["INP"].offset,
            "tensor_ch": ld.tensor_ch,
            "tensor_h": ld.tensor_h,
            "tensor_w": ld.tensor_w,
            "kh": ld.kh,
            "kw": ld.kw,
            "sh": ld.sh,
            "sw": ld.sw,
            "pad": ld.pad,
            "offset_a": ld.offset_a,
            "out_h": out_h,
            "out_w": out_w,
        }

    extra = len(format_input_steps)
    total_steps = num_steps + extra

    L += [
        "enum NnStepType {",
        "    NN_STEP_VTA          = 0,",
        "    NN_STEP_QADD         = 1,",
        "    NN_STEP_CONCAT       = 2,",
        "    NN_STEP_DEQUANT      = 3,",
        "    NN_STEP_QUANT        = 4,",
        "    NN_STEP_FORMAT_INPUT = 5,",
        "};",
        "",
        "struct NnVtaStep { int layer_idx; };",
        "",
        "struct NnExecStep {",
        "    NnStepType  type;",
        "    const char *name;",
        "    union {",
        "        NnVtaStep         vta;",
        "        NnQaddStep        qadd;",
        "        NnConcatStep      concat;",
        "        NnDequantStep     dequant;",
        "        NnQuantStep       quant;",
        "        NnFormatInputStep format_input;",
        "    };",
        "};",
        "",
        f"#define NN_NUM_STEPS {total_steps}u",
        "",
        "static const NnExecStep nn_exec_steps[NN_NUM_STEPS] = {",
    ]

    emitted = 0  # count of entries written so far (for trailing comma logic)

    def _comma(pos: int) -> str:
        return "," if pos < total_steps - 1 else ""

    for k, (step_idx, processor, layer_name) in enumerate(dep_info.execution_order):
        ld = dep_info.layers.get(layer_name)

        # Inject FORMAT_INPUT step before any VTA "image" layer
        if processor == "vta" and layer_name in format_input_steps:
            fi = format_input_steps[layer_name]
            L.append(f"    /* format_input for {layer_name} */")
            L.append(
                f'    {{ NN_STEP_FORMAT_INPUT, "format_{layer_name}", {{ .format_input = {{'
            )
            L.append(f"        {hex32(fi['raw_addr'])}, {hex32(fi['inp_addr'])},")
            L.append(
                f"        {fi['tensor_ch']}u, {fi['tensor_h']}u, {fi['tensor_w']}u,"
            )
            L.append(f"        {fi['kh']}u, {fi['kw']}u, {fi['sh']}u, {fi['sw']}u,")
            L.append(
                f"        {{ {fi['pad'][0]}, {fi['pad'][1]}, {fi['pad'][2]}, {fi['pad'][3]} }},"
            )
            L.append(f"        {fi['offset_a']},")
            L.append(f"        {fi['out_h']}u, {fi['out_w']}u, {block_size}u")
            L.append(f"    }} }} }},")
            emitted += 1

        if processor == "vta":
            vta_idx = suffix_to_idx.get(layer_name, -1)
            if vta_idx < 0:
                print(f"WARNING: VTA layer '{layer_name}' not found in layers list")
            L.append(f"    /* step {step_idx} */")
            L.append(
                f'    {{ NN_STEP_VTA, "{layer_name}", {{ .vta = {{ {vta_idx} }} }} }}{_comma(emitted)}'
            )
            emitted += 1

        elif processor == "qadd" and ld:
            inpA = _out_addr(
                ld.deps[0] if ld.deps else "",
                dep_info,
                layers,
                ddr_base,
                suffix_to_idx,
                cpu_out,
            )
            inpB = _out_addr(
                ld.deps[1] if len(ld.deps) > 1 else "",
                dep_info,
                layers,
                ddr_base,
                suffix_to_idx,
                cpu_out,
            )
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1, cpu_out
            )
            n = ld.out_ch * ld.out_h * ld.out_w
            L.append(f"    /* step {step_idx}: qadd */")
            L.append(f'    {{ NN_STEP_QADD, "{layer_name}", {{ .qadd = {{')
            L.append(f"        {hex32(inpA)}, {hex32(inpB)}, {hex32(out)}, {n}u,")
            L.append(f"        {ld.scale_a}f, {ld.scale_b}f, {ld.scale_c}f,")
            L.append(f"        {ld.offset_a}, {ld.offset_b}, {ld.offset_c}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        elif processor == "concat" and ld:
            inp_addrs = [
                _out_addr(
                    ld.deps[j] if j < len(ld.deps) else "",
                    dep_info,
                    layers,
                    ddr_base,
                    suffix_to_idx,
                    cpu_out,
                )
                for j in range(4)
            ]
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1, cpu_out
            )
            n_rows = ld.tensor_h * ld.tensor_w
            n_ch_per_inp = ld.tensor_ch
            L.append(f"    /* step {step_idx}: concat */")
            L.append(f'    {{ NN_STEP_CONCAT, "{layer_name}", {{ .concat = {{')
            L.append(f"        {{ {', '.join(hex32(a) for a in inp_addrs)} }},")
            L.append(f"        {hex32(out)}, {n_rows}u, {n_ch_per_inp}u, {ld.nb_inp},")
            L.append(
                f"        {{ {ld.scale_a}f, {ld.scale_b}f, {ld.scale_u}f, {ld.scale_v}f }},"
            )
            L.append(
                f"        {{ {ld.offset_a}, {ld.offset_b}, {ld.offset_u}, {ld.offset_v} }},"
            )
            L.append(f"        {ld.scale_c}f, {ld.offset_c}, {block_size}u")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        elif processor == "dequant" and ld:
            inp = _out_addr(
                ld.deps[0] if ld.deps else "",
                dep_info,
                layers,
                ddr_base,
                suffix_to_idx,
                cpu_out,
            )
            n = ld.tensor_ch * ld.tensor_h * ld.tensor_w
            L.append(f"    /* step {step_idx}: dequant */")
            L.append(f'    {{ NN_STEP_DEQUANT, "{layer_name}", {{ .dequant = {{')
            L.append(f"        {hex32(inp)}, {n}u, {ld.scale_a}f, {ld.offset_a}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        elif processor == "quant" and ld:
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1, cpu_out
            )
            n = ld.out_ch * ld.out_h * ld.out_w
            L.append(f"    /* step {step_idx}: quant */")
            L.append(f'    {{ NN_STEP_QUANT, "{layer_name}", {{ .quant = {{')
            L.append(f"        {hex32(out)}, {n}u, {ld.scale_a}f, {ld.offset_a}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        else:
            print(
                f"WARNING: unsupported processor '{processor}' for '{layer_name}' - emitting VTA stub"
            )
            L.append(
                f"    /* step {step_idx}: {processor} {layer_name} - unsupported, skipped */"
            )
            L.append(
                f'    {{ NN_STEP_VTA, "{layer_name}", {{ .vta = {{ -1 }} }} }}{_comma(emitted)}'
            )
            emitted += 1

    L.append("};")
    L.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(
        f"[gen] Exec plan written to {out_path} ({total_steps} steps, {extra} format-input)"
    )


# ---------------------------------------------------------------------------
# XSDB Tcl script
# ---------------------------------------------------------------------------


def gen_tcl(
    layers: List[LayerInfo],
    ddr_base: int,
    comp_dir: str,
    out_path: str,
    dep_info: Optional[DependencyInfo] = None,
    include_input: bool = True,
) -> None:
    """Generate an XSDB Tcl script that loads static model data (INSN/UOP/WGT/ACC).

    If include_input is True (default), input_nn.bin is also loaded into the
    scratch DDR region (for the run_nn flow where input is pre-loaded).
    If False, only static model data is loaded (for run_nn_uart / test_gemm).
    """
    L: List[str] = []
    L.append("# Auto-generated by tools/gen_nn_baremetal.py - DO NOT EDIT")
    L.append("#")
    if include_input:
        L.append("# Loads static model data (INSN/UOP/WGT/ACC) and the network input")
        L.append(
            "# (input_nn.bin) into DDR via XSDB, then resumes the ARM application."
        )
    else:
        L.append("# Loads static model data (INSN/UOP/WGT/ACC) only.")
        L.append(
            "# input_nn.bin is NOT loaded - supplied at runtime (UART or other means)."
        )
    L.append("#")
    L.append("# Usage (from Vitis XSDB console or xsct shell):")
    script_name = os.path.basename(out_path)
    L.append(f"#   source {script_name}")
    L.append("")
    L.append("connect")
    L.append('targets -set -filter {name =~ "APU*"}')
    L.append("stop")
    L.append("after 500")
    L.append("")

    for i, layer in enumerate(layers):
        L.append(f'# --- layer {i} "{layer.suffix}" static model data ---')
        for buf_type in STATIC_LOAD_ORDER:
            m = layer.mem[buf_type]
            if m.size == 0:
                continue
            bin_path = os.path.abspath(layer.bin_files[buf_type])
            if os.path.isfile(bin_path):
                addr_str = f"0x{ddr_base + m.offset:08X}"
                L.append(f'puts "Loading {layer.suffix} {buf_type}..."')
                L.append(f"dow -data {{{bin_path}}} {addr_str}")
        L.append("")

    if include_input:
        input_nn_path = os.path.abspath(os.path.join(comp_dir, "input_nn.bin"))
        raw_phys = scratch_addr(layers, ddr_base)
        addr_str = f"0x{raw_phys:08X}"
        L.append(
            "# --- raw network input (scratch - ARM applies im2row at runtime) ---"
        )
        L.append(f'puts "Loading input_nn.bin (raw) -> {addr_str}..."')
        if os.path.isfile(input_nn_path):
            L.append(f"dow -data {{{input_nn_path}}} {addr_str}")
        else:
            L.append(
                f"# WARNING: input_nn.bin not found at codegen time: {input_nn_path}"
            )
            L.append(
                f'puts stderr "ERROR: input_nn.bin not found - place it at: {input_nn_path}"'
            )
            L.append("exit 1")
        L.append("")

    L.append("# Resume ARM execution")
    L.append("con")

    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] XSDB Tcl script written to {out_path}")


# ---------------------------------------------------------------------------
# Assembly incbin file
# ---------------------------------------------------------------------------


def gen_asm_incbin(layers: List[LayerInfo], out_path: str) -> None:
    L: List[str] = []
    L.append("/* Auto-generated by gen_nn_baremetal.py - DO NOT EDIT */")
    L.append("/*")
    L.append(" * VTA static model data: one .incbin section per buffer per layer.")
    L.append(" * Each section is placed at its DRAM address by nn_vta_sections.ld.")
    L.append(
        " * Add this file as a source in your project and INCLUDE nn_vta_sections.ld"
    )
    L.append(" * inside your platform SECTIONS { ... } block.")
    L.append(" */")
    L.append("")

    for i, layer in enumerate(layers):
        for buf_type in STATIC_LOAD_ORDER:
            if layer.mem[buf_type].size == 0:
                continue
            abs_bin = os.path.abspath(layer.bin_files[buf_type])
            bin_path = Path(abs_bin).as_posix()  # absolute; relativized by create_vitis_workspace.py
            sec_name = f".vta_l{i}_{buf_type.lower()}"
            L.append(f'    .section {sec_name}, "a", %progbits')
            L.append("    .align 6")
            if os.path.isfile(abs_bin):
                L.append(f'    .incbin "{bin_path}"')
            else:
                L.append(
                    f"    /* WARNING: binary not found at codegen time: {bin_path} */"
                )
                print(f"WARNING: {abs_bin} not found - section will be empty")
            L.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] Assembly incbin file written to {out_path}")


# ---------------------------------------------------------------------------
# Linker script fragment
# ---------------------------------------------------------------------------


def gen_linker_fragment(layers: List[LayerInfo], ddr_base: int, out_path: str) -> None:
    L: List[str] = []
    L.append("/* Auto-generated by gen_nn_baremetal.py - DO NOT EDIT              */")
    L.append("/* VTA static model data linker fragment                             */")
    L.append("/*                                                                   */")
    L.append(
        "/* Include this file inside the platform linker script generated.                    */"
    )
    L.append("/* Example (in your lscript.ld):           */")
    L.append("/*   INCLUDE ../gen/nn_vta_sections.ld                                */")
    L.append("")

    L.append("SECTIONS {")
    for i, layer in enumerate(layers):
        for buf_type in STATIC_LOAD_ORDER:
            m = layer.mem[buf_type]
            if m.size == 0:
                continue
            addr = ddr_base + m.offset
            sec_name = f".vta_l{i}_{buf_type.lower()}"
            L.append(f"{sec_name} 0x{addr:08X} : {{ KEEP(*({sec_name})) }}")

    L.append("}")
    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] Linker fragment written to {out_path}")


# ---------------------------------------------------------------------------
# Input-only XSDB Tcl script
# ---------------------------------------------------------------------------


def gen_input_tcl(
    layers: List[LayerInfo],
    ddr_base: int,
    comp_dir: str,
    out_path: str,
) -> None:
    L: List[str] = []
    L.append("# Auto-generated by gen_nn_baremetal.py - DO NOT EDIT")
    L.append("#")
    L.append("# Loads input_nn.bin only - static model data is embedded in the ELF.")
    L.append("#")
    L.append("# Usage (from Vitis XSDB console or xsct shell):")
    L.append("#   source load_input.tcl")
    L.append("")
    L.append("connect")
    L.append('targets -set -filter {name =~ "APU*"}')
    L.append("stop")
    L.append("after 500")
    L.append("")

    input_nn_path = os.path.abspath(os.path.join(comp_dir, "input_nn.bin"))
    raw_phys = scratch_addr(layers, ddr_base)
    addr_str = f"0x{raw_phys:08X}"

    L.append("# --- raw network input (scratch - ARM applies im2row at runtime) ---")
    L.append(f'puts "Loading input_nn.bin (raw) -> {addr_str}..."')
    if os.path.isfile(input_nn_path):
        L.append(f"dow -data {{{input_nn_path}}} {addr_str}")
    else:
        L.append(f"# WARNING: input_nn.bin not found at codegen time: {input_nn_path}")
        L.append(
            f'puts stderr "ERROR: input_nn.bin not found - place it at: {input_nn_path}"'
        )
        L.append("exit 1")
    L.append("")
    L.append("# Resume ARM execution")
    L.append("con")

    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] Input-only XSDB Tcl script written to {out_path}")


# ---------------------------------------------------------------------------
# Memory fit check
# ---------------------------------------------------------------------------


def check_memory_fit(
    layers: List[LayerInfo], ddr_base: int, max_addr: int, comp_dir: str
) -> bool:
    """Verify that every DDR allocation ends before max_addr.

    Checks VTA layer buffers and the raw-input scratch region.
    CPU scratch allocations (qadd/concat intermediates) are not included.
    Returns True if everything fits, False otherwise.
    """
    overflows: List[str] = []
    high_watermark = ddr_base

    for i, layer in enumerate(layers):
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            if m.size == 0:
                continue
            end = ddr_base + m.offset + m.size
            high_watermark = max(high_watermark, end)
            if end > max_addr:
                overflows.append(
                    f"  layer {i:3d} ({layer.suffix:<30s}) {buf_type}:"
                    f" end=0x{end:08X} > max=0x{max_addr:08X}"
                    f" (overflow by {end - max_addr} bytes)"
                )

    raw_phys = scratch_addr(layers, ddr_base)
    input_nn_path = os.path.join(comp_dir, "input_nn.bin")
    raw_size = os.path.getsize(input_nn_path) if os.path.isfile(input_nn_path) else 0
    if raw_size > 0:
        raw_end = raw_phys + _align_page(raw_size)
        high_watermark = max(high_watermark, raw_end)
        if raw_end > max_addr:
            overflows.append(
                f"  input_nn.bin scratch:"
                f" end=0x{raw_end:08X} > max=0x{max_addr:08X}"
                f" (overflow by {raw_end - max_addr} bytes)"
            )

    print(f"\n[check] DDR base:       0x{ddr_base:08X}")
    print(
        f"[check] Max address:    0x{max_addr:08X}  ({max_addr - ddr_base} bytes available)"
    )
    print(
        f"[check] High watermark: 0x{high_watermark:08X}  ({high_watermark - ddr_base} bytes used)"
    )

    if overflows:
        print(f"[check] FAIL - {len(overflows)} overflow(s):")
        for msg in overflows:
            print(msg)
        return False

    remaining = max_addr - high_watermark
    print(f"[check] OK - {remaining} bytes free (0x{remaining:08X})")
    return True


# ---------------------------------------------------------------------------
# Overlap check
# ---------------------------------------------------------------------------


def check_buffer_overlaps(layers: List[LayerInfo], ddr_base: int) -> bool:
    """Check that no two DDR buffer regions overlap.

    Collects every non-empty buffer across all layers and all buffer types,
    then tests each pair for a non-empty intersection.  Returns True if the
    layout is clean, False (and prints every conflict) if any overlap exists.
    """
    # Build flat list: (phys_start, phys_end, label)
    regions: List[Tuple[int, int, str]] = []
    for i, layer in enumerate(layers):
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            if m.size == 0:
                continue
            start = ddr_base + m.offset
            end = start + m.size
            label = f"layer {i} ({layer.suffix}) {buf_type}"
            regions.append((start, end, label))

    conflicts: List[str] = []
    for j in range(len(regions)):
        for k in range(j + 1, len(regions)):
            s1, e1, l1 = regions[j]
            s2, e2, l2 = regions[k]
            if s1 < e2 and s2 < e1:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                conflicts.append(
                    f"  {l1}  [0x{s1:08X}–0x{e1:08X})\n"
                    f"  {l2}  [0x{s2:08X}–0x{e2:08X})\n"
                    f"    overlap: [0x{overlap_start:08X}–0x{overlap_end:08X})"
                    f"  ({overlap_end - overlap_start} bytes)"
                )

    if conflicts:
        print(f"\n[overlap] ERROR - {len(conflicts)} DDR region overlap(s) detected:")
        for msg in conflicts:
            print(msg)
        return False

    print(f"\n[overlap] OK - no DDR region overlaps ({len(regions)} buffers checked)")
    return True


# ---------------------------------------------------------------------------
# Summary print
# ---------------------------------------------------------------------------


def print_summary(layers: List[LayerInfo], ddr_base: int) -> None:
    print(f"\nMemory layout summary (DDR base = {hex32(ddr_base)}):")
    print(f"  {'Layer':<8} {'Buffer':<6} {'Physical addr':<16} {'Size':>10}")
    print(f"  {'-' * 8} {'-' * 6} {'-' * 16} {'-' * 10}")
    for i, layer in enumerate(layers):
        for buf_type in BUFFER_TYPES:
            m = layer.mem[buf_type]
            tag = "*" if buf_type in ("INP", "OUT") else " "
            print(
                f"  {i:<8} {buf_type:<6} {hex32(ddr_base + m.offset):<16} {hex32(m.size):>10} {tag}"
            )
    print("  (* = runtime buffer, not pre-loaded)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _print_usage_summary(
    runner: Optional[str],
    data_loader: Optional[str],
    want_tcl: bool,
    want_elf: bool,
    want_input: bool,
) -> None:
    r = runner or "run_nn"
    dl = data_loader or "tcl+elf"
    print(f"\n[gen] Deployment configuration: runner={r}  data-loader={dl}")
    if want_tcl and want_input:
        print(
            "[gen]   TCL (full):    load_nn.tcl         - static model data + input_nn.bin"
        )
    if want_tcl:
        print("[gen]   TCL (static):  load_nn_static.tcl  - static model data only")
    if want_input and not (want_tcl and want_input):
        print("[gen]   TCL (input):   load_input.tcl      - input_nn.bin only")
    elif want_input:
        print(
            "[gen]   TCL (input):   load_input.tcl      - input_nn.bin only (for ELF flow)"
        )
    if want_elf:
        print("[gen]   ELF embed:     nn_bin_data.S + nn_vta_sections.ld")
    print(f"[gen]   Compile:       examples/{r}.cc")
    if r == "run_nn_uart":
        print("[gen]   Input via:     UART (no TCL input load needed)")
    elif want_input:
        print("[gen]   Input via:     pre-loaded (TCL or ELF + load_input.tcl)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate baremetal header and XSDB script from VTA compiler output."
    )
    parser.add_argument(
        "compiler_output_dir", help="Path to the compiler output directory"
    )
    parser.add_argument(
        "--ddr-base", default="0x0", help="DDR base address (default: 0x0)"
    )
    # Runner / data-loader selection
    parser.add_argument(
        "--runner",
        choices=["run_nn", "run_nn_uart", "test_gemm"],
        default=None,
        help="Target runner binary. Controls whether input_nn.bin loading is generated. "
        "Default: generate all artifacts.",
    )
    parser.add_argument(
        "--data-loader",
        choices=["tcl", "elf"],
        default=None,
        help="Data loading strategy. 'tcl' generates XSDB scripts; 'elf' generates "
        "assembly incbin + linker fragment. Default: generate all artifacts.",
    )
    parser.add_argument(
        "--outdir",
        default="gen",
        metavar="DIR",
        help="Directory where all generated files are written (default: gen). "
        "Fixed filenames: nn_ddr_map.h, nn_exec_plan.h, load_nn.tcl, "
        "load_nn_static.tcl, load_input.tcl, nn_bin_data.S, nn_vta_sections.ld",
    )
    parser.add_argument(
        "--max-addr",
        metavar="ADDR",
        help="Maximum DDR address (hex). If given, verify all allocations fit below this address.",
    )
    parser.add_argument(
        "--config-json",
        metavar="PATH",
        help="VTA hardware config JSON (e.g. vta_config.json). Reads LOG_BLOCK to set block size.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        metavar="N",
        help="VTA block size override (overrides --config-json LOG_BLOCK). Default: 16.",
    )
    args = parser.parse_args()

    ddr_base = int(args.ddr_base, 16)
    comp_dir = os.path.abspath(args.compiler_output_dir)
    outdir = os.path.abspath(args.outdir)
    block_size = load_block_size(args.config_json, args.block_size)
    print(f"[gen] VTA block size: {block_size}")
    print(f"[gen] Output directory: {outdir}")

    # Derive generation flags from runner / data-loader selection.
    # When neither is specified all artifacts are generated (backward compat).
    want_tcl = args.data_loader in (None, "tcl")
    want_elf = args.data_loader in (None, "elf")
    want_input = args.runner in (None, "run_nn")  # uart/test_gemm: input not pre-loaded

    if not os.path.isdir(comp_dir):
        sys.exit(f"ERROR: compiler output directory not found: {comp_dir}")

    dep_path = os.path.join(comp_dir, "dependency.csv")
    if not os.path.isfile(dep_path):
        sys.exit(f"ERROR: dependency.csv not found: {dep_path}")
    dep_info = load_dependency_csv(dep_path)
    print(f"[gen] dependency.csv: {len(dep_info.execution_order)} execution steps")

    vta_suffixes = [name for _, proc, name in dep_info.execution_order if proc == "vta"]
    layers = collect_layers(comp_dir, vta_suffixes)
    print(f"[gen] found {len(layers)} VTA layer(s)")

    if not check_buffer_overlaps(layers, ddr_base):
        sys.exit(1)

    os.makedirs(outdir, exist_ok=True)

    def out(filename: str) -> str:
        return os.path.join(outdir, filename)

    # Always generate runner/loader-agnostic headers.
    gen_header(layers, ddr_base, out("nn_ddr_map.h"))
    gen_exec_plan_header(
        dep_info, layers, ddr_base, comp_dir, out("nn_exec_plan.h"), block_size
    )

    # TCL data-loader artifacts.
    if want_tcl:
        gen_tcl(
            layers,
            ddr_base,
            comp_dir,
            out("load_nn_static.tcl"),
            dep_info=dep_info,
            include_input=False,
        )
        if want_input:
            gen_tcl(
                layers,
                ddr_base,
                comp_dir,
                out("load_nn.tcl"),
                dep_info=dep_info,
                include_input=True,
            )

    # input_nn.bin TCL - generated whenever the runner needs pre-loaded input,
    # regardless of data-loader (useful even in ELF flow).
    if want_input:
        gen_input_tcl(layers, ddr_base, comp_dir, out("load_input.tcl"))

    # ELF data-loader artifacts.
    if want_elf:
        gen_asm_incbin(layers, out("nn_bin_data.S"))
        gen_linker_fragment(layers, ddr_base, out("nn_vta_sections.ld"))

    print_summary(layers, ddr_base)
    _print_usage_summary(args.runner, args.data_loader, want_tcl, want_elf, want_input)

    if args.max_addr:
        max_addr = int(args.max_addr, 16)
        if not check_memory_fit(layers, ddr_base, max_addr, comp_dir):
            sys.exit(1)


if __name__ == "__main__":
    main()
