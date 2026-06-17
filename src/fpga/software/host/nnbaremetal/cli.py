"""Command-line entry point: wires parse -> layout -> checks -> emit."""

from .config import (
    _elem_bytes,
    check_config_compat,
    gen_hw_config_header,
    load_config_params,
)
from .model import _align_page
from .parse import collect_layers, load_dependency_csv
from .layout import _build_cpu_out_addrs, _build_cpu_param_addrs
from .emit_headers import gen_exec_plan_header, gen_header
from .emit_load import gen_asm_incbin, gen_input_tcl, gen_linker_fragment, gen_tcl
from .emit_sd import gen_sd_manifest
from .debug_emit import assign_layer_check_regions, gen_cpu_debug_map, gen_debug_map
from .checks import (
    check_binary_fits,
    check_buffer_overlaps,
    check_cpu_output_fits,
    check_memory_fit,
    print_summary,
)

import argparse
import csv
import json
import os
import sys
from pathlib import Path


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
    parser.add_argument(
        "--outdir",
        default="gen",
        metavar="DIR",
        help="Directory where all generated files are written (default: gen).",
    )

    parser.add_argument(
        "--config-json",
        metavar="PATH",
        help=(
            "VTA hardware config JSON (e.g. vta_config.json). Reads LOG_BLOCK,"
            " LOG_INP_WIDTH, LOG_OUT_WIDTH, LOG_WGT_WIDTH, LOG_ACC_WIDTH."
            " Generates gen/vta_hw_config.h with the corresponding C++ type aliases."
        ),
    )
    parser.add_argument(
        "--block-size",
        type=int,
        metavar="N",
        help="VTA block size override (overrides --config-json LOG_BLOCK). Default: 16.",
    )
    audit_group = parser.add_argument_group("Audit")
    audit_group.add_argument(
        "--max-addr",
        metavar="ADDR",
        help="Maximum DDR address (hex). If given, verify all allocations fit below this address.",
    )
    debug_group = parser.add_argument_group("Debug")

    debug_group.add_argument(
        "--emit-layer-check",
        action="store_true",
        help=(
            "Emit per-layer isolation-check artifacts (nn_debug_map.h + embedded"
            " golden inputs/outputs) for the run_nn_debug app. Requires --ref-dir."
            " Off by default; normal images are unaffected."
        ),
    )
    debug_group.add_argument(
        "--ref-dir",
        metavar="DIR",
        help=(
            "Directory with fsim golden dumps (VTA_DUMP_LAYERS=1):"
            " input<SUFFIX>.bin / output<SUFFIX>.bin. Required with --emit-layer-check."
        ),
    )
    parser.add_argument(
        "--emit-cpu-check",
        action="store_true",
        help=(
            "Emit nn_cpu_debug_map.h for the run_nn_cpu_debug (isolation)"
            " per-CPU-op check. Reuses the same golden DRAM regions"
            " as --emit-layer-check; implies --emit-layer-check."
        ),
    )
    sd_group = parser.add_argument_group("SD loader")
    sd_group.add_argument(
        "--emit-sd-manifest",
        action="store_true",
        help=(
            "Emit nn_sd_manifest.h (file -> DDR address map) and stage the .bin"
            " set into <outdir>/sd_card/ for the runtime SD-card loader"
            " (DATA_LOADER=sd). Off by default."
        ),
    )
    sd_group.add_argument(
        "--sd-dir",
        default="",
        metavar="NAME",
        help=(
            "Subfolder on the SD card the board reads the .bin set from (e.g."
            " 'qyolo_pattern'), so several models can share one card. Baked into"
            " the manifest as NN_SD_DIR and used as the staging subfolder."
            " Default: card root."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase verbosity of the generation script",
    )
    args = parser.parse_args()
    if args.emit_cpu_check:
        args.emit_layer_check = True

    ddr_base = int(args.ddr_base, 16)
    comp_dir = os.path.abspath(args.compiler_output_dir)
    outdir = os.path.abspath(args.outdir)
    cfg = load_config_params(args.config_json, args.block_size)
    block_size = cfg.block_size
    print(
        f"[gen] VTA block size: {block_size}"
        f" | inp={1 << cfg.log_inp_width}-bit"
        f" | out={1 << cfg.log_out_width}-bit"
        f" | acc={1 << cfg.log_acc_width}-bit"
    )
    print(f"[gen] Output directory: {outdir}")

    if not os.path.isdir(comp_dir):
        sys.exit(f"ERROR: compiler output directory not found: {comp_dir}")

    dep_path = os.path.join(comp_dir, "dependency.csv")
    if not os.path.isfile(dep_path):
        sys.exit(f"ERROR: dependency.csv not found: {dep_path}")
    dep_info = load_dependency_csv(dep_path)
    print(f"[gen] dependency.csv: {len(dep_info.execution_order)} execution steps")

    check_config_compat(cfg, dep_info)

    vta_suffixes = [name for _, proc, name in dep_info.execution_order if proc == "vta"]
    layers = collect_layers(comp_dir, vta_suffixes)
    print(f"[gen] found {len(layers)} VTA layer(s)")

    # Annotate each layer with its reshape_info so the static-load emitters can
    # tell a conv (ACC = static bias, pre-load) from an int32/maxpool layer
    # (ACC = dynamic runtime input, must NOT be pre-loaded).  Must run before
    # the check_* calls and any gen_* emitter below.
    for layer in layers:
        ld = dep_info.layers.get(layer.suffix)
        if ld:
            layer.reshape_info = ld.reshape_info

    suffix_to_idx = {layer.suffix: i for i, layer in enumerate(layers)}
    cpu_out, alloc_top, cpu_scratch = _build_cpu_out_addrs(
        dep_info, layers, ddr_base, suffix_to_idx, comp_dir
    )
    # CPU-op parameter blobs (convtranspose float weights/bias) allocated above
    # all VTA + CPU-scratch regions, loaded via the static-load path (incbin/Tcl).
    ct_params, ct_blobs, alloc_top = _build_cpu_param_addrs(
        dep_info, comp_dir, alloc_top
    )
    # Combine CPU activation scratch + CPU-op parameter blobs for the layout
    # guard checks (overlap / fit), each as (label, addr, bytes).
    all_scratch = list(cpu_scratch) + [
        (label, addr, size) for label, _path, addr, size in ct_blobs
    ]

    if not check_buffer_overlaps(layers, ddr_base, all_scratch):
        sys.exit(1)

    if not check_binary_fits(layers, comp_dir):
        sys.exit(1)
    if not check_cpu_output_fits(
        dep_info,
        layers,
        ddr_base,
        suffix_to_idx,
        cpu_out,
        block_size,
        inp_elem_bytes=_elem_bytes(cfg.log_inp_width),
    ):
        sys.exit(1)

    # Per-layer isolation check: lay out the fsim golden bins above all live
    # allocations, then re-verify the layout (now including the golden regions).
    emit_check = args.emit_layer_check
    if emit_check:
        if not args.ref_dir:
            sys.exit("ERROR: --emit-layer-check requires --ref-dir")
        ref_dir = os.path.abspath(args.ref_dir)
        if not os.path.isdir(ref_dir):
            sys.exit(f"ERROR: --ref-dir not found: {ref_dir}")
        check_top = assign_layer_check_regions(
            layers, dep_info, ddr_base, ref_dir, alloc_top
        )
        print(
            f"[gen] isolation-check golden regions: 0x{_align_page(alloc_top):08X}"
            f"-0x{check_top:08X}"
        )
        if not check_buffer_overlaps(layers, ddr_base, all_scratch):
            sys.exit(1)

    os.makedirs(outdir, exist_ok=True)

    def out(filename: str) -> str:
        return os.path.join(outdir, filename)

    gen_hw_config_header(cfg, out("vta_hw_config.h"))
    gen_header(layers, ddr_base, out("nn_ddr_map.h"))
    gen_exec_plan_header(
        dep_info,
        layers,
        ddr_base,
        comp_dir,
        out("nn_exec_plan.h"),
        block_size,
        suffix_to_idx=suffix_to_idx,
        cpu_out=cpu_out,
        log_out_width=cfg.log_out_width,
        ct_params=ct_params,
    )
    gen_tcl(
        layers,
        ddr_base,
        comp_dir,
        out("load_nn_static.tcl"),
        dep_info=dep_info,
        include_input=False,
        extra_blobs=ct_blobs,
    )
    gen_tcl(
        layers,
        ddr_base,
        comp_dir,
        out("load_nn.tcl"),
        dep_info=dep_info,
        include_input=True,
        extra_blobs=ct_blobs,
    )
    gen_input_tcl(layers, ddr_base, comp_dir, out("load_input.tcl"))
    if args.emit_sd_manifest:
        gen_sd_manifest(
            layers,
            ddr_base,
            comp_dir,
            out("nn_sd_manifest.h"),
            out("sd_card"),
            sd_dir=args.sd_dir,
            emit_refs=emit_check,
            extra_blobs=ct_blobs,
        )
    gen_asm_incbin(
        layers, out("nn_bin_data.S"), emit_check=emit_check, extra_blobs=ct_blobs
    )
    gen_linker_fragment(
        layers,
        ddr_base,
        out("nn_vta_sections.ld"),
        emit_check=emit_check,
        extra_blobs=ct_blobs,
    )
    if emit_check:
        gen_debug_map(layers, out("nn_debug_map.h"))
    if args.emit_cpu_check:
        gen_cpu_debug_map(
            dep_info,
            layers,
            cfg,
            out("nn_cpu_debug_map.h"),
            suffix_to_idx,
            ddr_base,
            comp_dir,
        )

    if args.verbose:
        print_summary(layers, ddr_base)

    if args.max_addr:
        max_addr = int(args.max_addr, 16)
        if not check_memory_fit(layers, ddr_base, max_addr, comp_dir, all_scratch):
            sys.exit(1)
    else:
        print(
            "WARNING: --max-addr not given - DDR fit check skipped; allocations"
            " (incl. golden regions) are not verified to fit the board's mapped"
            " DRAM. Pass --max-addr <hex> to enable the check."
        )
