import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vta_campaign.settings import REPO

sys.path.insert(0, str(REPO / "tools"))
import uart_bench  # noqa: E402

INPUT = b"\x10\x20\x30\x40"
TABLE = (b"[time] 0 conv1                         5 us  vta 50 cyc (40 compute)\r\n"
         b"[time] TOTAL 5 us = VTA 5 us + CPU 0 us (CPU 0%)\r\n")


class FakeSerial:
    """run_nn_uart as seen from the host: banner and READY on a trigger, then
    the [time] table, OUTPUT and a payload that differs on every run."""

    def __init__(self, port, baud, timeout):
        self.rx = b""
        self.pending = b""
        self.run = 0

    @property
    def in_waiting(self):
        return len(self.rx)

    def write(self, data):
        self.pending += data
        if self.pending in (b"\x01", b"\x02"):
            self.rx += b"input=4 out=3\r\nREADY\r\n"
            if self.pending == b"\x02":
                self._respond()
        elif self.pending == b"\x01" + INPUT:
            self._respond()
        return len(data)

    def _respond(self):
        self.run += 1
        self.rx += TABLE + b"OUTPUT\r\n" + bytes([self.run] * 3)
        self.pending = b""

    def read(self, n):
        out, self.rx = self.rx[:n], self.rx[n:]
        return out

    def reset_input_buffer(self):
        self.rx = b""

    def close(self):
        pass


class FailingSerial(FakeSerial):
    """A board whose every inference fails."""

    def _respond(self):
        self.rx += b"inference failed, skipping output\r\n"
        self.pending = b""


class UartBenchTest(unittest.TestCase):
    def test_exits_nonzero_when_no_run_succeeded(self):
        with self.assertRaises(SystemExit) as e:
            self.run_bench("--runs", "2", serial_cls=FailingSerial)
        self.assertEqual(e.exception.code, 1)

    def test_exits_zero_when_runs_succeeded(self):
        self.run_bench("--runs", "2")  # no SystemExit

    def run_bench(self, *extra, leftover=None, serial_cls=FakeSerial):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "in.bin").write_bytes(INPUT)
            if leftover is not None:
                (d / "out.bin").write_bytes(leftover)
            argv = ["uart_bench.py", "--port", "/dev/null", "--input", str(d / "in.bin"),
                    "--tag", "t", "--out-dir", str(d / "results"), "--quiet",
                    *(a.format(d=d) for a in extra)]
            with mock.patch.object(uart_bench.serial, "Serial", serial_cls), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                uart_bench.main()
            saved = d / "out.bin"
            return saved.read_bytes() if saved.exists() else None

    def test_save_output_keeps_the_first_run(self):
        out = self.run_bench("--runs", "3", "--reuse-input",
                             "--save-output", "{d}/out.bin")
        self.assertEqual(out, b"\x01\x01\x01")

    def test_save_output_replaces_a_leftover(self):
        out = self.run_bench("--runs", "1", "--save-output", "{d}/out.bin",
                             leftover=b"stale")
        self.assertEqual(out, b"\x01\x01\x01")

    def test_no_save_output_by_default(self):
        self.assertIsNone(self.run_bench("--runs", "1"))
