"""The compiler flags a (model, config) pair needs to be correct, from
tools/campaign/correctness.toml."""
from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path

CORRECTNESS = Path(__file__).resolve().parents[1] / "correctness.toml"


@cache
def _rules(path: Path) -> tuple[dict[str, list[str]], list[dict]]:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return raw["flag_sets"], raw.get("rule", [])


def flags_for(model: str, config: str, path: Path = CORRECTNESS) -> list[str]:
    sets, rules = _rules(path)
    for rule in rules:
        if config in rule["configs"] and model in rule.get("models", [model]):
            return [flag for name in rule["flags"] for flag in sets[name]]
    return []
