import dataclasses
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FakeRunner
from vta_campaign.mill import log_name
from vta_campaign.matrix import load_campaign
from vta_campaign.settings import load_settings
from vta_campaign.stage_sd import stage_sd

CAMPAIGNS = Path(__file__).resolve().parents[1] / "campaigns"


class StageSdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        base = load_settings(None, {})
        self.legs = load_campaign(CAMPAIGNS / "o2-matrix.toml", base)
        self.settings = dataclasses.replace(base, repo=root, work=root / "work",
                                            cards=root / "cards")

    def tearDown(self):
        self.tmp.cleanup()

    def sdcard_writes(self, model, config, content):
        def effect():
            d = (self.settings.repo / f"out/examples/onnx/{model}/{config}"
                 / f"sdCard.dest/sd_card/{model}_{config}")
            d.mkdir(parents=True, exist_ok=True)
            (d / "data.bin").write_text(content)
        return effect

    def test_stage_sd_skips_elf_legs(self):
        r = FakeRunner()
        stage_sd(r, self.settings, self.legs)
        targets = [c[-1] for c in r.commands]
        self.assertEqual(targets, ["examples.onnx[qyolo,vta_w8b].sdCard",
                                   "examples.onnx[qyolo,vta_config_a128].sdCard"])
        cmd = r.commands[0]
        self.assertIn("-Dvta.ddr.base=0x1000000", cmd)
        self.assertIn("-Dvta.sd.dir=qyolo_vta_w8b", cmd)

    def test_stage_sd_copies_to_each_board_and_parks_previous_copy(self):
        old = self.settings.cards / "zcu104/qyolo_vta_w8b"
        old.mkdir(parents=True)
        (old / "data.bin").write_text("old")
        name = log_name("sdcard", "qyolo", "vta_w8b", ())
        r = FakeRunner(effects={name: self.sdcard_writes("qyolo", "vta_w8b", "new")},
                       rcs={log_name("sdcard", "qyolo", "vta_config_a128", ()): 1})
        result = stage_sd(r, self.settings, self.legs)
        self.assertEqual(result, [("qyolo_vta_w8b", "OK"),
                                  ("qyolo_vta_config_a128", "FAILED")])
        for b in ("zcu104", "vck190"):
            self.assertEqual((self.settings.cards / b / "qyolo_vta_w8b/data.bin")
                             .read_text(), "new")
        parked = list((self.settings.cards / "zcu104")
                      .glob(".superseded-qyolo_vta_w8b-*"))
        self.assertEqual(len(parked), 1)
        self.assertEqual((parked[0] / "data.bin").read_text(), "old")
