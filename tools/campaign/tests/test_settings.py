import tempfile
import unittest
from pathlib import Path

from vta_campaign.settings import REPO, load_settings


class SettingsTest(unittest.TestCase):
    def test_defaults_and_overrides(self):
        s = load_settings(None, {"vck190": "/dev/ttyUSB0"})
        self.assertEqual(s.repo, REPO)
        self.assertEqual(s.work, REPO / "build/campaign")
        self.assertEqual(s.results, REPO / "results")
        z, v = s.boards["zcu104"], s.boards["vck190"]
        self.assertEqual((z.port, z.baud, z.uart_usb_model, z.jtag_cable),
                         ("/dev/ttyUSB1", 2000000, None, None))
        self.assertEqual((v.port, v.baud, v.uart_usb_model, v.jtag_cable),
                         ("/dev/ttyUSB0", 115200, "VCK190", "VCK190"))

    def test_jtag_lock_is_shared_by_every_checkout(self):
        # Two worktrees have a work dir each, but share one hw_server.
        s = load_settings(None, {})
        self.assertEqual(s.jtag_lock, Path("~/.cache/vta-campaign/jtag.lock").expanduser())
        self.assertFalse(s.jtag_lock.is_relative_to(REPO))

    def test_relative_paths_resolve_under_repo(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml") as f:
            f.write('[paths]\narchive = "synth_archive"\ncards = "~/cards"\n')
            f.flush()
            s = load_settings(Path(f.name), {})
        self.assertEqual(s.archive, REPO / "synth_archive")
        self.assertEqual(s.cards, Path("~/cards").expanduser())

    def test_user_file_adds_a_board(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml") as f:
            f.write('[boards.kv260]\nport = "/dev/ttyUSB9"\nbaud = 115200\n')
            f.flush()
            s = load_settings(Path(f.name), {})
        self.assertEqual(s.boards["kv260"].port, "/dev/ttyUSB9")
        self.assertIn("zcu104", s.boards)

    def test_unknown_board_override_is_rejected(self):
        with self.assertRaises(ValueError):
            load_settings(None, {"kv260": "/dev/ttyUSB0"})
