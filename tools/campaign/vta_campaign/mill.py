"""The mill invocations a campaign is made of.

Every step of a leg that mill can do is a mill task; this module only builds
their command lines and the -D properties that describe a leg.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence

from .matrix import Leg
from .runner import Runner
from .settings import Settings

MILL_TIMEOUT = 7200
# DDR base of the SD-loader data: stage-sd stages the cards at it, and the
# streams on a card embed it, so an SD-loader app is built at it too.
DDR_BASE = "0x1000000"


def mill_cmd(flags: Sequence[str], target: str, *args: str) -> list[str]:
    return ["./mill", *flags, target, *args]


def target(model: str, config: str, task: str) -> str:
    return f"examples.onnx[{model},{config}].{task}"


def log_name(step: str, model: str, config: str, flags: Sequence[str]) -> str:
    digest = hashlib.sha1(" ".join(sorted(flags)).encode()).hexdigest()[:8]
    return f"{step}_{model}_{config}_{digest}"


def leg_props(settings: Settings, leg: Leg) -> list[str]:
    """Everything that sets a leg apart, as mill properties, flags last."""
    b = settings.boards[leg.board]
    props = [f"-Dvta.board.name={leg.board}", f"-Dvta.sd.dir={leg.sd_dir}",
             f"-Dvta.app.opt={leg.app_opt}", f"-Dvta.uart.baud={b.baud}"]
    if b.jtag_cable:
        props.append(f"-Dvta.jtag.cable={b.jtag_cable}")
    if leg.hw_dir is not None:
        props.append(f"-Dvta.hw.dir={leg.hw_dir}")
    if leg.loader == "sd":
        props.append(f"-Dvta.ddr.base={DDR_BASE}")
    return props + list(leg.flags)


def expected_options(base: dict[str, str], props: Sequence[str]) -> dict[str, str]:
    """The options mill would report for `props` on top of `base`."""
    return {**base, **dict(p.removeprefix("-D").split("=", 1) for p in props)}


def vta_options(runner: Runner) -> dict[str, str]:
    """The vta.* options in effect with no -D flag: defaults plus whatever
    `./mill configure` persisted."""
    rc, out = runner.capture(mill_cmd([], "show", "vtaOptions"), "vta_options",
                             MILL_TIMEOUT)
    if rc != 0:
        raise RuntimeError(f"./mill show vtaOptions failed (rc={rc})")
    return json.loads(out) if out else {}


def mill_defaults(settings: Settings) -> dict[str, str]:
    """config/mill-defaults.properties, as mill reads it (key=value lines)."""
    out = {}
    for line in (settings.repo / "config/mill-defaults.properties").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def non_default(effective: dict[str, str],
                defaults: dict[str, str]) -> dict[str, tuple[str, str]]:
    """{option: (value, default)} for every option that is not at its default."""
    return {k: (v, defaults.get(k, "")) for k, v in sorted(effective.items())
            if v != defaults.get(k, "")}


def prepare(runner: Runner, legs: Sequence[Leg]) -> list[tuple[str, str]]:
    """Build everything slow up front, as (what, "ok" | "FAILED") rows.

    The hardware platform of every (config, board): synthesis run inside a
    leg's buildVitisApp would hold mill's out/ for hours, and the other
    board's process with it. Then every (model, config, flags)'s compile and
    fsim run (layerDumps), so a compile failure surfaces before board time.
    """
    rows: dict[str, str] = {}
    for leg in legs:
        what = f"hardware {leg.config} {leg.board}"
        if what in rows:
            continue
        cross = f"targets[{leg.config},{leg.board}]"
        cmd = (mill_cmd([], f"{cross}.vitisPlatform") if leg.hw_dir is None else
               mill_cmd([f"-Dvta.hw.dir={leg.hw_dir}"], f"{cross}.prebuiltVitisPlatform"))
        rc = runner.run(cmd, f"hardware_{leg.config}_{leg.board}", MILL_TIMEOUT)
        rows[what] = "ok" if rc == 0 else "FAILED"
    for leg in legs:
        what = f"golden {leg.model} {leg.config} {' '.join(leg.flags) or '-'}"
        if what in rows:
            continue
        rc = runner.run(mill_cmd(leg.flags, target(leg.model, leg.config, "layerDumps")),
                        log_name("golden", leg.model, leg.config, leg.flags), MILL_TIMEOUT)
        rows[what] = "ok" if rc == 0 else "FAILED"
    return list(rows.items())
