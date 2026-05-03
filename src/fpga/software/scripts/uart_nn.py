#!/usr/bin/env python3
"""
uart_nn.py — Host-side script for the VTA UART interactive inference loop.

Connects to the board over a serial port, waits for the READY sentinel,
sends a raw input file, and saves the raw output bytes.  Repeats for every
input file provided, or for --repeat iterations of the same file.

Protocol (board side implemented in run_nn.cc)
----------------------------------------------
  Board sends: "=== VTA NN runner: <N> step(s) ===\\r\\n"
  Board sends: "input=<N> out=<M>\\r\\n"
  Loop:
    Board sends: "READY\\r\\n"
    Host sends:  <input_n_bytes> raw HWC INT8 bytes (no framing)
    Board runs inference
    Board sends: <out_n_bytes> raw bytes

Usage
-----
  # Single run, output saved to out.bin:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin --output out.bin

  # Multiple inputs, outputs saved to results/:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input a.bin b.bin --output-dir results/

  # Repeat same input 5 times:
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin --repeat 5 --output-dir results/

  # Board already running (skip banner parsing):
  python3 scripts/uart_nn.py --port /dev/ttyUSB0 --input-bytes 150528 --output-bytes 200704 \\
      --input input_nn.bin --output out.bin

Dependencies
------------
  pip install pyserial
"""

import argparse
import re
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:
    sys.exit("ERROR: pyserial not installed.\n       Run: pip install pyserial")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

READY_SENTINEL = b"READY\r\n"
BANNER_TIMEOUT = 20.0  # seconds to wait for the startup banner


# ---------------------------------------------------------------------------
# Serial helpers
# ---------------------------------------------------------------------------


def read_line(ser: "serial.Serial", timeout: float = 10.0) -> bytes:
    """Read one \\n-terminated line from the serial port."""
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        ch = ser.read(1)
        if ch:
            buf += ch
            if ch == b"\n":
                return buf
    raise TimeoutError(f"Timeout waiting for newline; partial: {buf!r}")


def parse_banner(ser: "serial.Serial", timeout: float = BANNER_TIMEOUT):
    """Read lines until 'input=N out=M' is found; return (N, M) or (None, None)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            line = read_line(ser, timeout=max(0.1, remaining))
        except TimeoutError:
            break
        text = line.decode(errors="replace").strip()
        if text:
            print(f"[board] {text}")
        m = re.search(r"input=(\d+)\s+out=(\d+)", text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def wait_ready(ser: "serial.Serial", timeout: float = 60.0) -> None:
    """Block until READY\\r\\n is received, printing any intermediate lines."""
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        ch = ser.read(1)
        if not ch:
            continue
        buf += ch
        if buf.endswith(b"\n"):
            text = buf.decode(errors="replace").strip()
            if text and text != "READY":
                print(f"[board] {text}")
            if buf == READY_SENTINEL:
                return
            buf = b""
    raise TimeoutError("Timeout waiting for READY sentinel")


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


def drain_logs_until_output(ser: "serial.Serial", timeout: float, verbose: bool) -> None:
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
    wait_ready(ser, timeout=ready_timeout)
    if verbose:
        print(f"  [>] sending {len(input_data)} bytes …")
    send_bytes(ser, input_data, verbose=verbose)
    drain_logs_until_output(ser, timeout=ready_timeout, verbose=verbose)
    if verbose:
        print(f"  [<] receiving {out_n_bytes} bytes …")
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
        help="Baud rate.",
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
        help="Input size in bytes. Skips banner parsing when provided.",
    )
    parser.add_argument(
        "--output-bytes",
        type=int,
        metavar="N",
        help="Output size in bytes. Skips banner parsing when provided.",
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
    args = parser.parse_args()

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

    print(f"[uart] Opening {args.port} at {args.baud} baud …")
    ser = serial.Serial(args.port, args.baud, timeout=1.0)

    # Parse startup banner for sizes, unless both are given on the command line.
    input_n_bytes: int | None = args.input_bytes
    out_n_bytes: int | None = args.output_bytes

    if input_n_bytes is None or out_n_bytes is None:
        print(f"[uart] Waiting for board banner (up to {BANNER_TIMEOUT}s) …")
        bn, bo = parse_banner(ser)
        if input_n_bytes is None:
            input_n_bytes = bn
        if out_n_bytes is None:
            out_n_bytes = bo

    if input_n_bytes is None or out_n_bytes is None:
        ser.close()
        sys.exit(
            "ERROR: could not read input/output sizes from board banner.\n"
            "       Either reset the board so it re-sends the banner, or pass\n"
            "       --input-bytes and --output-bytes explicitly."
        )

    print(f"[uart] input={input_n_bytes} bytes  output={out_n_bytes} bytes")

    # Main loop.
    total_runs = len(inputs) * args.repeat
    run_idx = 0
    for inp_path in inputs:
        raw = inp_path.read_bytes()
        if len(raw) != input_n_bytes:
            print(
                f"WARNING: {inp_path.name} is {len(raw)} bytes but board expects "
                f"{input_n_bytes} — sending anyway"
            )

        for rep in range(args.repeat):
            run_idx += 1
            suffix = f"_r{rep}" if args.repeat > 1 else ""
            tag = f"{inp_path.stem}{suffix}"
            print(f"[run {run_idx}/{total_runs}] {tag}")

            out_data = run_inference(
                ser, raw, out_n_bytes, args.ready_timeout, args.verbose
            )

            if args.output:
                out_path = Path(args.output)
            elif out_dir:
                out_path = out_dir / f"{tag}_out.bin"
            else:
                out_path = Path(f"{tag}_out.bin")

            out_path.write_bytes(out_data)
            print(f"  saved {len(out_data)} bytes → {out_path}")

    ser.close()
    print("[uart] Done.")


if __name__ == "__main__":
    main()
