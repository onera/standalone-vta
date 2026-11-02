import unittest
from pathlib import Path

from vta_campaign.correctness import flags_for
from vta_campaign.matrix import load_campaign
from vta_campaign.settings import load_settings

CAMPAIGNS = Path(__file__).resolve().parents[1] / "campaigns"
FOLD = "-Dvta.fold.inp.zp=true"
CLASSIC = ["-Dvta.direct.conv=true", "-Dvta.alias.inp=true",
           "-Dvta.alias.cpu.out=true"]


class CorrectnessTest(unittest.TestCase):
    def test_flags_for(self):
        for cfg in ("vta_config", "vta_config_a128", "vta_w8b", "vta_w8b_a128"):
            self.assertEqual(flags_for("qyolo", cfg), [])
            self.assertEqual(flags_for("resnet18", cfg), [])
        for cfg in ("vta_config_8b", "vta_config_8b_a128"):
            self.assertEqual(flags_for("qyolo", cfg), [FOLD])
            self.assertEqual(flags_for("resnet18", cfg), [FOLD])
        for cfg in ("vta_8b_block32", "vta_8b_block32_a128"):
            self.assertEqual(flags_for("qyolo", cfg), [FOLD, *CLASSIC])
            self.assertEqual(flags_for("resnet18", cfg), [FOLD])
            self.assertEqual(flags_for("lenet5", cfg), [FOLD])


class MatrixTest(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(None, {})

    def load(self, name):
        return load_campaign(CAMPAIGNS / f"{name}.toml", self.settings)

    def test_config_matrix_expands(self):
        legs = self.load("config-matrix")
        self.assertEqual(len(legs), 32)
        self.assertEqual(len({l.tag for l in legs}), 32)
        by_tag = {l.tag: l for l in legs}
        q = by_tag["C-qyolo-vta_8b_block32-vck190"]
        self.assertEqual(list(q.flags), [FOLD, *CLASSIC])
        self.assertEqual((q.loader, q.app_opt, q.n_runs, q.mode),
                         ("sd", "O2", 30, "reuse"))
        self.assertEqual(q.sd_dir, "qyolo_vta_8b_block32")
        self.assertIsNone(q.hw_dir)  # mill's own synthesis
        a = by_tag["C-resnet18-vta_config_a128-zcu104"]
        self.assertEqual(a.hw_dir, self.settings.archive / "vta_config__zcu104__axi128")

    def test_opt_sweep_expands(self):
        legs = self.load("opt-sweep")
        self.assertEqual(len(legs), 7)
        by_variant = {l.variant: l for l in legs}
        self.assertEqual(by_variant["base"].flags, ())
        self.assertEqual(len(set(by_variant["all"].flags)), 4)
        self.assertEqual(by_variant["base"].tag,
                         "OPT-base-resnet18-vta_config-vck190")
        self.assertTrue(all(l.loader == "elf" for l in legs))

    def test_full_and_o2_matrix_expand(self):
        self.assertEqual(len(self.load("full-matrix")), 46)
        self.assertEqual(len(self.load("o2-matrix")), 6)

    def test_correctness_flags_come_first_without_duplicates(self):
        legs = self.load("full-matrix")
        q = next(l for l in legs if l.model == "qyolo"
                 and l.config == "vta_8b_block32_a128")
        self.assertEqual(list(q.flags), [FOLD, *CLASSIC])

    def test_no_axi_bits_flag_anywhere(self):
        for f in CAMPAIGNS.glob("*.toml"):
            for leg in load_campaign(f, self.settings):
                self.assertFalse(any("vta.axi.bits" in x for x in leg.flags),
                                 leg.tag)

    def test_unknown_variant_is_rejected(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".toml") as f:
            f.write('name = "x"\n[[group]]\nmodels = ["lenet5"]\n'
                    'configs = ["vta_config"]\nboards = ["zcu104"]\n'
                    'app_opts = ["O0"]\nloader = "elf"\ntag = "{model}"\n'
                    'variants = ["nope"]\n')
            f.flush()
            with self.assertRaises(ValueError):
                load_campaign(Path(f.name), self.settings)
