"""One board leg end to end, and resumable campaigns of them.

A leg is mill tasks around two uart_bench sessions:

  buildVitisApp, flashBoard, runInfo      (mill)
  one capture with --save-output          (uart_bench)
  checkBoardOutput: board output vs fsim  (mill, gates what follows)
  the measurement, per mode               (uart_bench)

mill runs one command at a time per out/, so the UART sessions, which take
minutes to hours, run outside it and the other board's process never waits on
them.
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from . import board
from .board import BoardError, jtag_lock
from .matrix import Leg
from .mill import (MILL_TIMEOUT, expected_options, leg_props, mill_cmd,
                   mill_defaults, non_default, target, vta_options)
from .record import write_experiment
from .runner import Runner
from .settings import Settings

RUNNER = "run_nn_uart"
BUILD_TIMEOUT = 5400
FLASH_TIMEOUT = 3600
CAPTURE_TIMEOUT = 3600
BENCH_TIMEOUT = 14400
MODES = {"reuse": ["reuse"], "upload": ["upload"], "both": ["upload", "reuse"]}


@dataclass
class LegStatus:
    tag: str
    status: str  # OK, FAIL, NO_HW, NO_SD_DATA, DRY_RUN
    step: str = ""
    detail: str = ""
    result_dirs: list[str] = field(default_factory=list)
    # Every vta.* option the leg ran with: an OK only counts for these.
    options: dict[str, str] = field(default_factory=dict)


def _status_path(settings: Settings, leg: Leg) -> Path:
    return settings.work / "status" / leg.campaign / f"{leg.tag}.json"


def load_status(settings: Settings, leg: Leg) -> LegStatus | None:
    path = _status_path(settings, leg)
    return LegStatus(**json.loads(path.read_text())) if path.exists() else None


def _save(settings: Settings, leg: Leg, st: LegStatus) -> LegStatus:
    path = _status_path(settings, leg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(st), indent=2) + "\n")
    return st


def _is_current_ok(st: LegStatus | None, expected: dict[str, str]) -> bool:
    return st is not None and st.status == "OK" and st.options == expected


def _missing_input(settings: Settings, leg: Leg) -> str | None:
    if leg.hw_dir is not None and not (leg.hw_dir / f"vta_{leg.board}.xsa").exists():
        return "NO_HW"
    # The SD loader reads the model data from the card, so a pair that was
    # never staged cannot run however correct its flags are.
    if leg.loader == "sd" and not (settings.cards / leg.board / leg.sd_dir).is_dir():
        return "NO_SD_DATA"
    return None


def _results_dir(log: Path) -> Path | None:
    """The directory uart_bench reports it wrote ("[bench] results in X")."""
    if not log.exists():
        return None
    found = re.findall(r"^\[bench\] results in (.+)$", log.read_text(), re.M)
    return Path(found[-1]) if found else None


def run_leg(runner: Runner, settings: Settings, leg: Leg, *,
            check=board.check_port) -> LegStatus:
    dry = runner.dry_run
    info: dict = {}

    def done(status: str, step: str = "", detail: str = "",
             dirs: list[str] | None = None) -> LegStatus:
        st = LegStatus(leg.tag, "DRY_RUN" if dry else status, step, detail,
                       dirs or [], info.get("options", {}))
        return st if dry else _save(settings, leg, st)

    def see(step: str) -> str:
        return f"see {runner.log_dir / leg.tag}_{step}.log"

    missing = _missing_input(settings, leg)
    if missing and not dry:
        return done(missing, "inputs", f"hw_dir={leg.hw_dir} cards={settings.cards}")
    if missing:
        print(f"# {leg.tag}: would be skipped as {missing}")

    b = settings.boards[leg.board]
    if not dry:
        try:
            check(settings, leg.board, b.port)
        except BoardError as e:
            return done("FAIL", "port", str(e))

    props = leg_props(settings, leg)
    app = ["--runner", RUNNER, "--data-loader", leg.loader]
    task = lambda name: target(leg.model, leg.config, name)
    leg_dir = settings.work / "legs" / leg.campaign / leg.tag
    input_bin, board_out = leg_dir / "input_nn.bin", leg_dir / "out.bin"

    def bench(runs: int, tag: str, out_dir: Path, *extra: str) -> list[str]:
        return [sys.executable, str(settings.repo / "tools/uart_bench.py"),
                "--port", b.port, "--baud", str(b.baud), "--input", str(input_bin),
                "--runs", str(runs), "--tag", tag, "--out-dir", str(out_dir),
                "--banner-timeout", "300", "--ready-timeout", "1800", "--quiet", *extra]

    if runner.run(mill_cmd(props, task("buildVitisApp"), *app),
                  f"{leg.tag}_build", BUILD_TIMEOUT) != 0:
        return done("FAIL", "build", see("build"))
    try:
        with nullcontext() if dry else jtag_lock(settings):
            rc = runner.run(mill_cmd(props, task("flashBoard"), *app),
                            f"{leg.tag}_flash", FLASH_TIMEOUT)
    except BoardError as e:
        return done("FAIL", "flash", str(e))
    if rc != 0:
        return done("FAIL", "flash", see("flash"))

    # Copies the input out of mill's out/ and reports what the run is made of.
    rc, out = runner.capture(
        mill_cmd(props, "show", task("runInfo"), "--snapshot-dir", str(leg_dir), *app),
        f"{leg.tag}_info", MILL_TIMEOUT)
    if rc != 0:
        return done("FAIL", "info", see("info"))
    info.update(json.loads(out) if out else {})

    # Verification gates measurement: a wrong answer is never timed. An
    # earlier attempt's capture must not pass for this one's, whatever stops
    # uart_bench before it writes.
    if not dry:
        board_out.unlink(missing_ok=True)
    runner.run(bench(1, f"{leg.tag}-check", leg_dir / "check",
                     "--save-output", str(board_out)),
               f"{leg.tag}_capture", CAPTURE_TIMEOUT)
    if not dry and not board_out.exists():
        return done("FAIL", "capture", f"no output captured, {see('capture')}")
    if runner.run(mill_cmd(props, task("checkBoardOutput"), "--output", str(board_out)),
                  f"{leg.tag}_check", MILL_TIMEOUT) != 0:
        return done("FAIL", "check", f"board output differs from fsim, {see('check')}")

    dirs = []
    for mode in MODES[leg.mode]:
        rc = runner.run(bench(leg.n_runs, f"{leg.tag}-{mode}", settings.results,
                              *(["--reuse-input"] if mode == "reuse" else [])),
                        f"{leg.tag}_bench_{mode}", BENCH_TIMEOUT)
        if dry:
            continue
        d = _results_dir(runner.log_dir / f"{leg.tag}_bench_{mode}.log")
        if d is not None:
            write_experiment(d, leg, settings, info, mode, {"bench_rc": rc})
            dirs.append(str(d))
        if rc != 0 or d is None:
            return done("FAIL", f"measure-{mode}", f"uart_bench rc={rc}, "
                        f"{see(f'bench_{mode}')}", dirs)
    return done("OK", dirs=dirs)


def warn_persisted(settings: Settings, base: dict[str, str]) -> None:
    changed = non_default(base, mill_defaults(settings))
    if changed:
        print("WARNING: these options apply to every leg (./mill configure); "
              "legs run and are recorded with them:")
        for k, (v, d) in changed.items():
            print(f"  {k}={v} (default {d or 'empty'})")


def run_campaign(runner: Runner, settings: Settings, legs: Sequence[Leg],
                 **hw) -> list[LegStatus]:
    """Run every leg not already OK with the options it would run with now.
    Each failure is recorded and the campaign continues; rerunning retries
    everything that is not OK."""
    base = {} if runner.dry_run else vta_options(runner)
    warn_persisted(settings, base)
    statuses = []
    for leg in legs:
        prev = None if runner.dry_run else load_status(settings, leg)
        if _is_current_ok(prev, expected_options(base, leg_props(settings, leg))):
            statuses.append(prev)
            continue
        print(f"######## {leg.tag}  {time.strftime('%m-%d %H:%M')}", flush=True)
        try:
            st = run_leg(runner, settings, leg, **hw)
        except Exception as e:  # one broken leg must not end an overnight run
            tb = traceback.format_exception_only(e)[-1].strip()
            st = LegStatus(leg.tag, "FAIL", "internal", tb)
            if not runner.dry_run:
                _save(settings, leg, st)
        print(f"  => {st.status} {st.step} {st.detail}".rstrip(), flush=True)
        statuses.append(st)
    return statuses


def status_table(settings: Settings, legs: Sequence[Leg],
                 base: dict[str, str]) -> str:
    rows = [("tag", "status", "step", "flags", "detail")]
    for leg in legs:
        st = load_status(settings, leg)
        state = "pending" if st is None else st.status
        if st is not None and st.status == "OK" and not _is_current_ok(
                st, expected_options(base, leg_props(settings, leg))):
            state = "stale"  # measured with other options
        rows.append((leg.tag, state, st.step if st else "",
                     " ".join(leg.flags) or "-", st.detail if st else ""))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r[:4], widths)) + "  " + r[4]
                     for r in rows)
