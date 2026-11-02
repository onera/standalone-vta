import csv
import dataclasses
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FakeRunner
from vta_campaign.settings import load_settings
from vta_campaign.sim_timing import sim_timing


class SimTimingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = dataclasses.replace(load_settings(None, {}),
                                            work=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sim_timing_excludes_build(self):
        r = FakeRunner()
        out = sim_timing(r, self.settings, ["lenet5", "qyolo"], runs=3)
        cmds = r.commands
        builds = [c for c in cmds if c[0] == "./mill"]
        timed = [c for c in cmds if c[0] != "./mill"]
        self.assertEqual(cmds[:len(builds)], builds)  # every build first
        self.assertEqual({c[-1] for c in builds}, {
            "examples.onnx[lenet5,vta_config].compile",
            "examples.onnx[lenet5,vta_config].reference",
            "examples.onnx[qyolo,vta_config].compile",
            "examples.onnx[qyolo,vta_config].reference",
            "modules.simulator[vta_config].fsimBinary",
            "modules.simulator[vta_config].vsimBinary"})
        self.assertEqual(len(timed), 2 * 2 * 3)
        fsim = self.settings.repo / "out/modules/simulator/vta_config/fsimBinary.dest/fsim"
        self.assertEqual(timed[0][0], str(fsim))
        self.assertIn("--no-timeout", [c for c in timed if c[0].endswith("vsim")][0])
        self.assertNotIn("--no-timeout", timed[0])
        with open(out) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 12)
        self.assertEqual(set(rows[0]), {"backend", "model", "run", "seconds", "rc"})
