#!/usr/bin/env python3
"""Static DRAM-layout guard for the VTA baremetal path.

Builds the exact layout the generator emits (via the nnbaremetal package) and
runs the layout guard checks: buffer overlaps, static binaries fitting their
slots, CPU-op outputs fitting the VTA region they feed, and -with --max-addr-
every allocation fitting the board's mapped DRAM. Prints a DRAM map. Exit status
is non-zero if any check fails.

The generator (gen_nn_baremetal) calls the same checks as a pre-emit guard; this
script is the standalone entry for auditing a compiler_output directory, e.g. to
sanity-check a non-zero --ddr-base relocation (fsim/compiler use 0x0).

Usage:
    python3 host/audit_dram.py <compiler_output_dir> \\
        [--ddr-base 0x10000000] [--config-json <cfg>.json] \\
        [--block-size 16] [--max-addr 0x40000000]
"""

import argparse
import os
import sys

from nnbaremetal.config import load_config_params, _elem_bytes
from nnbaremetal.parse import load_dependency_csv, collect_layers
from nnbaremetal.layout import _build_cpu_out_addrs
from nnbaremetal.checks import (check_buffer_overlaps, check_binary_fits,
                                check_cpu_output_fits, check_memory_fit,
                                print_summary)


def run_guard_checks(dep_info, layers, ddr_base, suffix_to_idx, cpu_out,
                     cpu_scratch, cfg, comp_dir, max_addr=None) -> bool:
    """Run every layout guard. Returns True only if all pass."""
    ok = check_buffer_overlaps(layers, ddr_base, cpu_scratch)
    ok = check_binary_fits(layers, comp_dir) and ok
    ok = check_cpu_output_fits(dep_info, layers, ddr_base, suffix_to_idx,
                               cpu_out, cfg.block_size,
                               _elem_bytes(cfg.log_inp_width)) and ok
    if max_addr is not None:
        ok = check_memory_fit(layers, ddr_base, max_addr, comp_dir, cpu_scratch) and ok
    return ok


def audit(comp_dir, ddr_base, config_json, block_size, max_addr=None) -> int:
    cfg = load_config_params(config_json, block_size)
    dep_info = load_dependency_csv(os.path.join(comp_dir, "dependency.csv"))
    vta_suffixes = [n for _, proc, n in dep_info.execution_order if proc == "vta"]
    layers = collect_layers(comp_dir, vta_suffixes)
    for layer in layers:
        ld = dep_info.layers.get(layer.suffix)
        if ld:
            layer.reshape_info = ld.reshape_info
    suffix_to_idx = {layer.suffix: i for i, layer in enumerate(layers)}
    cpu_out, _alloc_top, cpu_scratch = _build_cpu_out_addrs(
        dep_info, layers, ddr_base, suffix_to_idx, comp_dir)

    print(f"=== VTA DRAM audit (base 0x{ddr_base:08X}, block {cfg.block_size}) ===")
    ok = run_guard_checks(dep_info, layers, ddr_base, suffix_to_idx, cpu_out,
                          cpu_scratch, cfg, comp_dir, max_addr)
    print_summary(layers, ddr_base)
    if max_addr is None:
        print("\nNote: pass --max-addr <hex> to verify allocations fit mapped DRAM.")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Static DRAM-layout guard for VTA baremetal.")
    p.add_argument("comp_dir", help="compiler_output directory")
    p.add_argument("--ddr-base", default="0x0", help="baremetal DDR base (default 0x0)")
    p.add_argument(
        "--config-json",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                             "config", "vta_config.json"),
        help="VTA hardware config JSON (element widths / block size)",
    )
    p.add_argument("--block-size", type=int, default=None, help="override block size")
    p.add_argument("--max-addr", default=None, help="board DRAM ceiling (hex) to enable the fit check")
    args = p.parse_args()
    max_addr = int(args.max_addr, 0) if args.max_addr else None
    return audit(args.comp_dir, int(args.ddr_base, 0), args.config_json,
                 args.block_size, max_addr)


if __name__ == "__main__":
    sys.exit(main())
