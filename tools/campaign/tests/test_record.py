import dataclasses
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from vta_campaign.matrix import load_campaign
from vta_campaign.record import write_experiment
from vta_campaign.settings import load_settings

CAMPAIGNS = Path(__file__).resolve().parents[1] / "campaigns"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=repo, check=True, capture_output=True)


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "a.txt").write_text("a")
        git(self.repo, "init", "-q")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        real = load_settings(None, {})
        self.settings = dataclasses.replace(real, repo=self.repo)
        self.leg = next(l for l in load_campaign(CAMPAIGNS / "config-matrix.toml", real)
                        if l.tag == "C-qyolo-vta_8b_block32-vck190")

    def tearDown(self):
        self.tmp.cleanup()

    def record(self) -> dict:
        out = Path(self.tmp.name) / "results/C-x-reuse-1"
        out.mkdir(parents=True)
        info = {"model": "qyolo", "elf_sha256": "ab", "options": {"vta.ref.seed": "1234"}}
        path = write_experiment(out, self.leg, self.settings, info, "reuse",
                                {"bench_rc": 0})
        self.assertEqual(path, out / "experiment.json")
        return json.loads(path.read_text())

    def test_run_info_is_kept_as_mill_reported_it(self):
        exp = self.record()
        self.assertEqual(set(exp), {"run", "campaign"})
        self.assertEqual(exp["run"]["options"], {"vta.ref.seed": "1234"})

    def test_campaign_block(self):
        c = self.record()["campaign"]
        self.assertEqual((c["campaign"], c["tag"], c["variant"], c["mode"], c["n_runs"]),
                         ("config-matrix", "C-qyolo-vta_8b_block32-vck190", "base",
                          "reuse", 30))
        self.assertEqual(c["flags"], list(self.leg.flags))
        self.assertEqual(c["bench_rc"], 0)
        self.assertEqual(len(c["git"]["commit"]), 40)
        for k in ("hostname", "recorded_at"):
            self.assertIn(k, c)

    def test_dirty_lists_tracked_files_only(self):
        (self.repo / "a.txt").write_text("b")
        (self.repo / "untracked.txt").write_text("x")
        self.assertEqual(self.record()["campaign"]["git"]["dirty_tracked_files"],
                         ["M a.txt"])
