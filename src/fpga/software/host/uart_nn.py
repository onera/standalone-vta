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

TRIGGER = b"\x01"
READY_SENTINEL = b"READY\r\n"
BANNER_TIMEOUT_DEFAULT = 20.0


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
    """Send input, drain inference logs, receive output. Call after sync()."""
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
        default=921600,
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
