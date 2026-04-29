#!/usr/bin/env python3
"""
gen_nn_baremetal.py — Generate baremetal headers and XSCT load scripts
from VTA compiler output directories.

Usage
-----
    python3 tools/gen_nn_baremetal.py <compiler_output_dir>             \
        [--ddr-base 0x10000000]                                          \
        [--out-header    src/fpga/software/examples/nn_ddr_map.h]       \
        [--out-tcl       src/fpga/software/examples/load_nn.tcl]        \
        [--out-exec-plan src/fpga/software/examples/nn_exec_plan.h]     \
        [--ps-init       <path/to/psu_init.tcl>]

Inputs consumed from <compiler_output_dir>
------------------------------------------
  layers_name.csv              — VTA layers and their filename suffixes
  dependency.csv               — full execution graph (VTA + CPU steps)
  memory_addresses[SUFFIX].csv — per-VTA-layer DDR offset/size table
  input_nn.bin                 — network input, pre-formatted for VTA block
                                 layout; loaded to the first layer's INP addr

Only INSN, UOP, WGT, ACC are pre-loaded as static model data.
INP and OUT buffers are runtime: INP receives input_nn.bin before the first
layer, subsequent INP regions are populated by the previous VTA layer's OUT.

Outputs
-------
  nn_ddr_map.h    — vta::LayerDesc array for VTA layers
  load_nn.tcl     — XSCT script: loads INSN/UOP/WGT/ACC + input_nn.bin
  nn_exec_plan.h  — Typed execution step array (VTA + CPU steps)
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUFFER_TYPES = ("INP", "WGT", "ACC", "OUT", "UOP", "INSN")
# Buffers to pre-load (static model data).  INP = runtime input; OUT = runtime output.
STATIC_LOAD_ORDER = ("INSN", "UOP", "WGT", "ACC")


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


def load_layers_name(path: str) -> List[Tuple[int, str]]:
    """Parse layers_name.csv → list of (index, suffix) sorted by index."""
    layers: List[Tuple[int, str]] = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            row = [c.strip() for c in row]
            if not row or row[0] == "nb_vta_ir":
                continue
            try:
                idx = int(row[0])
                suffix = row[1] if len(row) > 1 else ""
                layers.append((idx, suffix))
            except ValueError:
                pass
    layers.sort(key=lambda x: x[0])
    return layers


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


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def collect_layers(comp_dir: str) -> List[LayerInfo]:
    """Read layers_name.csv and per-layer memory_addresses CSVs."""
    lname_path = os.path.join(comp_dir, "layers_name.csv")
    if not os.path.isfile(lname_path):
        sys.exit(f"ERROR: {lname_path} not found")

    index_suffix = load_layers_name(lname_path)
    if not index_suffix:
        sys.exit("ERROR: no layers found in layers_name.csv")

    layers: List[LayerInfo] = []
    for idx, suffix in index_suffix:
        maddr_path = mem_addresses_path(comp_dir, suffix)
        if not os.path.isfile(maddr_path):
            sys.exit(f"ERROR: {maddr_path} not found (layer {idx}, suffix '{suffix}')")
        mem = load_memory_addresses(maddr_path)
        missing = [t for t in BUFFER_TYPES if t not in mem]
        if missing:
            sys.exit(f"ERROR: {maddr_path} missing entries for: {missing}")
        bin_files = {t: layer_binfile(comp_dir, t, suffix) for t in BUFFER_TYPES}
        layers.append(LayerInfo(suffix=suffix, mem=mem, bin_files=bin_files))
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
) -> int:
    """DDR address of a VTA layer's OUT buffer."""
    idx = suffix_to_idx.get(layer_name, -1)
    if idx >= 0:
        return ddr_base + layers[idx].mem["OUT"].offset
    return 0


def _cpu_out_addr(
    cpu_name: str,
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    ddr_base: int,
    suffix_to_idx: Dict[str, int],
    start_after: int,
) -> int:
    """
    Scan forward in execution_order to find where the CPU op's output is consumed.
    If the consumer is a VTA layer: im2row → INP address; int32 → ACC address.
    """
    for k in range(start_after, len(dep_info.execution_order)):
        _, proc, name = dep_info.execution_order[k]
        layer = dep_info.layers.get(name)
        if not layer or cpu_name not in layer.deps:
            continue
        if proc == "vta":
            idx = suffix_to_idx.get(name, -1)
            if idx >= 0:
                if layer.reshape_info == "im2row":
                    return ddr_base + layers[idx].mem["INP"].offset
                else:
                    return ddr_base + layers[idx].mem["ACC"].offset
        return 0  # CPU→CPU chain: unsupported, caller gets 0
    return 0


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
    print(f"WARNING: {bin_path} not found — falling back to CSV region size")
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
    L.append("/* Auto-generated by tools/gen_nn_baremetal.py — DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "../include/vta_nn.h"')
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
    dep_info: DependencyInfo, layers: List[LayerInfo], ddr_base: int, out_path: str
) -> None:
    suffix_to_idx = {layer.suffix: i for i, layer in enumerate(layers)}
    num_steps = len(dep_info.execution_order)

    L: List[str] = []
    L.append("/* Auto-generated by tools/gen_nn_baremetal.py — DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "../include/vta_cpu_ops.h"')
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
            L.append(f"        {fi['kh']}u, {fi['kw']}u, {fi['sh']}u,")
            L.append(
                f"        {{ {fi['pad'][0]}, {fi['pad'][1]}, {fi['pad'][2]}, {fi['pad'][3]} }},"
            )
            L.append(f"        {fi['offset_a']},")
            L.append(f"        {fi['out_h']}u, {fi['out_w']}u")
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
                ld.deps[0] if ld.deps else "", dep_info, layers, ddr_base, suffix_to_idx
            )
            inpB = _out_addr(
                ld.deps[1] if len(ld.deps) > 1 else "",
                dep_info,
                layers,
                ddr_base,
                suffix_to_idx,
            )
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1
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
                )
                for j in range(4)
            ]
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1
            )
            L.append(f"    /* step {step_idx}: concat */")
            L.append(f'    {{ NN_STEP_CONCAT, "{layer_name}", {{ .concat = {{')
            L.append(f"        {{ {', '.join(hex32(a) for a in inp_addrs)} }},")
            L.append(f"        {hex32(out)}, {ld.tensor_ch}u, {ld.nb_inp},")
            L.append(
                f"        {{ {ld.scale_a}f, {ld.scale_b}f, {ld.scale_u}f, {ld.scale_v}f }},"
            )
            L.append(
                f"        {{ {ld.offset_a}, {ld.offset_b}, {ld.offset_u}, {ld.offset_v} }},"
            )
            L.append(f"        {ld.scale_c}f, {ld.offset_c}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        elif processor == "dequant" and ld:
            inp = _out_addr(
                ld.deps[0] if ld.deps else "", dep_info, layers, ddr_base, suffix_to_idx
            )
            n = ld.tensor_ch * ld.tensor_h * ld.tensor_w
            L.append(f"    /* step {step_idx}: dequant */")
            L.append(f'    {{ NN_STEP_DEQUANT, "{layer_name}", {{ .dequant = {{')
            L.append(f"        {hex32(inp)}, {n}u, {ld.scale_a}f, {ld.offset_a}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        elif processor == "quant" and ld:
            out = _cpu_out_addr(
                layer_name, dep_info, layers, ddr_base, suffix_to_idx, k + 1
            )
            n = ld.out_ch * ld.out_h * ld.out_w
            L.append(f"    /* step {step_idx}: quant */")
            L.append(f'    {{ NN_STEP_QUANT, "{layer_name}", {{ .quant = {{')
            L.append(f"        {hex32(out)}, {n}u, {ld.scale_a}f, {ld.offset_a}")
            L.append(f"    }} }} }}{_comma(emitted)}")
            emitted += 1

        else:
            print(
                f"WARNING: unsupported processor '{processor}' for '{layer_name}' — emitting VTA stub"
            )
            L.append(
                f"    /* step {step_idx}: {processor} {layer_name} — unsupported, skipped */"
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
# XSCT Tcl script
# ---------------------------------------------------------------------------


def gen_tcl(
    layers: List[LayerInfo],
    ddr_base: int,
    comp_dir: str,
    out_path: str,
    dep_info: Optional[DependencyInfo] = None,
    ps_init: Optional[str] = None,
) -> None:
    L: List[str] = []
    L.append("# Auto-generated by tools/gen_nn_baremetal.py — DO NOT EDIT")
    L.append("#")
    L.append("# Loads static model data (INSN/UOP/WGT/ACC) and the network input")
    L.append("# (input_nn.bin) into DDR via XSCT, then resumes the ARM application.")
    L.append("#")
    L.append("# Usage (from Vitis XSCT console or xsct shell):")
    L.append("#   source load_nn.tcl")
    L.append("")

    if ps_init:
        ps_abs = os.path.abspath(ps_init)
        L.append("# 1. Reset the PSU and initialise the DDR controller via psu_init")
        L.append("connect")
        L.append('targets -set -filter {name =~ "PSU"}')
        L.append("rst")
        L.append("after 3000")
        L.append(f"source {{{ps_abs}}}")
        L.append("psu_init")
        L.append("after 1000")
        L.append("")
        L.append("# 2. Hold the A53 #0 in reset, then stop so we can write DDR")
        L.append('targets -set -filter {name =~ "ARM Cortex-A53 #0"}')
        L.append("rst -processor")
        L.append("stop")
        L.append("after 500")
    else:
        L.append("# psu_init not provided: assuming DDR is already initialised.")
        L.append("# Re-run with --ps-init <path/to/psu_init.tcl> for cold start.")
        L.append("connect")
        L.append('targets -set -filter {name =~ "ARM Cortex-A53 #0"}')
        L.append("stop")
        L.append("after 500")
    L.append("")

    # Static model data: INSN, UOP, WGT, ACC only
    for i, layer in enumerate(layers):
        L.append(f'# --- layer {i} "{layer.suffix}" static model data ---')
        for buf_type in STATIC_LOAD_ORDER:
            bin_path = os.path.abspath(layer.bin_files[buf_type])
            if os.path.isfile(bin_path):
                addr_str = f"0x{ddr_base + layer.mem[buf_type].offset:08X}"
                L.append(f'puts "Loading {layer.suffix} {buf_type}..."')
                L.append(f"dow -data {{{bin_path}}} {addr_str}")
        L.append("")

    # input_nn.bin → scratch area (after all VTA data).
    # The ARM format-input step reads from here and writes the im2row result
    # to the actual VTA INP address.
    input_nn_path = os.path.abspath(os.path.join(comp_dir, "input_nn.bin"))
    raw_phys = scratch_addr(layers, ddr_base)

    addr_str = f"0x{raw_phys:08X}"
    L.append("# --- raw network input (scratch — ARM applies im2row at runtime) ---")
    L.append(f'puts "Loading input_nn.bin (raw) -> {addr_str}..."')
    if os.path.isfile(input_nn_path):
        L.append(f"dow -data {{{input_nn_path}}} {addr_str}")
    else:
        L.append(f"# WARNING: {input_nn_path} not found at codegen time")
        L.append(f"dow -data {{{input_nn_path}}} {addr_str}")
    L.append("")
    L.append("# Resume ARM execution")
    L.append("con")

    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] XSCT Tcl script written to {out_path}")


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate baremetal header and XSCT script from VTA compiler output."
    )
    parser.add_argument(
        "compiler_output_dir", help="Path to the compiler output directory"
    )
    parser.add_argument(
        "--ddr-base", default="0x0", help="DDR base address (default: 0x0)"
    )
    parser.add_argument(
        "--out-header",
        default="examples/nn_ddr_map.h",
        help="Output path for the VTA LayerDesc C header",
    )
    parser.add_argument(
        "--out-tcl",
        default="examples/load_nn.tcl",
        help="Output path for the XSCT Tcl script",
    )
    parser.add_argument(
        "--out-exec-plan",
        default=None,
        metavar="PATH",
        help="Output path for the execution-plan C header (nn_exec_plan.h)",
    )
    parser.add_argument(
        "--ps-init",
        default=None,
        metavar="PATH",
        help=(
            "Path to psu_init.tcl (ZynqMP) or ps7_init.tcl (Zynq-7000). "
            "Required for cold-start DDR initialisation."
        ),
    )
    args = parser.parse_args()

    ddr_base = int(args.ddr_base, 16)
    comp_dir = os.path.abspath(args.compiler_output_dir)

    if not os.path.isdir(comp_dir):
        sys.exit(f"ERROR: compiler output directory not found: {comp_dir}")
    if args.ps_init and not os.path.isfile(args.ps_init):
        sys.exit(f"ERROR: ps-init file not found: {args.ps_init}")

    layers = collect_layers(comp_dir)
    print(f"[gen] found {len(layers)} VTA layer(s)")

    dep_info: Optional[DependencyInfo] = None
    dep_path = os.path.join(comp_dir, "dependency.csv")
    if os.path.isfile(dep_path):
        dep_info = load_dependency_csv(dep_path)
        print(f"[gen] dependency.csv: {len(dep_info.execution_order)} execution steps")
    else:
        print(
            f"WARNING: {dep_path} not found — exec plan and image-layer detection skipped"
        )

    out_paths = [args.out_header, args.out_tcl]
    if args.out_exec_plan:
        out_paths.append(args.out_exec_plan)
    for p in out_paths:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)

    gen_header(layers, ddr_base, args.out_header)
    gen_tcl(
        layers,
        ddr_base,
        comp_dir,
        args.out_tcl,
        dep_info=dep_info,
        ps_init=args.ps_init,
    )
    if args.out_exec_plan:
        if dep_info:
            gen_exec_plan_header(dep_info, layers, ddr_base, args.out_exec_plan)
        else:
            print("WARNING: --out-exec-plan requires dependency.csv — skipping")
    print_summary(layers, ddr_base)


if __name__ == "__main__":
    main()
