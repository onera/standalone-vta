"""campaign: prepare, stage and run measurement campaigns on the boards."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import mill
from .leg import warn_persisted, run_campaign, run_leg, status_table
from .sim_timing import sim_timing
from .stage_sd import stage_sd
from .matrix import Leg, load_campaign
from .runner import Runner
from .settings import Settings, load_settings


def _port(value: str) -> tuple[str, str]:
    board, sep, dev = value.partition("=")
    if not sep or not board or not dev:
        raise argparse.ArgumentTypeError(f"expected BOARD=DEVICE, got {value!r}")
    return board, dev


def _legs(args, settings: Settings) -> list[Leg]:
    legs = load_campaign(args.campaign, settings)
    if args.boards:
        legs = [l for l in legs if l.board in args.boards]
    return legs


def cmd_prepare(args, settings: Settings, runner: Runner) -> int:
    rows = mill.prepare(runner, _legs(args, settings))
    for what, result in rows:
        print(f"{result:7} {what}")
    return 0 if all(v == "ok" for _, v in rows) else 1


def cmd_stage_sd(args, settings: Settings, runner: Runner) -> int:
    result = stage_sd(runner, settings, _legs(args, settings))
    for sd_dir, status in result:
        print(f"{sd_dir:32} {status}")
    print(f"card trees under {settings.cards}")
    return 0 if all(s == "OK" for _, s in result) else 1


def cmd_sim_timing(args, settings: Settings, runner: Runner) -> int:
    path = sim_timing(runner, settings, args.models, args.config,
                      args.backends, args.runs)
    if not args.dry_run:
        print(path.read_text(), end="")
    return 0


def cmd_run(args, settings: Settings, runner: Runner) -> int:
    legs = _legs(args, settings)
    statuses = run_campaign(runner, settings, legs)
    if not args.dry_run:
        print(status_table(settings, legs, mill.vta_options(runner)))
    return 0 if all(s.status in ("OK", "DRY_RUN") for s in statuses) else 1


def cmd_leg(args, settings: Settings, runner: Runner) -> int:
    legs = {l.tag: l for l in _legs(args, settings)}
    if args.tag not in legs:
        print(f"no leg {args.tag!r} in {args.campaign}; tags:\n  "
              + "\n  ".join(legs), file=sys.stderr)
        return 2
    if not args.dry_run:
        warn_persisted(settings, mill.vta_options(runner))
    st = run_leg(runner, settings, legs[args.tag])
    print(f"{st.tag}: {st.status} {st.step} {st.detail}".rstrip())
    return 0 if st.status in ("OK", "DRY_RUN") else 1


def cmd_status(args, settings: Settings, runner: Runner) -> int:
    print(status_table(settings, _legs(args, settings), mill.vta_options(runner)))
    return 0


def _campaign_parser(sub, name: str, help: str, handler):
    p = sub.add_parser(name, help=help)
    p.add_argument("campaign", type=Path, help="campaign file (campaigns/*.toml)")
    p.add_argument("--boards", nargs="+", metavar="BOARD",
                   help="only the legs on these boards")
    p.set_defaults(handler=handler)
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="campaign", description=__doc__)
    p.add_argument("--settings", type=Path,
                   help="settings file read over tools/campaign/settings.toml")
    p.add_argument("--dry-run", action="store_true",
                   help="print the commands instead of running them")
    p.add_argument("--port", type=_port, action="append", default=[],
                   metavar="BOARD=DEVICE", help="override a board's UART port")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")
    _campaign_parser(sub, "prepare", "compile and simulate every pair up front (the fsim golden)",
                     cmd_prepare)
    _campaign_parser(sub, "stage-sd", "stage SD-card data for the SD-loader legs",
                     cmd_stage_sd)
    for name, help, handler in (
            ("run", "run every leg not already OK", cmd_run),
            ("leg", "run one leg of a campaign, by tag", cmd_leg)):
        r = _campaign_parser(sub, name, help, handler)
        if name == "leg":
            r.add_argument("tag")
    _campaign_parser(sub, "status", "show the status of every leg", cmd_status)
    t = sub.add_parser("sim-timing", help="time the simulator binaries alone")
    t.add_argument("--models", nargs="+", default=["lenet5", "resnet18", "qyolo"])
    t.add_argument("--config", default="vta_config")
    t.add_argument("--backends", nargs="+", default=["fsim", "vsim"],
                   choices=["fsim", "vsim"])
    t.add_argument("--runs", type=int, default=3)
    t.set_defaults(handler=cmd_sim_timing)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.settings, dict(args.port))
    runner = Runner(settings.work / "logs", args.dry_run)
    return args.handler(args, settings, runner)


if __name__ == "__main__":
    sys.exit(main())
