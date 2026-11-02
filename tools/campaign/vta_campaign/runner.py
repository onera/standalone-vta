"""The one place external commands are run: logged, time-limited, and
skippable with --dry-run."""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .settings import REPO


class Runner:
    def __init__(self, log_dir: Path, dry_run: bool):
        self.log_dir = log_dir
        self.dry_run = dry_run
        self.commands: list[list[str]] = []

    def run(self, cmd: list[str], log: str, timeout: float,
            env: dict[str, str] | None = None, cwd: Path | None = None) -> int:
        """Run `cmd` with stdout and stderr in <log_dir>/<log>.log.

        Returns the exit code, 124 on timeout like coreutils `timeout`. A dry
        run prints the command and returns 0.
        """
        cmd = [str(c) for c in cmd]
        self.commands.append(cmd)
        if self.dry_run:
            print(f"$ {shlex.join(cmd)}")
            return 0
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / f"{log}.log", "w") as out:
            try:
                return subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT,
                                      cwd=cwd or REPO, env=env,
                                      timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                out.write(f"\n[campaign] timed out after {timeout}s\n")
                return 124

    def capture(self, cmd: list[str], log: str, timeout: float) -> tuple[int, str]:
        """Like `run`, but return stdout (e.g. a `./mill show` value) and log
        only stderr. A dry run prints the command and returns (0, "")."""
        cmd = [str(c) for c in cmd]
        self.commands.append(cmd)
        if self.dry_run:
            print(f"$ {shlex.join(cmd)}")
            return 0, ""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / f"{log}.log", "w") as err:
            try:
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=err, text=True,
                                   cwd=REPO, timeout=timeout)
                return p.returncode, p.stdout
            except subprocess.TimeoutExpired:
                err.write(f"\n[campaign] timed out after {timeout}s\n")
                return 124, ""
