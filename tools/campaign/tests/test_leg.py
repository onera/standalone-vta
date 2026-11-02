import contextlib
import dataclasses
import io
import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FakeRunner
from vta_campaign.board import BoardError, jtag_lock
from vta_campaign.leg import run_campaign, run_leg, status_table
from vta_campaign.matrix import load_campaign
from vta_campaign.mill import leg_props, mill_defaults
from vta_campaign.settings import load_settings

CAMPAIGNS = Path(__file__).resolve().parents[1] / "campaigns"


def _try_jtag(settings, q):
    try:
        with jtag_lock(settings, timeout=0.3):
            q.put("took")
    except BoardError:
        q.put("blocked")


def probe_jtag(settings) -> str:
    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    p = ctx.Process(target=_try_jtag, args=(settings, q))
    p.start()
    p.join()
    return q.get()


class LegTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        real = load_settings(None, {})
        self.settings = dataclasses.replace(real, work=root / "work",
                                            results=root / "results",
                                            cards=root / "cards",
                                            jtag_lock=root / "jtag.lock")
        base = load_campaign(CAMPAIGNS / "opt-sweep.toml", real)[0]
        self.leg = dataclasses.replace(base, model="lenet5", tag="T-lenet5", mode="both")
        self.defaults = mill_defaults(self.settings)
        self.checked = []
        self.leg_dir = self.settings.work / "legs/opt-sweep/T-lenet5"

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, settings, board, port):
        self.checked.append((board, port))

    def options(self, leg):
        return {**self.defaults,
                **dict(p.removeprefix("-D").split("=", 1)
                       for p in leg_props(self.settings, leg))}

    def bench_writes(self, tag, mode):
        def effect():
            d = self.settings.results / f"{tag}-{mode}-20261022-120000"
            d.mkdir(parents=True)
            log = self.settings.work / "logs" / f"{tag}_bench_{mode}.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(f"[bench] results in {d}\n")
        return effect

    def capture_writes(self, leg):
        def effect():
            d = self.settings.work / "legs" / leg.campaign / leg.tag
            d.mkdir(parents=True, exist_ok=True)
            (d / "out.bin").write_bytes(b"\0" * 256)
        return effect

    def runner(self, leg, effects=None, base=None, **rcs):
        e = {f"{leg.tag}_bench_{m}": self.bench_writes(leg.tag, m)
             for m in ("upload", "reuse")}
        e[f"{leg.tag}_capture"] = self.capture_writes(leg)
        e.update(effects or {})
        info = {"model": leg.model, "elf_sha256": "ab", "options": self.options(leg)}
        return FakeRunner(rcs=rcs, effects=e, log_dir=self.settings.work / "logs",
                          outputs={f"{leg.tag}_info": json.dumps(info),
                                   "vta_options": json.dumps(base or self.defaults)})

    def run_leg(self, leg, runner):
        return run_leg(runner, self.settings, leg, check=self.check)

    def test_leg_runs_the_mill_tasks_around_two_uart_sessions(self):
        r = self.runner(self.leg)
        st = self.run_leg(self.leg, r)
        self.assertEqual(st.status, "OK", st.detail)
        self.assertEqual(r.logs, ["T-lenet5_build", "T-lenet5_flash", "T-lenet5_info",
                                  "T-lenet5_capture", "T-lenet5_check",
                                  "T-lenet5_bench_upload", "T-lenet5_bench_reuse"])
        self.assertEqual(self.checked, [("vck190", "/dev/ttyUSB5")])
        build, flash, info, capture, check, upload, reuse = r.commands
        target = "examples.onnx[lenet5,vta_config]"
        app = ["--runner", "run_nn_uart", "--data-loader", "elf"]
        self.assertEqual(build[-5:], [f"{target}.buildVitisApp", *app])
        self.assertEqual(flash[-5:], [f"{target}.flashBoard", *app])
        self.assertEqual(info[-8:], ["show", f"{target}.runInfo",
                                     "--snapshot-dir", str(self.leg_dir), *app])
        self.assertEqual(check[-3:], [f"{target}.checkBoardOutput", "--output",
                                      str(self.leg_dir / "out.bin")])
        for cmd in (build, flash, info, check):
            self.assertEqual(cmd[0], "./mill")
            self.assertIn("-Dvta.board.name=vck190", cmd)
            self.assertIn("-Dvta.app.opt=O0", cmd)
        for cmd in (capture, upload, reuse):
            self.assertTrue(cmd[1].endswith("tools/uart_bench.py"))
            self.assertEqual(cmd[cmd.index("--input") + 1],
                             str(self.leg_dir / "input_nn.bin"))
        self.assertEqual(capture[capture.index("--runs") + 1], "1")
        self.assertEqual(capture[capture.index("--save-output") + 1],
                         str(self.leg_dir / "out.bin"))
        self.assertNotIn("--reuse-input", upload)
        self.assertIn("--reuse-input", reuse)
        self.assertEqual(reuse[reuse.index("--tag") + 1], "T-lenet5-reuse")
        self.assertEqual(len(st.result_dirs), 2)
        for d in st.result_dirs:
            exp = json.loads((Path(d) / "experiment.json").read_text())
            self.assertEqual(exp["run"]["elf_sha256"], "ab")
        saved = json.loads((self.settings.work / "status/opt-sweep/T-lenet5.json")
                           .read_text())
        self.assertEqual(saved["status"], "OK")
        self.assertEqual(saved["options"], self.options(self.leg))

    def test_failed_step_stops_the_leg(self):
        for step, logs in (("build", 1), ("flash", 2), ("info", 3), ("check", 5)):
            r = self.runner(self.leg, **{f"T-lenet5_{step}": 1})
            st = self.run_leg(self.leg, r)
            self.assertEqual((st.status, st.step), ("FAIL", step))
            self.assertEqual(len(r.logs), logs, step)

    def test_no_captured_output_blocks_measurement(self):
        r = self.runner(self.leg, effects={"T-lenet5_capture": lambda: None})
        st = self.run_leg(self.leg, r)
        self.assertEqual((st.status, st.step), ("FAIL", "capture"))
        self.assertFalse(any("bench" in l for l in r.logs))

    def test_leftover_capture_never_passes_for_this_one(self):
        self.leg_dir.mkdir(parents=True)
        (self.leg_dir / "out.bin").write_bytes(b"from an earlier attempt")
        r = self.runner(self.leg, effects={"T-lenet5_capture": lambda: None}, **{
            "T-lenet5_capture": 1})
        st = self.run_leg(self.leg, r)
        self.assertEqual((st.status, st.step), ("FAIL", "capture"))
        self.assertNotIn("T-lenet5_check", r.logs)

    def test_wrong_port_fails_before_any_command(self):
        def check(settings, board, port):
            raise BoardError("WRONG BOARD")
        r = self.runner(self.leg)
        st = run_leg(r, self.settings, self.leg, check=check)
        self.assertEqual((st.status, st.step), ("FAIL", "port"))
        self.assertEqual(r.commands, [])

    def test_missing_inputs_skip_the_leg(self):
        r = self.runner(self.leg)
        st = self.run_leg(dataclasses.replace(self.leg, hw_dir=Path("/nope")), r)
        self.assertEqual(st.status, "NO_HW")
        st = self.run_leg(dataclasses.replace(self.leg, loader="sd"), r)
        self.assertEqual(st.status, "NO_SD_DATA")
        self.assertEqual(r.commands, [])

    def test_jtag_lock_held_while_flashing_only(self):
        seen = {}
        def probe(step):
            def effect():
                seen[step] = probe_jtag(self.settings)
            return effect
        r = self.runner(self.leg, effects={"T-lenet5_build": probe("build"),
                                           "T-lenet5_flash": probe("flash"),
                                           "T-lenet5_info": probe("info")})
        self.assertEqual(self.run_leg(self.leg, r).status, "OK")
        self.assertEqual(seen, {"build": "took", "flash": "blocked", "info": "took"})

    def test_dry_run_prints_commands_without_side_effects(self):
        r = self.runner(self.leg)
        r.dry_run = True
        st = self.run_leg(dataclasses.replace(self.leg, hw_dir=Path("/nope")), r)
        self.assertEqual(st.status, "DRY_RUN")
        self.assertEqual(len(r.commands), 7)
        self.assertEqual(self.checked, [])
        self.assertFalse((self.settings.work / "status").exists())

    def campaign(self, runner, legs, **kw):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            sts = run_campaign(runner, self.settings, legs, check=self.check, **kw)
        return sts, out.getvalue()

    def test_run_resumes_and_reruns_stale_legs(self):
        self.campaign(self.runner(self.leg), [self.leg])
        r = self.runner(self.leg)
        sts, _ = self.campaign(r, [self.leg])
        self.assertEqual(sts[0].status, "OK")
        self.assertEqual(r.logs, ["vta_options"])  # nothing re-run
        # A persisted option changes what the leg would run with: stale.
        base = dict(self.defaults, **{"vta.pool.loop": "true"})
        self.assertIn("stale", status_table(self.settings, [self.leg], base))
        r = self.runner(self.leg, base=base)
        self.campaign(r, [self.leg])
        self.assertIn("T-lenet5_build", r.logs)

    def test_persisted_options_are_warned_about(self):
        base = dict(self.defaults, **{"vta.direct.conv": "true"})
        _, out = self.campaign(self.runner(self.leg, base=base), [self.leg])
        self.assertIn("vta.direct.conv=true", out)
        self.assertIn("default false", out)

    def test_exception_in_leg_is_recorded_and_campaign_continues(self):
        second = dataclasses.replace(self.leg, tag="T-second")
        def check(settings, board, port):
            if not self.checked:
                self.checked.append(port)
                raise RuntimeError("udevadm: not found")
        r = self.runner(second)
        with contextlib.redirect_stdout(io.StringIO()):
            sts = run_campaign(r, self.settings, [self.leg, second], check=check)
        self.assertEqual([(s.status, s.step) for s in sts],
                         [("FAIL", "internal"), ("OK", "")])
        self.assertIn("udevadm", sts[0].detail)
