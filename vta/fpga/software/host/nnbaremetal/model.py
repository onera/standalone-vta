"""Core data structures, constants, and path/name helpers."""

import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BUFFER_TYPES = ("INP", "WGT", "ACC", "OUT", "UOP", "INSN")
STATIC_LOAD_ORDER = ("INSN", "UOP", "WGT", "ACC")


def _is_runtime_acc(layer: "LayerInfo", buf_type: str) -> bool:
    """True when a buffer must NOT be statically pre-loaded into the ELF.

    For an int32 (ALU/maxpool) layer the ACC holds the layer's *input*
    activations (dynamic, produced by the previous layer at runtime), not a
    static parameter.  The VTA ALU reduction (dst = max(dst, src), reset=0) is
    seeded straight from ACC, so a static placeholder there would corrupt the
    result.  Conv ACC (a bias) stays static.  See STATIC_LOAD_ORDER callers.
    """
    return buf_type == "ACC" and layer.reshape_info == "int32"


def iter_static_buffers(layers: List["LayerInfo"]):
    """Yield (i, layer, buf_type, mem) for each statically pre-loaded buffer.

    Single source of truth for "what gets embedded in the ELF / loaded by Tcl":
    iterates STATIC_LOAD_ORDER and skips empty buffers and the runtime ACC of
    int32/maxpool layers (see _is_runtime_acc).  Used by every emitter/checker
    that walks the static model data.
    """
    for i, layer in enumerate(layers):
        for buf_type in STATIC_LOAD_ORDER:
            m = layer.mem[buf_type]
            if m.size == 0 or _is_runtime_acc(layer, buf_type):
                continue
            yield i, layer, buf_type, m


_PAGE = 0x1000
INSN_BYTES = 16
INCBIN_ALIGN_LOG2 = 6


def _align_page(n: int) -> int:
    return ((n + _PAGE - 1) // _PAGE) * _PAGE


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
    # reshape_info from dependency.csv ("im2row", "int32", ...); populated in
    # main() from dep_info.  Defaults to "im2row" so any layer left unannotated
    # keeps the historical conv behaviour (ACC = static bias).
    reshape_info: str = "im2row"
    # --- per-layer isolation-check regions (populated only with
    #     --emit-layer-check; all default to "absent") ---
    in_ref_file: Optional[str] = None  # fsim golden input  (input<suffix>.bin)
    in_ref_addr: int = 0  # DRAM address of the embedded golden input
    in_ref_size: int = 0  # golden input byte count
    in_dst_addr: int = 0  # buffer the input is copied into (INP or ACC)
    out_ref_file: Optional[str] = None  # fsim golden output (output<suffix>.bin)
    out_ref_addr: int = 0  # DRAM address of the embedded golden output
    out_ref_size: int = 0  # golden output byte count


@dataclass
class LayerDep:
    """Per-layer entry parsed from dependency.csv."""

    processor: str  # "vta", "qadd", "concat", "dequant", "quant", "convtranspose"
    reshape_info: str  # "im2row", "int32", ...
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


BIN_BASENAME: Dict[str, str] = {
    "INP": "input",
    "WGT": "weight",
    "ACC": "accumulator",
    "OUT": "out_init",
    "UOP": "uop",
    "INSN": "instructions",
}


def layer_binfile(comp_dir: str, buf_type: str, suffix: str) -> str:
    # ACC uses the block-formatted sibling: the raw "accumulator{suffix}.bin"
    # written by the vta_compiler is (Ah x Bw) row-major and is shorter than
    # the block-tiled LACC SRAM region, so loading it byte-for-byte into DRAM
    # leaves the trailing region uninitialized and the bias layout wrong.
    # fsim re-blocks via data_formatting at load time; baremetal cannot, so it
    # reads "accumulator{suffix}_block.bin" instead (emitted by main_vta_compiler).
    if buf_type == "ACC":
        return os.path.join(comp_dir, f"{BIN_BASENAME[buf_type]}{suffix}_block.bin")
    return os.path.join(comp_dir, f"{BIN_BASENAME[buf_type]}{suffix}.bin")


def mem_addresses_path(comp_dir: str, suffix: str) -> str:
    return os.path.join(comp_dir, f"memory_addresses{suffix}.csv")


def ref_input_path(ref_dir: str, suffix: str) -> str:
    """fsim golden input dump for a layer (VTA_DUMP_LAYERS=1)."""
    return os.path.join(ref_dir, f"input{suffix}.bin")


def ref_input_y_path(ref_dir: str, suffix: str) -> str:
    """fsim golden secondary-operand input dump (dual-operand int32 layers)."""
    return os.path.join(ref_dir, f"input{suffix}_Y.bin")


def ref_output_path(ref_dir: str, suffix: str) -> str:
    """fsim golden output dump for a layer (raw OUT, pre-rescale)."""
    return os.path.join(ref_dir, f"output{suffix}.bin")


def _relpath_posix(abs_path: str, base_dir: str) -> str:
    """Return a POSIX-style relative path from base_dir to abs_path."""
    return Path(os.path.relpath(abs_path, base_dir)).as_posix()


def hex32(v: int) -> str:
    return f"0x{v:08X}u"


def insn_count_from_file(bin_path: str, csv_size: int) -> int:
    """Instruction count from actual .bin file size (not padded CSV region size)."""
    if os.path.isfile(bin_path):
        file_bytes = os.path.getsize(bin_path)
        if file_bytes % INSN_BYTES != 0:
            print(
                f"WARNING: {bin_path} size {file_bytes} not a multiple of {INSN_BYTES}"
            )
        return file_bytes // INSN_BYTES
    print(f"WARNING: {bin_path} not found - falling back to CSV region size")
    return csv_size // INSN_BYTES


def safe_c_name(suffix: str, index: int) -> str:
    if not suffix:
        return f"l{index}"
    name = "".join(ch if ch.isalnum() else "_" for ch in suffix)
    return ("_" + name) if name[0].isdigit() else name
