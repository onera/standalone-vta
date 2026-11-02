import dataclasses
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from vta_campaign.board import BoardError, check_port, jtag_lock
from vta_campaign.settings import load_settings


def _try_lock(settings, q):
    try:
        with jtag_lock(settings, timeout=0.3):
            q.put("took")
    except BoardError:
        q.put("blocked")


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = dataclasses.replace(load_settings(None, {}),
                                            work=Path(self.tmp.name),
                                            jtag_lock=Path(self.tmp.name) / "jtag.lock")

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_port_rejects_wrong_board(self):
        s = self.settings
        vck = lambda port: "VCK190"
        other = lambda port: "Quad_RS232-HS"
        exists = lambda port: True
        check_port(s, "vck190", "/dev/ttyUSB5", vck, exists)
        check_port(s, "zcu104", "/dev/ttyUSB1", other, exists)
        check_port(s, "zcu104", "/dev/ttyUSB1", lambda p: None, exists)
        with self.assertRaisesRegex(BoardError, "WRONG BOARD"):
            check_port(s, "zcu104", "/dev/ttyUSB1", vck, exists)
        with self.assertRaisesRegex(BoardError, "WRONG BOARD"):
            check_port(s, "vck190", "/dev/ttyUSB5", other, exists)
        with self.assertRaisesRegex(BoardError, "no such port"):
            check_port(s, "vck190", "/dev/ttyUSB5", vck, lambda p: False)

    def test_jtag_lock_is_exclusive(self):
        ctx = multiprocessing.get_context("fork")
        q = ctx.Queue()
        with jtag_lock(self.settings):
            p = ctx.Process(target=_try_lock, args=(self.settings, q))
            p.start()
            p.join()
            self.assertEqual(q.get(), "blocked")
        p = ctx.Process(target=_try_lock, args=(self.settings, q))
        p.start()
        p.join()
        self.assertEqual(q.get(), "took")
