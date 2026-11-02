"""Machine settings: where things go and how each board is reached."""
from __future__ import annotations

import dataclasses
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_SETTINGS = Path(__file__).resolve().parents[1] / "settings.toml"


@dataclass(frozen=True)
class BoardSettings:
    port: str
    baud: int
    uart_usb_model: str | None = None
    jtag_cable: str | None = None


@dataclass(frozen=True)
class Settings:
    repo: Path
    work: Path
    results: Path
    archive: Path
    cards: Path
    jtag_lock: Path
    boards: dict[str, BoardSettings]


def _path(raw: str) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else REPO / p


def load_settings(path: Path | None, port_overrides: dict[str, str]) -> Settings:
    """Read `path` (default tools/campaign/settings.toml) over the defaults
    file, so a user file only has to name what it changes."""
    with open(DEFAULT_SETTINGS, "rb") as f:
        raw = tomllib.load(f)
    if path is not None:
        with open(path, "rb") as f:
            user = tomllib.load(f)
        for key, value in user.items():
            if isinstance(value, dict):
                raw.setdefault(key, {}).update(value)
            else:
                raw[key] = value

    boards = {name: BoardSettings(**b) for name, b in raw["boards"].items()}
    for name, port in port_overrides.items():
        if name not in boards:
            raise ValueError(f"--port {name}=...: unknown board, "
                             f"expected one of {sorted(boards)}")
        boards[name] = dataclasses.replace(boards[name], port=port)

    paths = raw["paths"]
    return Settings(
        repo=REPO,
        work=_path(paths["work"]),
        results=_path(paths["results"]),
        archive=_path(paths["archive"]),
        cards=_path(paths["cards"]),
        jtag_lock=_path(paths["jtag_lock"]),
        boards=boards,
    )
