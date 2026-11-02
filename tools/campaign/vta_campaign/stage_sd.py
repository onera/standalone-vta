"""SD-card content for the legs that use the SD loader.

Staged once per (model, config, flags) and copied to the host card tree of
every board that runs it: the streams depend on the model, the config and the
DDR base, never on the board or the AXI width.
"""
from __future__ import annotations

import shutil
import time
from typing import Sequence

from .mill import DDR_BASE, MILL_TIMEOUT, log_name, mill_cmd, target
from .matrix import Leg
from .runner import Runner
from .settings import Settings



def stage_sd(runner: Runner, settings: Settings,
             legs: Sequence[Leg]) -> list[tuple[str, str]]:
    pairs: dict[tuple, list[str]] = {}
    for leg in legs:
        if leg.loader == "sd":
            boards = pairs.setdefault((leg.model, leg.config, leg.flags), [])
            if leg.board not in boards:
                boards.append(leg.board)

    result = []
    for (model, config, flags), boards in pairs.items():
        sd_dir = f"{model}_{config}"
        rc = runner.run(mill_cmd([f"-Dvta.ddr.base={DDR_BASE}",
                                            f"-Dvta.sd.dir={sd_dir}", *flags],
                                 target(model, config, "sdCard")),
                        log_name("sdcard", model, config, flags), MILL_TIMEOUT)
        if rc != 0:
            result.append((sd_dir, "FAILED"))
            continue
        if runner.dry_run:
            result.append((sd_dir, "OK"))
            continue
        src = (settings.repo / f"out/examples/onnx/{model}/{config}"
               / "sdCard.dest/sd_card" / sd_dir)
        if not src.is_dir():
            result.append((sd_dir, f"NO_OUTPUT at {src}"))
            continue
        for board in boards:
            dest = settings.cards / board / sd_dir
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest.rename(dest.with_name(f".superseded-{sd_dir}-{int(time.time())}"))
            shutil.copytree(src, dest)
        result.append((sd_dir, "OK"))
    return result
