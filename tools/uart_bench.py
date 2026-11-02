#!/usr/bin/env python3
"""
uart_bench.py - repeat one model many times over the run_nn_uart loop and
turn the board's own [time] table into statistics.

The firmware already reports everything we need: vta::run_nn() buffers a
per-step timing row for the whole inference and dumps the table in one go
just before the OUTPUT sentinel (driver/src/vta_nn.cc).  Those rows are
printed unconditionally - `uart_nn.py --verbose` only decides whether the
host *echoes* them - so nothing on the board has to change to measure it.
Buffering matters: an xil_printf blocks until the line has shifted out, so
logging a step as it happens would cost more than the step.

This script speaks the same protocol as uart_nn.py (trigger 0x01, banner,
READY, raw input, logs, OUTPUT, raw output) but keeps the log lines instead
of discarding them, and records a host-side wall clock alongside the board's
numbers.  It is deliberately self-contained: the protocol is ~40 lines and
duplicating it keeps the benchmark from perturbing the runner it measures.

Outputs, under <out-dir>/<tag>-<timestamp>/:
    raw.log    every board line, verbatim, run by run
    runs.csv   one row per run (host + board totals, output digest)
    steps.csv  one row per (run, step)
    stats.md   the summary you actually read

Usage:
    ./tools/uart_bench.py --port /dev/ttyUSB1 --baud 2000000 \
        --input out/examples/onnx/qyolo/vta_8b_block32/reference.dest/input_nn.bin \
        --runs 100 --tag qyolo-sd
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    sys.exit("ERROR: pyserial not installed. Run this under `pixi run`.")

# 0x01 uploads a fresh input then runs; 0x02 reruns on the input already in
# the board's raw buffer (run_nn_uart.cc). The upload is ~half the round trip
# for qyolo, so --reuse-input is what isolates inference cost from UART cost.
TRIG_LOAD = b"\x01"
TRIG_RERUN = b"\x02"
READY = b"READY\r\n"
OUTPUT = b"OUTPUT\r\n"

# [time] 12 conv2d_3                      1234 us  vta 5678 cyc (910 compute)
RE_STEP_VTA = re.compile(
    r"^\[time\]\s+(\d+)\s+(\S+)\s+(\d+) us\s+vta (\d+) cyc \((\d+) compute\)$"
)
# [time] 13 im2row_3                        456 us  cpu
RE_STEP_CPU = re.compile(r"^\[time\]\s+(\d+)\s+(\S+)\s+(\d+) us\s+cpu$")
RE_TOTAL = re.compile(
    r"^\[time\] TOTAL (\d+) us = VTA (\d+) us \+ CPU (\d+) us \(CPU (\d+)%\)$"
)
RE_BANNER = re.compile(r"input=(\d+)\s+out=(\d+)")


class BoardError(RuntimeError):
    pass


class Reader:
    """Buffered reader over the serial port.

    Byte-at-a-time ser.read(1) cannot keep up with the board's log burst: the
    firmware buffers its whole [time] table and shifts it out in one go, which
    at 2 Mbaud is ~20 KB in ~0.1 s, and one syscall per byte overruns the
    kernel tty buffer - a first version silently lost ~30% of the step rows
    and still produced plausible-looking statistics.

    So fill in bulk and split lines here. The leftover buffer is the reason
    this is a class rather than two functions: a bulk read can run past the
    OUTPUT sentinel into the binary payload, and read_exact() must consume
    those already-read bytes before touching the port again.
    """

    def __init__(self, ser):
        self.ser = ser
        self.buf = b""

    def _fill(self, deadline: float) -> None:
        while True:
            waiting = self.ser.in_waiting
            chunk = self.ser.read(waiting if waiting > 0 else 1)
            if chunk:
                self.buf += chunk
                return
            if time.monotonic() > deadline:
                raise BoardError("timeout waiting for board data")

    def read_line(self, deadline: float) -> bytes:
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line, self.buf = self.buf[: i + 1], self.buf[i + 1 :]
                return line
            self._fill(deadline)

    def read_exact(self, n: int, deadline: float) -> bytes:
        while len(self.buf) < n:
            self._fill(deadline)
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def write(self, data: bytes) -> None:
        sent = 0
        while sent < len(data):
            sent += self.ser.write(data[sent : sent + 4096])

    def reset(self) -> None:
        self.buf = b""
        self.ser.reset_input_buffer()


def sync(
    rd: Reader,
    timeout: float,
    log,
    trigger: bytes = TRIG_LOAD,
    allow_boot: bool = False,
) -> "tuple[int, int]":
    """Trigger the board and read lines until READY; return (in_bytes, out_bytes)."""
    rd.write(trigger)
    in_b = out_b = None
    deadline = time.monotonic() + timeout
    while True:
        line = rd.read_line(deadline)
        if line == READY:
            if in_b is None or out_b is None:
                raise BoardError("READY without an input=/out= banner")
            return in_b, out_b
        text = line.decode(errors="replace").rstrip()
        if text:
            log(text)
        if "VTA NN runner" in text:
            # Board just (re)booted, so it never saw our trigger. Expected on
            # the first run (it was only just flashed/powered), fatal after
            # that: a reboot empties the raw input buffer, so a later rerun
            # trigger would silently compute on whatever is left there.
            if not allow_boot:
                raise BoardError("board rebooted mid-benchmark")
            rd.write(trigger)
        m = RE_BANNER.search(text)
        if m:
            in_b, out_b = int(m.group(1)), int(m.group(2))


# The firmware reports a failed inference and then skips its output entirely
# (run_nn_uart.cc: "inference failed, skipping output" -> continue). Waiting for
# an OUTPUT sentinel that will never arrive costs the whole ready-timeout per
# run, so treat these as an immediate failure instead.
FATAL_MARKERS = (
    "malloc failed",
    "inference failed",
    "bad layer_idx",
    "run_layer: TIMEOUT",
    "SD static-model load failed",
)


def drain_until_output(rd: Reader, timeout: float, log) -> "list[str]":
    """Collect log lines until the OUTPUT sentinel. These carry the [time] table."""
    lines = []
    deadline = time.monotonic() + timeout
    while True:
        line = rd.read_line(deadline)
        if line == OUTPUT:
            return lines
        text = line.decode(errors="replace").rstrip()
        lines.append(text)
        log(text)
        for marker in FATAL_MARKERS:
            if marker in text:
                raise BoardError(f"board aborted the run: {text.strip()}")


def parse_timing(lines: "list[str]") -> dict:
    """Pull the per-step rows and the TOTAL line out of one run's log."""
    steps, totals = [], None
    for text in lines:
        m = RE_STEP_VTA.match(text)
        if m:
            steps.append(
                {
                    "step": int(m.group(1)),
                    "name": m.group(2),
                    "kind": "vta",
                    "us": int(m.group(3)),
                    "ecnt": int(m.group(4)),
                    "ucnt": int(m.group(5)),
                }
            )
            continue
        m = RE_STEP_CPU.match(text)
        if m:
            steps.append(
                {
                    "step": int(m.group(1)),
                    "name": m.group(2),
                    "kind": "cpu",
                    "us": int(m.group(3)),
                    "ecnt": "",
                    "ucnt": "",
                }
            )
            continue
        m = RE_TOTAL.match(text)
        if m:
            totals = {
                "total_us": int(m.group(1)),
                "vta_us": int(m.group(2)),
                "cpu_us": int(m.group(3)),
                "cpu_pct": int(m.group(4)),
            }
    return {"steps": steps, "totals": totals}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def pctl(values: "list[float]", q: float) -> float:
    """Nearest-rank percentile. n is ~100 here, so no interpolation games."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]


def describe(values: "list[float]") -> dict:
    if not values:
        return {}
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    return {
        "n": n,
        "mean": mean,
        "median": statistics.median(values),
        "stdev": sd,
        "cv_pct": (sd / mean * 100.0) if mean else 0.0,
        "min": min(values),
        "max": max(values),
        "p95": pctl(values, 0.95),
    }


def fmt_row(label: str, d: dict) -> str:
    if not d:
        return f"| {label} | - | - | - | - | - | - | - |"
    return (
        f"| {label} | {d['n']} | {d['mean']:.1f} | {d['median']:.1f} | "
        f"{d['stdev']:.1f} | {d['cv_pct']:.2f}% | {d['min']:.0f} | "
        f"{d['max']:.0f} | {d['p95']:.0f} |"
    )


def write_stats(path: Path, meta: dict, runs: list, per_step: dict) -> str:
    ok = [r for r in runs if r["status"] == "ok"]
    lines = [
        f"# UART inference benchmark - {meta['tag']}",
        "",
        f"- date: {meta['started']}",
        f"- port: `{meta['port']}` @ {meta['baud']} baud",
        f"- input: `{meta['input']}` ({meta['input_bytes']} bytes)",
        f"- input upload: {'once, then rerun on the resident copy (0x02)' if meta['reuse_input'] else 'every run (0x01)'}",
        f"- board reports: input={meta['banner_in']} out={meta['banner_out']} bytes",
        f"- runs requested: {meta['runs']}, completed: {len(ok)}, "
        f"failed: {len(runs) - len(ok)}",
        f"- step rows per run: {meta['expected_steps']} "
        f"(every completed run delivered a full [time] table)",
        f"- wall clock: {meta['wall_s']:.1f} s",
        "",
        "All times in microseconds. `board total/vta/cpu` are the firmware's own",
        "`[time] TOTAL` line; `host *` are measured on this machine and include",
        "the UART payload transfers, which dominate at any baud rate.",
        "",
        "## Aggregate",
        "",
        "| metric | n | mean | median | stdev | cv | min | max | p95 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    # Board timings are per-inference and unaffected by how the input got
    # there, so they average over every run. Host timings are not: in
    # --reuse-input mode run 1 pays the whole upload and the other 99 pay
    # none, and averaging the two together reports a round trip that no run
    # ever took (mean 6.47 s for a set where 99 runs took 6.40 s).
    host_rows = [r for r in ok if not (meta["reuse_input"] and int(r["loaded"]))]
    host_note = (
        " (reruns only; the single upload run is broken out below)"
        if meta["reuse_input"]
        else ""
    )
    for label, key, rows_for in [
        ("board total", "total_us", ok),
        ("board vta", "vta_us", ok),
        ("board cpu", "cpu_us", ok),
        ("host send" + host_note, "host_send_us", host_rows),
        ("host infer+logs", "host_infer_us", host_rows),
        ("host recv", "host_recv_us", host_rows),
        ("host round-trip", "host_round_us", host_rows),
    ]:
        lines.append(
            fmt_row(label, describe([r[key] for r in rows_for if r.get(key) != ""]))
        )

    if meta["reuse_input"]:
        up = [r for r in ok if int(r["loaded"])]
        if up:
            u = up[0]
            lines += [
                "",
                f"The one upload run (run {u['run']}) took "
                f"{u['host_send_us']/1e6:.3f} s to push {meta['input_bytes']} bytes "
                f"and {u['host_round_us']/1e6:.3f} s round trip, against "
                f"{statistics.fmean([r['host_round_us'] for r in host_rows])/1e6:.3f} s "
                f"for the {len(host_rows)} reruns.",
            ]

    digests = {r["out_sha256"] for r in ok}
    lines += [
        "",
        "## Output determinism",
        "",
        f"{len(digests)} distinct output digest(s) across {len(ok)} successful run(s)"
        + (" - every run returned the same bytes." if len(digests) == 1 else "."),
        "",
    ]
    for d in sorted(digests):
        count = sum(1 for r in ok if r["out_sha256"] == d)
        lines.append(f"- `{d}` x{count}")

    if per_step:
        lines += [
            "",
            "## Per-step cost (sorted by mean, top 40)",
            "",
            "| step | name | kind | n | mean | median | stdev | cv | min | max | p95 |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        ranked = sorted(
            per_step.items(), key=lambda kv: statistics.fmean(kv[1]["us"]), reverse=True
        )
        for (idx, name), rec in ranked[:40]:
            d = describe(rec["us"])
            lines.append(
                f"| {idx} | {name} | {rec['kind']} | {d['n']} | {d['mean']:.1f} | "
                f"{d['median']:.1f} | {d['stdev']:.1f} | {d['cv_pct']:.2f}% | "
                f"{d['min']:.0f} | {d['max']:.0f} | {d['p95']:.0f} |"
            )
        if len(ranked) > 40:
            lines.append("")
            lines.append(f"({len(ranked) - 40} further steps in `steps.csv`.)")

    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--port", required=True)
    p.add_argument("--baud", type=int, default=2000000)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--runs", type=int, default=100)
    p.add_argument("--tag", required=True, help="Name for the results directory.")
    p.add_argument("--out-dir", type=Path, default=Path("results"))
    p.add_argument("--banner-timeout", type=float, default=60.0)
    p.add_argument("--ready-timeout", type=float, default=300.0)
    p.add_argument("--quiet", action="store_true", help="Do not echo board lines.")
    p.add_argument(
        "--reuse-input",
        action="store_true",
        help="Upload the input once, then rerun on the board's resident copy "
        "(trigger 0x02). Isolates inference cost from the UART upload. "
        "Requires the run_nn_uart build that understands 0x02.",
    )
    p.add_argument(
        "--expect-steps",
        type=int,
        default=None,
        help="Expected number of [time] step rows. Default: learn it from the "
        "first run; any later run that disagrees is recorded as failed.",
    )
    p.add_argument(
        "--save-output",
        type=Path,
        default=None,
        help="Write the first successful run's raw (block-tiled) output here, "
        "e.g. to check it with `./mill examples.onnx[<model>,<config>]"
        ".checkBoardOutput`.",
    )
    args = p.parse_args()

    # A leftover from an earlier session must not pass for this one's output,
    # even if this one fails before its first run.
    if args.save_output:
        args.save_output.unlink(missing_ok=True)
    raw = args.input.read_bytes()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = args.out_dir / f"{args.tag}-{stamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    raw_log = (outdir / "raw.log").open("w", encoding="utf-8")

    def log(text: str) -> None:
        raw_log.write(text + "\n")
        raw_log.flush()
        if not args.quiet:
            print(f"  [board] {text}", flush=True)

    print(f"[bench] {args.port} @ {args.baud} baud, {args.runs} runs -> {outdir}")
    ser = serial.Serial(args.port, args.baud, timeout=1.0)
    rd = Reader(ser)

    runs: list = []
    per_step: dict = {}
    banner_in = banner_out = None
    expected_steps = args.expect_steps
    saved = False
    t_wall = time.monotonic()

    for i in range(1, args.runs + 1):
        raw_log.write(f"--- run {i}/{args.runs} ---\n")
        print(f"[run {i}/{args.runs}]", flush=True)
        rec = {"run": i, "status": "ok", "error": ""}
        try:
            load = (not args.reuse_input) or i == 1
            t0 = time.monotonic()
            in_b, out_b = sync(
                rd,
                args.banner_timeout,
                log,
                TRIG_LOAD if load else TRIG_RERUN,
                allow_boot=(i == 1),
            )
            banner_in, banner_out = in_b, out_b
            if len(raw) != in_b:
                print(
                    f"WARNING: input is {len(raw)} bytes, board expects {in_b}",
                    flush=True,
                )
            t1 = time.monotonic()
            if load:
                rd.write(raw)
            t2 = time.monotonic()
            lines = drain_until_output(rd, args.ready_timeout, log)
            t3 = time.monotonic()
            data = rd.read_exact(out_b, time.monotonic() + args.ready_timeout)
            t4 = time.monotonic()

            parsed = parse_timing(lines)
            if parsed["totals"] is None:
                raise BoardError("no [time] TOTAL line in this run's log")
            n_steps = len(parsed["steps"])
            if expected_steps is None:
                expected_steps = n_steps
            elif n_steps != expected_steps:
                # Dropped UART bytes truncate the table. Counting the run
                # anyway would bias every per-step statistic downward without
                # any visible symptom, so mark it and keep it out of the stats.
                raise BoardError(
                    f"incomplete [time] table: {n_steps} step rows, "
                    f"expected {expected_steps} (dropped UART bytes?)"
                )
            rec.update(parsed["totals"])
            rec.update(
                {
                    "host_sync_us": (t1 - t0) * 1e6,
                    "host_send_us": (t2 - t1) * 1e6,
                    "host_infer_us": (t3 - t2) * 1e6,
                    "host_recv_us": (t4 - t3) * 1e6,
                    "host_round_us": (t4 - t0) * 1e6,
                    "loaded": int(load),
                    "out_bytes": len(data),
                    "out_sha256": hashlib.sha256(data).hexdigest(),
                    "n_steps": len(parsed["steps"]),
                }
            )
            for s in parsed["steps"]:
                key = (s["step"], s["name"])
                rec_s = per_step.setdefault(key, {"kind": s["kind"], "us": []})
                rec_s["us"].append(s["us"])
                s["run"] = i
            rec["_steps"] = parsed["steps"]
            if args.save_output and not saved:
                args.save_output.write_bytes(data)
                saved = True
            print(
                f"  total {rec['total_us']} us (vta {rec['vta_us']}, "
                f"cpu {rec['cpu_us']}), host round {rec['host_round_us']/1000:.0f} ms",
                flush=True,
            )
        except (BoardError, OSError) as exc:
            rec["status"] = "failed"
            rec["error"] = str(exc)
            rec["_steps"] = []
            print(f"  FAILED: {exc}", flush=True)
            log(f"[bench] run {i} failed: {exc}")
            rd.reset()
        runs.append(rec)

    ser.close()
    wall_s = time.monotonic() - t_wall
    raw_log.close()

    run_fields = [
        "run", "status", "loaded", "total_us", "vta_us", "cpu_us", "cpu_pct",
        "host_sync_us", "host_send_us", "host_infer_us", "host_recv_us",
        "host_round_us", "out_bytes", "out_sha256", "n_steps", "error",
    ]
    with (outdir / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=run_fields, extrasaction="ignore")
        w.writeheader()
        for r in runs:
            w.writerow(r)

    with (outdir / "steps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run", "step", "name", "kind", "us", "ecnt", "ucnt"])
        w.writeheader()
        for r in runs:
            for s in r["_steps"]:
                w.writerow(s)

    meta = {
        "tag": args.tag,
        "started": stamp,
        "port": args.port,
        "baud": args.baud,
        "input": str(args.input),
        "input_bytes": len(raw),
        "banner_in": banner_in,
        "banner_out": banner_out,
        "runs": args.runs,
        "reuse_input": args.reuse_input,
        "expected_steps": expected_steps,
        "wall_s": wall_s,
    }
    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    text = write_stats(outdir / "stats.md", meta, runs, per_step)
    print("\n" + text)
    print(f"[bench] results in {outdir}")
    # Failed runs are recorded and left out of the statistics; a session with
    # none left measured nothing, and a caller must not take it for a result.
    if not any(r["status"] == "ok" for r in runs):
        sys.exit(1)


if __name__ == "__main__":
    main()
