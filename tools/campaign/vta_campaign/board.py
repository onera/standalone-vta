"""Board access: which UART is which board, and the shared JTAG lock."""
from __future__ import annotations

import fcntl
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from .settings import Settings


class BoardError(RuntimeError):
    pass


def read_udev_model(port: str) -> str | None:
    """The ID_MODEL udev reports for a serial device, or None."""
    out = subprocess.run(["udevadm", "info", "-q", "property", "-n", port],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("ID_MODEL="):
            return line.removeprefix("ID_MODEL=")
    return None


def check_port(settings: Settings, board: str, port: str,
               udev_model: Callable[[str], str | None] = read_udev_model,
               exists: Callable[[str], bool] = os.path.exists) -> None:
    """Refuse a port that is missing or belongs to another board.

    A board with a `uart_usb_model` must report it as the port's ID_MODEL,
    and no board may use a port reporting another board's. ttyUSB numbering
    shifts when a board is unplugged, so a stale default would otherwise
    drive the wrong board.
    """
    if not exists(port):
        raise BoardError(f"no such port {port} (is {board} connected?)")
    model = udev_model(port)
    own = settings.boards[board].uart_usb_model
    if own is not None:
        if model != own:
            raise BoardError(f"WRONG BOARD: {port} reports ID_MODEL={model!r}, "
                             f"expected {own!r}")
        return
    others = {b.uart_usb_model for b in settings.boards.values()} - {None}
    if model in others:
        raise BoardError(f"WRONG BOARD: {port} is the {model}, not the {board}")


@contextmanager
def jtag_lock(settings: Settings, timeout: float = 5400) -> Iterator[None]:
    """Serialise flashing across processes.

    Both boards can be swept at once, as two processes, but programming goes
    through one shared hw_server. mill already runs one command at a time per
    `out/`, but two checkouts or worktrees have one `out/` each.
    """
    path: Path = settings.jtag_lock
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with open(path, "w") as f:
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise BoardError(f"could not take the lock {path} "
                                     f"within {timeout}s")
                time.sleep(min(2.0, timeout / 10))
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
