#!/usr/bin/env python3
"""Compare a baremetal VTA output dump against the functional simulator's
compiler_output/final_output.bin (the source of truth).

The board writes the output block-tiled; this detiles it to NCHW and diffs it
against final_output.bin (already NCHW).

The block layout mirrors output_tensor()/unsplit() in
src/simulators/functional_simulator/include/cpu_functions.h: blocks are laid out
row-major over (N/B row-blocks, C/B col-blocks); within a block element [rr][cc]
maps to (spatial row rr, channel cc). The matrix is [N=H*W rows, C cols].

Usage:
    python3 host/check_output.py <baremetal_out.bin> \\
        [--ref <compiler_output>/final_output.bin] \\
        [--comp-dir <compiler_output>] [--config-json <cfg>.json] \\
        [--shape C,H,W] [--block-size N]
"""

import argparse
import os
import sys

import numpy as np

import gen_nn_baremetal as gen

_HERE = os.path.dirname(__file__)
_DEF_COMP = os.path.join(_HERE, "..", "..", "..", "..", "compiler_output")
_DEF_CFG = os.path.join(_HERE, "..", "..", "..", "..", "config", "vta_config.json")


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def detile(raw: np.ndarray, C: int, H: int, W: int, B: int) -> np.ndarray:
    """Block-tiled [N/B][C/B][B][B] -> NCHW flat [C][H*W]. Drops padding cells."""
    N = H * W
    Cb = _ceil_div(C, B)
    expect = _ceil_div(N, B) * Cb * B * B
    if raw.size < expect:
        raise ValueError(f"raw output too small: {raw.size} < expected tiled {expect}")
    out = np.zeros(C * N, dtype=raw.dtype)
    for n in range(N):
        rb, rr = divmod(n, B)
        for c in range(C):
            cb, cc = divmod(c, B)
            out[c * N + n] = raw[(rb * Cb + cb) * B * B + rr * B + cc]
    return out


def report_diff(name: str, a: np.ndarray, b: np.ndarray) -> bool:
    """Diff two arrays; print stats; return True if identical."""
    n = min(a.size, b.size)
    if a.size != b.size:
        print(f"[{name}] SIZE DIFF: got {a.size} vs ref {b.size} (comparing first {n})")
    a32 = a[:n].astype(np.int32)
    b32 = b[:n].astype(np.int32)
    diff = a32 - b32
    nz = np.flatnonzero(diff)
    if a.size == b.size and nz.size == 0:
        print(f"[{name}] MATCH ({n} elements identical)")
        return True
    first = int(nz[0]) if nz.size else -1
    print(f"[{name}] MISMATCH: {nz.size}/{n} differ "
          f"({100.0 * nz.size / n:.3f}%), max|diff|={int(np.abs(diff).max())}, "
          f"first @ idx {first}")
    if first >= 0:
        lo, hi = max(0, first - 4), min(n, first + 12)
        print(f"        idx[{lo}:{hi}] got = {a32[lo:hi].tolist()}")
        print(f"        idx[{lo}:{hi}] ref = {b32[lo:hi].tolist()}")
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Compare baremetal VTA output to final_output.bin")
    p.add_argument("baremetal_out", help="raw output dump from the board (int8, block-tiled)")
    p.add_argument("--ref", default=None, help="reference NCHW bin (default <comp-dir>/final_output.bin)")
    p.add_argument("--comp-dir", default=_DEF_COMP)
    p.add_argument("--config-json", default=_DEF_CFG)
    p.add_argument("--shape", default=None, help="C,H,W override (else read from dependency.csv)")
    p.add_argument("--block-size", type=int, default=None)
    args = p.parse_args()

    cfg = gen.load_config_params(args.config_json, args.block_size)
    B = cfg.block_size

    if args.shape:
        C, H, W = (int(x) for x in args.shape.split(","))
    else:
        dep = gen.load_dependency_csv(os.path.join(args.comp_dir, "dependency.csv"))
        ld = dep.layers.get(dep.output_layer)
        if ld is None:
            sys.exit(f"ERROR: output layer '{dep.output_layer}' not in dependency.csv; pass --shape")
        C, H, W = ld.out_ch, ld.out_h, ld.out_w

    ref_path = args.ref or os.path.join(args.comp_dir, "final_output.bin")
    raw = np.fromfile(args.baremetal_out, dtype=np.int8)
    ref = np.fromfile(ref_path, dtype=np.int8)

    print(f"shape C,H,W = {C},{H},{W}  block={B}")
    print(f"baremetal raw: {raw.size} B   reference (NCHW): {ref.size} B   ({ref_path})\n")

    ok = report_diff("detiled vs NCHW ref", detile(raw, C, H, W, B), ref)
    print("\nRESULT:", "PASS - matches the functional simulator." if ok
          else "FAIL - output diverges from the functional simulator.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
