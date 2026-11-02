"""Simulator-only timing: everything is built first, untimed, then only the
simulator binary is timed, so Verilator, JVM and mill time are excluded."""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Sequence

from .mill import MILL_TIMEOUT, mill_cmd, target
from .runner import Runner
from .settings import Settings


def sim_timing(runner: Runner, settings: Settings, models: Sequence[str],
               config: str = "vta_config",
               backends: Sequence[str] = ("fsim", "vsim"),
               runs: int = 3) -> Path:
    for model in models:
        for task in ("compile", "reference"):
            runner.run(mill_cmd([], target(model, config, task)),
                       f"timing_build_{model}_{task}", MILL_TIMEOUT)
    for be in backends:
        runner.run(mill_cmd([], f"modules.simulator[{config}].{be}Binary"),
                   f"timing_build_{be}", MILL_TIMEOUT)

    rows = []
    for model in models:
        comp = settings.repo / f"out/examples/onnx/{model}/{config}/compile.dest"
        ref = settings.repo / f"out/examples/onnx/{model}/{config}/reference.dest"
        for be in backends:
            binary = settings.repo / f"out/modules/simulator/{config}/{be}Binary.dest/{be}"
            for i in range(1, runs + 1):
                out = settings.work / "simtiming" / f"{be}_{model}_{i}"
                if not runner.dry_run:
                    out.mkdir(parents=True, exist_ok=True)
                cmd = [str(binary), "--comp-dir", str(comp), "--ref-dir", str(ref),
                       "--output", str(out)]
                if be == "vsim":
                    cmd.append("--no-timeout")
                t0 = time.monotonic()
                rc = runner.run(cmd, f"timing_{be}_{model}_{i}", MILL_TIMEOUT)
                rows.append({"backend": be, "model": model, "run": i,
                             "seconds": f"{time.monotonic() - t0:.2f}", "rc": rc})

    csv_path = settings.work / "sim-timing.csv"
    if runner.dry_run:
        return csv_path
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["backend", "model", "run", "seconds", "rc"])
        w.writeheader()
        w.writerows(rows)
    return csv_path
