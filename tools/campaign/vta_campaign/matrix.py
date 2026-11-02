"""Campaign files: TOML descriptions of the legs to run, expanded into `Leg`s.

A campaign is one or more `[[group]]`s, each the cartesian product of its
configs, boards, models, app_opts and variants (in that nesting order, so legs
sharing a config and a board run back to back). See tools/campaign/README.md
for the schema.
"""
from __future__ import annotations

import itertools
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .correctness import flags_for
from .settings import Settings


@dataclass(frozen=True)
class Leg:
    campaign: str
    tag: str
    model: str
    config: str
    board: str
    loader: Literal["sd", "elf"]
    app_opt: str
    n_runs: int
    mode: Literal["reuse", "upload", "both"]
    variant: str
    flags: tuple[str, ...]
    # A prebuilt hardware export (-Dvta.hw.dir), or None for mill's synthesis.
    hw_dir: Path | None

    @property
    def sd_dir(self) -> str:
        """SD-card folder of the pair, which the app's NN_SD_DIR points at.

        Always passed as -Dvta.sd.dir: it otherwise defaults to the bare model
        name, and every config of a model would stage into one folder.
        """
        return f"{self.model}_{self.config}"


def _dedup(flags: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(flags))


def load_campaign(path: Path, settings: Settings) -> list[Leg]:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    name = raw["name"]
    variants = {"base": [], **raw.get("variants", {})}
    legs = []
    for group in raw["group"]:
        unknown = set(group.get("variants", ["base"])) - variants.keys()
        if unknown:
            raise ValueError(f"{path}: unknown variants {sorted(unknown)}")
        for config, board, model, opt, variant in itertools.product(
                group["configs"], group["boards"], group["models"],
                group["app_opts"], group.get("variants", ["base"])):
            keys = dict(config=config, board=board, model=model,
                        app_opt=opt, variant=variant,
                        archive=settings.archive)
            template = group.get("hw_dirs", {}).get(config, group.get("hw_dir"))
            correct = (flags_for(model, config)
                       if raw.get("apply_correctness", True) else [])
            legs.append(Leg(
                campaign=name,
                tag=group["tag"].format(**keys),
                model=model, config=config, board=board,
                loader=group["loader"], app_opt=opt,
                n_runs=raw.get("n_runs", 30), mode=raw.get("mode", "reuse"),
                variant=variant,
                flags=_dedup(correct + variants[variant]),
                hw_dir=(None if template is None
                        else settings.repo / template.format(**keys)),
            ))
    tags = [l.tag for l in legs]
    dupes = {t for t in tags if tags.count(t) > 1}
    if dupes:
        raise ValueError(f"{path}: duplicate tags {sorted(dupes)}")
    return legs
