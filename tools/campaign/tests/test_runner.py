import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from vta_campaign.runner import Runner


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_records_and_skips(self):
        marker = self.logs / "marker"
        r = Runner(self.logs, dry_run=True)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = r.run(["touch", str(marker)], "touch", timeout=10)
        self.assertEqual(rc, 0)
        self.assertFalse(marker.exists())
        self.assertEqual(r.commands, [["touch", str(marker)]])
        self.assertIn(f"$ touch {marker}", out.getvalue())

    def test_run_logs_output_and_rc(self):
        r = Runner(self.logs, dry_run=False)
        rc = r.run(["sh", "-c", "echo hi; exit 3"], "hi", timeout=10)
        self.assertEqual(rc, 3)
        self.assertIn("hi", (self.logs / "hi.log").read_text())

    def test_capture_returns_stdout_and_logs_stderr(self):
        r = Runner(self.logs, dry_run=False)
        rc, out = r.capture(["sh", "-c", "echo '{\"a\": 1}'; echo noise >&2"], "show",
                            timeout=10)
        self.assertEqual((rc, out), (0, '{"a": 1}\n'))
        self.assertIn("noise", (self.logs / "show.log").read_text())

    def test_capture_dry_run(self):
        r = Runner(self.logs, dry_run=True)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(r.capture(["echo", "x"], "x", timeout=10), (0, ""))

    def test_timeout_returns_124(self):
        r = Runner(self.logs, dry_run=False)
        self.assertEqual(r.run(["sleep", "5"], "slow", timeout=0.2), 124)
