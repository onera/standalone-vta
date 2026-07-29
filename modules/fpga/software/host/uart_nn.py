#!/usr/bin/env python3
"""
uart_nn.py - Host-side script for the VTA UART interactive inference loop.

Connects to the board over a serial port, waits for the READY sentinel,
sends a raw input file, and saves the raw output bytes.  Repeats for every
input file provided, or for --repeat iterations of the same file.

Protocol (board side implemented in run_nn.cc)
----------------------------------------------
  Board sends: "=== VTA NN runner: <N> step(s) ===\\r\\n"   (once, at boot)
  Loop:
    Host sends:  trigger byte 0x01
    Board sends: "input=<N> out=<M>\\r\\n"
    Board sends: "READY\\r\\n"
    Host sends:  <input_n_bytes> raw HWC INT8 bytes (no framing)
    Board runs inference (prints per-step logs)
    Board sends: "OUTPUT\\r\\n"
    Board sends: <out_n_bytes> raw bytes

  The board is silent until it receives the trigger, so connecting at any time
  and sending 0x01 is enough to (re-)synchronise and get a fresh banner.

Usage
-----
  # Single run, output saved to out.bin:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin --output out.bin

  # Multiple inputs, outputs saved to results/:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input a.bin b.bin --output-dir results/

  # Repeat same input 5 times:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin --repeat 5 --output-dir results/

  # Override sizes (banner still consumed but sizes ignored):
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input-bytes 150528 --output-bytes 200704 \\
      --input input_nn.bin --output out.bin

  # De-tile VTA block output to NCHW flat for comparison with functional sim:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin --output out.bin \\
      --detile --output-shape 64,160,160 --block-size 16

Dependencies
------------
  pip install pyserial
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# De-tiling: VTA block layout -> NCHW flat
# ---------------------------------------------------------------------------


def detile(data: bytes, C: int, H: int, W: int, B: int = 8) -> bytes:
    """Convert VTA block-tiled INT8 output to NCHW flat.

    VTA block layout: [Nb][Cb][B][B] (row-major over Nb=ceil(N/B) row-blocks and
    Cb=ceil(C/B) col-blocks); within a block element [rr][cc] -> (spatial rr, channel cc).
    NCHW flat layout: [C][H*W] (channel-major).

    Pad-aware to match the source-of-truth unsplit()/output_tensor() in
    cpu_functions.h: when N=H*W or C is not a multiple of B the tiled buffer is
    zero-padded up to the block grid, and the padding cells are skipped here.
    """
    N = H * W
    Cb = (C + B - 1) // B
    Nb = (N + B - 1) // B
    tiled_len = Nb * Cb * B * B
    if len(data) < tiled_len:
        raise ValueError(
            f"detile: expected >= {tiled_len} tiled bytes (C={C} H={H} W={W} B={B}), "
            f"got {len(data)}"
        )
    out = bytearray(N * C)
    for row in range(N):
        rb, rr = divmod(row, B)
        for col in range(C):
            cbi, cc = divmod(col, B)
            out[col * N + row] = data[(rb * Cb + cbi) * B * B + rr * B + cc] & 0xFF
    return bytes(out)


def _check_output(
    raw_out: bytes, shape: "tuple[int,int,int]", block: int, ref_path: str
) -> None:
    """Detile the raw block-tiled output to NCHW (via this module's detile) and
    diff it against the reference bin. The richer standalone checker is
    `./mill vta.fpga.checkOutput`; this is the inline convenience path."""
    try:
        import numpy as np
    except Exception as exc:  # numpy not installed, etc.
        print(f"  [check] skipped: {exc}")
        return
    c, h, w = shape
    got = np.frombuffer(detile(raw_out, c, h, w, block), dtype=np.int8)
    ref = np.fromfile(ref_path, dtype=np.int8)
    print(f"  [check] vs {ref_path}  (C,H,W={c},{h},{w} block={block})")
    n = min(got.size, ref.size)
    if got.size != ref.size:
        print(f"  [check] SIZE DIFF: got {got.size} vs ref {ref.size} (comparing first {n})")
    diff = got[:n].astype(np.int32) - ref[:n].astype(np.int32)
    nz = np.flatnonzero(diff)
    if got.size == ref.size and nz.size == 0:
        print(f"  [check] PASS ({n} elements identical)")
    else:
        first = int(nz[0]) if nz.size else -1
        max_abs = int(np.abs(diff).max()) if diff.size else 0
        print(
            f"  [check] FAIL - {nz.size}/{n} differ, "
            f"max|diff|={max_abs}, first @ idx {first}"
        )


try:
    import serial
except ImportError:
    sys.exit("ERROR: pyserial not installed.\n       Run: pip install pyserial")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIGGER = b"\x01"
READY_SENTINEL = b"READY\r\n"
BANNER_TIMEOUT_DEFAULT = 40.0


# ---------------------------------------------------------------------------
# Serial helpers
# ---------------------------------------------------------------------------


def sync(
    ser: "serial.Serial", banner_timeout: float, verbose: bool
) -> "tuple[int | None, int | None]":
    """Send the trigger byte and read lines until READY.

    Parses the 'input=N out=M' banner line along the way.
    Returns (input_n_bytes, out_n_bytes); either may be None if the board did
    not send the banner before timing out.
    """
    ser.write(TRIGGER)
    in_b: "int | None" = None
    out_b: "int | None" = None
    deadline = time.monotonic() + banner_timeout
    buf = b""
    while time.monotonic() < deadline:
        ch = ser.read(1)
        if not ch:
            continue
        buf += ch
        if not buf.endswith(b"\n"):
            continue
        if buf == READY_SENTINEL:
            return in_b, out_b
        text = buf.decode(errors="replace").strip()
        if text:
            print(f"[board] {text}")
        m = re.search(r"input=(\d+)\s+out=(\d+)", text)
        if m:
            in_b, out_b = int(m.group(1)), int(m.group(2))
        buf = b""
    raise TimeoutError("Timeout waiting for READY after trigger")


def send_bytes(ser: "serial.Serial", data: bytes, verbose: bool = False) -> None:
    total = len(data)
    sent = 0
    chunk = 4096
    while sent < total:
        n = ser.write(data[sent : sent + chunk])
        sent += n
        if verbose:
            print(f"\r  tx {sent}/{total} bytes", end="", flush=True)
    if verbose:
        print()


def recv_bytes(ser: "serial.Serial", n_bytes: int, verbose: bool = False) -> bytes:
    buf = b""
    while len(buf) < n_bytes:
        chunk = ser.read(n_bytes - len(buf))
        buf += chunk
        if verbose:
            print(f"\r  rx {len(buf)}/{n_bytes} bytes", end="", flush=True)
    if verbose:
        print()
    return buf


OUTPUT_SENTINEL = b"OUTPUT\r\n"


def drain_logs_until_output(
    ser: "serial.Serial", timeout: float, verbose: bool
) -> None:
    """Read and optionally print text lines until the OUTPUT sentinel is received.

    The board sends all xil_printf step/cycle logs as text lines, then emits
    'OUTPUT\\r\\n' immediately before the raw binary payload.  Reading lines here
    prevents log bytes from being misinterpreted as binary output data.
    """
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        ch = ser.read(1)
        if not ch:
            continue
        buf += ch
        if buf.endswith(b"\n"):
            if buf == OUTPUT_SENTINEL:
                return
            if verbose:
                print(f"  [board] {buf.decode(errors='replace').rstrip()}")
            buf = b""
    raise TimeoutError("Timeout waiting for OUTPUT sentinel")


# ---------------------------------------------------------------------------
# Single inference run
# ---------------------------------------------------------------------------


def run_inference(
    ser: "serial.Serial",
    input_data: bytes,
    out_n_bytes: int,
    ready_timeout: float,
    verbose: bool,
) -> bytes:
    """Send input, drain inference logs, receive output. Call after sync()."""
    if verbose:
        print(f"  [>] sending {len(input_data)} bytes ...")
    send_bytes(ser, input_data, verbose=verbose)
    drain_logs_until_output(ser, timeout=ready_timeout, verbose=verbose)
    if verbose:
        print(f"  [<] receiving {out_n_bytes} bytes ...")
    return recv_bytes(ser, out_n_bytes, verbose=verbose)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send inputs to the VTA UART inference loop and collect outputs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--port",
        required=True,
        metavar="DEV",
        help="Serial device (e.g. /dev/ttyUSB0 or COM3).",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        metavar="N",
        help="Baud rate (must match VTA_UART_BAUD compiled into the firmware).",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        metavar="FILE",
        help="Raw input file(s). Each file is one inference run.",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Output file path (single-run shorthand).",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Directory for per-run output files (named <input_stem>_out.bin).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help="Repeat each input file N times.",
    )
    parser.add_argument(
        "--input-bytes",
        type=int,
        metavar="N",
        help="Override input size in bytes (banner value is still consumed but ignored).",
    )
    parser.add_argument(
        "--output-bytes",
        type=int,
        metavar="N",
        help="Override output size in bytes (banner value is still consumed but ignored).",
    )
    parser.add_argument(
        "--banner-timeout",
        type=float,
        default=BANNER_TIMEOUT_DEFAULT,
        metavar="SEC",
        help="Seconds to wait for the startup banner (input=N out=M line).",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=60.0,
        metavar="SEC",
        help="Seconds to wait for the READY sentinel before each run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print byte-level transfer progress.",
    )
    parser.add_argument(
        "--detile",
        action="store_true",
        help="De-tile VTA block output to NCHW flat before saving "
        "(for comparison with functional-sim final_output.bin).",
    )
    parser.add_argument(
        "--output-shape",
        metavar="C,H,W",
        help="Output tensor shape as 'C,H,W' (required with --detile).",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=16,
        metavar="B",
        help="VTA block size for de-tiling (default: 16).",
    )
    parser.add_argument(
        "--check",
        nargs="?",
        const="",
        default=None,
        metavar="REF",
        help="After each run, compare the raw output against a reference NCHW bin "
        "(functional-sim final_output.bin). With no value, uses "
        "../../../../simulators_output/final_output.bin relative to this script. "
        "Requires --output-shape (or it is read from dependency.csv).",
    )
    args = parser.parse_args()

    if args.detile and not args.output_shape:
        sys.exit("ERROR: --detile requires --output-shape C,H,W")
    detile_shape: "tuple[int,int,int] | None" = None
    if args.detile:
        try:
            c, h, w = (int(x) for x in args.output_shape.split(","))
            detile_shape = (c, h, w)
        except ValueError:
            sys.exit(
                "ERROR: --output-shape must be three comma-separated integers, e.g. 64,160,160"
            )

    # Resolve reference + shape for --check (compares raw output to functional sim).
    check_ref: "str | None" = None
    check_shape: "tuple[int,int,int] | None" = None
    if args.check is not None:
        here = Path(__file__).resolve().parent
        check_ref = args.check or str(
            here / ".." / ".." / ".." / ".." / "simulators_output" / "final_output.bin"
        )
        if not Path(check_ref).exists():
            sys.exit(f"ERROR: --check reference not found: {check_ref}")
        if detile_shape is not None:
            check_shape = detile_shape
        elif args.output_shape:
            c, h, w = (int(x) for x in args.output_shape.split(","))
            check_shape = (c, h, w)
        else:
            # Auto-read the output shape from the compiler's dependency.csv,
            # whose "output" row is: output,<layer name>,<C>,<H>,<W>.
            dep_csv = here / ".." / ".." / ".." / ".." / "compiler_output" / "dependency.csv"
            try:
                with open(dep_csv, newline="", encoding="utf-8") as f:
                    row = next(r for r in csv.reader(f) if r and r[0] == "output")
                check_shape = (int(row[2]), int(row[3]), int(row[4]))
            except Exception as exc:
                sys.exit(
                    f"ERROR: --check needs --output-shape (could not auto-read {dep_csv}: {exc})"
                )

    # Validate inputs.
    inputs = [Path(p) for p in args.input]
    for p in inputs:
        if not p.exists():
            sys.exit(f"ERROR: input file not found: {p}")

    if args.output and len(inputs) * args.repeat > 1:
        sys.exit(
            "ERROR: --output is for a single run; use --output-dir for multiple runs."
        )

    out_dir = Path(args.output_dir) if args.output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[uart] Opening {args.port} at {args.baud} baud ...")
    ser = serial.Serial(args.port, args.baud, timeout=1.0)

    # Sizes are discovered from the banner on the first run, or overridden by flags.
    input_n_bytes: "int | None" = args.input_bytes
    out_n_bytes: "int | None" = args.output_bytes

    # Main loop.
    total_runs = len(inputs) * args.repeat
    run_idx = 0
    for inp_path in inputs:
        raw = inp_path.read_bytes()

        for rep in range(args.repeat):
            run_idx += 1
            suffix = f"_r{rep}" if args.repeat > 1 else ""
            tag = f"{inp_path.stem}{suffix}"
            print(f"[run {run_idx}/{total_runs}] {tag}")

            # Trigger the board and parse the banner to get/confirm sizes.
            parsed_in, parsed_out = sync(ser, args.banner_timeout, args.verbose)
            if input_n_bytes is None:
                if parsed_in is None:
                    ser.close()
                    sys.exit(
                        "ERROR: board did not send input size in banner.\n"
                        "       Pass --input-bytes to override."
                    )
                input_n_bytes = parsed_in
                print(f"[uart] input={input_n_bytes} bytes  output={parsed_out} bytes")
            if out_n_bytes is None:
                if parsed_out is None:
                    ser.close()
                    sys.exit(
                        "ERROR: board did not send output size in banner.\n"
                        "       Pass --output-bytes to override."
                    )
                out_n_bytes = parsed_out

            if len(raw) != input_n_bytes:
                print(
                    f"WARNING: {inp_path.name} is {len(raw)} bytes but board expects "
                    f"{input_n_bytes} - sending anyway"
                )

            out_data = run_inference(
                ser, raw, out_n_bytes, args.ready_timeout, args.verbose
            )
            raw_out = out_data  # block-tiled bytes, before any detile

            if check_shape is not None:
                _check_output(raw_out, check_shape, args.block_size, check_ref)

            if args.output:
                out_path = Path(args.output)
            elif out_dir:
                out_path = out_dir / f"{tag}_out.bin"
            else:
                out_path = Path(f"{tag}_out.bin")

            if detile_shape is not None:
                c, h, w = detile_shape
                try:
                    out_data = detile(out_data, c, h, w, args.block_size)
                    print(f"  de-tiled -> NCHW [{c},{h},{w}]  ({len(out_data)} bytes)")
                except ValueError as exc:
                    sys.exit(f"ERROR: detile failed: {exc}")

            out_path.write_bytes(out_data)
            print(f"  saved {len(out_data)} bytes -> {out_path}")

    ser.close()
    print("[uart] Done.")


if __name__ == "__main__":
    main()
