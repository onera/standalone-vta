#!/usr/bin/env python3
"""
board_discovery.py - list the models, configs and boards this repo defines.

Reads source trees only; build outputs are located by the Mill tasks.
Stdlib only.

Layout read:
    examples/onnx/<model>.onnx
    config/<config>.json
    modules/fpga/boards/<board>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Fallback when a board JSON does not name one.
DEFAULT_PORT = "/dev/ttyUSB0"

# Fallback when a board JSON lists no uart_baud_choices: the BSP boot rate.
DEFAULT_BAUD_CHOICES = (115200,)


def list_models(repo_root: Path) -> list[str]:
    return sorted(p.name for p in (repo_root / "examples/onnx").glob("*.onnx"))


def list_configs(repo_root: Path) -> list[str]:
    return sorted(p.stem for p in (repo_root / "config").glob("*.json"))


def list_loaders() -> list[str]:
    return ["tcl", "elf", "sd"]


def list_boards(repo_root: Path) -> list[str]:
    return sorted(p.stem for p in (repo_root / "modules/fpga/boards").glob("*.json"))


def _board_field(repo_root: Path, board_key: str, field: str):
    """One field of a board JSON, or None if the board/field is missing."""
    try:
        with open(repo_root / "modules/fpga/boards" / f"{board_key}.json",
                  encoding="utf-8") as f:
            return json.load(f).get(field)
    except (OSError, ValueError):
        return None


def default_port(repo_root: Path, board_key: str) -> str:
    """The board's USB-serial device, from its ``uart_port`` field."""
    return _board_field(repo_root, board_key, "uart_port") or DEFAULT_PORT


def baud_choices(repo_root: Path, board_key: str) -> list[int]:
    """The board's UART baud rates, from its ``uart_baud_choices``."""
    raw = _board_field(repo_root, board_key, "uart_baud_choices")
    if not isinstance(raw, list) or not raw:
        return list(DEFAULT_BAUD_CHOICES)
    return [int(b) for b in raw]


def default_baud(repo_root: Path, board_key: str) -> int:
    """First entry of the board's ``uart_baud_choices``."""
    return baud_choices(repo_root, board_key)[0]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--board",
                   help="also print this board's default serial port and baud choices")
    args = p.parse_args(argv)

    root = Path(args.repo_root)
    out: dict[str, object] = {
        "models": list_models(root),
        "configs": list_configs(root),
        "boards": list_boards(root),
    }
    if args.board:
        out["port"] = default_port(root, args.board)
        out["baud_choices"] = baud_choices(root, args.board)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
