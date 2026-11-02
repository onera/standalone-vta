"""experiment.json: what a measurement directory was produced from.

`run` is mill's runInfo, as reported (inputs, ELF and hardware hashes, every
vta.* option in effect); `campaign` says which leg it was and from which
commit.
"""
from __future__ import annotations

import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .matrix import Leg
from .settings import Settings


def _git(settings: Settings, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=settings.repo, capture_output=True,
                          text=True).stdout.strip()


def write_experiment(result_dir: Path, leg: Leg, settings: Settings, run_info: dict,
                     mode: str, extra: dict) -> Path:
    rec = {
        "run": run_info,
        "campaign": {
            "campaign": leg.campaign, "tag": leg.tag, "variant": leg.variant,
            "flags": list(leg.flags), "loader": leg.loader, "mode": mode,
            "n_runs": leg.n_runs,
            "git": {
                "commit": _git(settings, "rev-parse", "HEAD"),
                "dirty_tracked_files": [
                    l for l in _git(settings, "status", "--porcelain").splitlines()
                    if l and not l.startswith("??")],
            },
            "hostname": socket.gethostname(),
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **extra,
        },
    }
    path = result_dir / "experiment.json"
    path.write_text(json.dumps(rec, indent=2) + "\n")
    return path
