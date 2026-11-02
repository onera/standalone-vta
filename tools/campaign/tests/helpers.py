"""Test doubles shared by the test modules."""
from __future__ import annotations

from pathlib import Path

from vta_campaign.runner import Runner


class FakeRunner(Runner):
    """Records commands instead of running them.

    `rcs` maps a log name to the exit code its command returns (default 0);
    `effects` maps a log name to a callable run in place of the command, to
    create the files the real command would have left behind; `outputs` maps
    a log name to the stdout `capture` returns.
    """

    def __init__(self, rcs: dict[str, int] | None = None, effects=None,
                 outputs: dict[str, str] | None = None, log_dir: Path | None = None):
        super().__init__(log_dir or Path("/nonexistent"), dry_run=False)
        self.rcs = rcs or {}
        self.effects = effects or {}
        self.outputs = outputs or {}
        self.logs: list[str] = []

    def run(self, cmd, log, timeout, env=None, cwd=None):
        self.commands.append([str(c) for c in cmd])
        self.logs.append(log)
        if log in self.effects:
            self.effects[log]()
        return self.rcs.get(log, 0)

    def capture(self, cmd, log, timeout):
        return self.run(cmd, log, timeout), self.outputs.get(log, "")
