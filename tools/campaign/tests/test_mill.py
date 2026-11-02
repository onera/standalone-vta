import dataclasses
import json
import unittest
from pathlib import Path

from tests.helpers import FakeRunner
from vta_campaign.matrix import load_campaign
from vta_campaign.mill import (DDR_BASE, expected_options, leg_props, log_name, mill_cmd,
                               mill_defaults, non_default, prepare, vta_options)
from vta_campaign.settings import load_settings

CAMPAIGNS = Path(__file__).resolve().parents[1] / "campaigns"


class MillTest(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(None, {})
        self.legs = {l.tag: l for l in
                     load_campaign(CAMPAIGNS / "config-matrix.toml", self.settings)}

    def test_mill_cmd(self):
        self.assertEqual(mill_cmd(["-Da=1"], "x.compile", "--y"),
                         ["./mill", "-Da=1", "x.compile", "--y"])

    def test_leg_props_synthesized_hardware(self):
        leg = self.legs["C-qyolo-vta_8b_block32-vck190"]
        props = leg_props(self.settings, leg)
        self.assertEqual(props[:5], [
            "-Dvta.board.name=vck190", "-Dvta.sd.dir=qyolo_vta_8b_block32",
            "-Dvta.app.opt=O2", "-Dvta.uart.baud=115200", "-Dvta.jtag.cable=VCK190"])
        self.assertEqual(props[-len(leg.flags):], list(leg.flags))  # flags last
        self.assertFalse(any(p.startswith("-Dvta.hw.dir") for p in props))

    def test_sd_legs_build_at_the_staged_ddr_base(self):
        # The card's streams embed the DDR base stage-sd staged them with, so
        # the app reading them must be built at the same one.
        sd = self.legs["C-qyolo-vta_8b_block32-vck190"]
        self.assertIn(f"-Dvta.ddr.base={DDR_BASE}", leg_props(self.settings, sd))
        elf = dataclasses.replace(sd, loader="elf")
        self.assertFalse(any("vta.ddr.base" in p for p in leg_props(self.settings, elf)))

    def test_leg_props_prebuilt_hardware(self):
        leg = self.legs["C-resnet18-vta_config_a128-zcu104"]
        props = leg_props(self.settings, leg)
        self.assertIn(f"-Dvta.hw.dir={leg.hw_dir}", props)
        self.assertFalse(any(p.startswith("-Dvta.jtag.cable") for p in props))

    def test_expected_options_overlay_leg_props(self):
        leg = self.legs["C-qyolo-vta_8b_block32-vck190"]
        base = {"vta.board.name": "zcu104", "vta.fold.inp.zp": "false",
                "vta.ref.seed": "1234"}
        exp = expected_options(base, leg_props(self.settings, leg))
        self.assertEqual(exp["vta.board.name"], "vck190")
        self.assertEqual(exp["vta.fold.inp.zp"], "true")
        self.assertEqual(exp["vta.ref.seed"], "1234")

    def test_vta_options_reads_mill_show(self):
        r = FakeRunner(outputs={"vta_options": json.dumps({"vta.ref.seed": "1234"})})
        self.assertEqual(vta_options(r), {"vta.ref.seed": "1234"})
        self.assertEqual(r.commands, [["./mill", "show", "vtaOptions"]])

    def test_non_default_lists_persisted_options(self):
        defaults = mill_defaults(self.settings)
        self.assertEqual(defaults["vta.ref.seed"], "1234")
        self.assertEqual(defaults["vta.sd.dir"], "")
        effective = dict(defaults, **{"vta.direct.conv": "true"})
        self.assertEqual(non_default(effective, defaults),
                         {"vta.direct.conv": ("true", "false")})

    def test_prepare_runs_layer_dumps_once_per_pair_and_flags(self):
        legs = list(self.legs.values())
        r = FakeRunner(rcs={log_name("golden", "qyolo", "vta_w8b", ()): 1})
        status = dict(prepare(r, legs))
        goldens = [c for c in r.commands if c[-1].endswith(".layerDumps")]
        self.assertEqual(len(goldens), 16)  # 8 configs x 2 models, boards collapse
        self.assertEqual(status["golden qyolo vta_w8b -"], "FAILED")
        q = next(c for c in goldens if "qyolo,vta_8b_block32" in c[-1])
        self.assertIn("-Dvta.fold.inp.zp=true", q)

    def test_prepare_builds_every_hardware_platform_up_front(self):
        # Synthesis inside a leg's buildVitisApp would hold mill's out/ for
        # hours while the other board's process waits on it.
        r = FakeRunner()
        status = dict(prepare(r, list(self.legs.values())))
        platforms = [c for c in r.commands if "Platform" in c[-1]]
        self.assertEqual(len(platforms), 16)  # 8 configs x 2 boards
        synth = [c for c in platforms if c[-1].endswith(".vitisPlatform")]
        prebuilt = [c for c in platforms if c[-1].endswith(".prebuiltVitisPlatform")]
        self.assertEqual(len(synth), 12)
        self.assertEqual(synth[0], ["./mill", "targets[vta_config,zcu104].vitisPlatform"])
        a128 = self.legs["C-resnet18-vta_config_a128-zcu104"]
        self.assertIn(["./mill", f"-Dvta.hw.dir={a128.hw_dir}",
                       "targets[vta_config_a128,zcu104].prebuiltVitisPlatform"], prebuilt)
        self.assertEqual(status["hardware vta_config zcu104"], "ok")
        # Hardware first: it is the slow part, and the goldens do not need it.
        self.assertTrue(r.commands[0][-1].endswith("Platform"))
