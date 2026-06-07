#!/usr/bin/env python3
"""Strb-aware comparison of an xsim post-synth run's OUT writes against the fsim golden.

Reads writes.log (lines "addr data strb last", produced by sim_top.sv from the io_dbgW
AXI write snoop), reconstructs each layer's OUT buffer byte-by-byte applying the per-beat
write strobe, and compares to simulators_output/output<layer>.bin.

Address model (mirrors CompilerOutputLayout): every layer L (0-based position in --layers)
is relocated by relo = L * reloStride. A beat at absolute byte address A belongs to layer
L = A // reloStride; its offset into that layer's OUT buffer is
    A - L*reloStride - OUT_base
where OUT_base is the "OUT" row of compiler_output/memory_addresses<layer>.csv.

Usage:
  compare_out.py --writes <run>/writes.log --layers MaxPool2,QLinearConv10,QLinearConv7 \
                 --compiler-out <repo>/examples/compiler_output \
                 --golden-dir   <repo>/.../simulators_output \
                 [--relo-stride 0x200000]
"""
import argparse
import os
import sys


def out_base(compiler_out, layer):
    path = os.path.join(compiler_out, f"memory_addresses{layer}.csv")
    with open(path) as f:
        for line in f:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0] == "OUT":
                return int(parts[1], 16)
    raise SystemExit(f"no OUT row in {path}")


def parse_writes(writes_path, relo_stride):
    """-> {layer_idx: {abs_byte_addr: byte_value}} applying strb per beat."""
    per_layer = {}
    with open(writes_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            a, d, s, _last = line.split()
            addr = int(a, 16)
            data = int(d, 16)          # 64-bit, little-endian byte i = bits [8i,8i+8)
            strb = int(s, 16)          # 8-bit lane mask
            lidx = addr // relo_stride
            bucket = per_layer.setdefault(lidx, {})
            for i in range(8):
                if strb & (1 << i):
                    bucket[addr + i] = (data >> (8 * i)) & 0xFF
    return per_layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--writes", required=True)
    ap.add_argument("--layers", required=True, help="comma-separated, in emit order")
    ap.add_argument("--compiler-out", required=True)
    ap.add_argument("--golden-dir", required=True)
    ap.add_argument("--relo-stride", default="0x200000")
    ap.add_argument("--show", type=int, default=8, help="how many mismatches to print")
    args = ap.parse_args()

    global reloStride
    reloStride = int(args.relo_stride, 16)
    layers = [s.strip() for s in args.layers.split(",") if s.strip()]
    per_layer = parse_writes(args.writes, reloStride)

    all_ok = True
    for idx, layer in enumerate(layers):
        golden_path = os.path.join(args.golden_dir, f"output{layer}.bin")
        if not os.path.exists(golden_path):
            print(f"[{layer}] SKIP - no golden {golden_path}")
            continue
        golden = open(golden_path, "rb").read()
        base = out_base(args.compiler_out, layer)
        relo = idx * reloStride
        written = per_layer.get(idx, {})

        matched = 0
        mism = []
        for off in range(len(golden)):
            abs_addr = relo + base + off
            got = written.get(abs_addr, None)
            exp = golden[off]
            if got is not None and got == exp:
                matched += 1
            elif len(mism) < args.show:
                mism.append((off, exp, got))
        ok = matched == len(golden)
        all_ok &= ok
        verdict = "OK" if ok else "MISMATCH"
        print(f"[{layer}] {matched}/{len(golden)} bytes  base=0x{base:x} relo=0x{relo:x}  {verdict}")
        for off, exp, got in mism:
            gs = "----" if got is None else f"0x{got:02x}"
            print(f"    off {off:6d}: golden=0x{exp:02x} got={gs}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
