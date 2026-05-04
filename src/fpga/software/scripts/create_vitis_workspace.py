#!/usr/bin/env python3
"""
create_vitis_workspace.py — Automate Vitis 2023.x / 2024.x / 2025.x workspace creation
for standalone VTA baremetal applications.

What this script does:
  1. Creates (or reuses) a Vitis workspace directory.
  2. Creates a hardware platform component from a Vivado XSA file.
  3. Builds the platform.
  4. Creates a bare-metal application component with an empty template.
  5. Copies all VTA driver sources + the chosen runner into the app src directory.

Runners (--runner)
------------------
  run_nn       — one-shot inference; input pre-loaded before execution
  run_nn_uart  — interactive UART loop; input received over UART each iteration
  test_gemm    — standalone GEMM hardware correctness test (no generated headers needed)

Data loaders (--data-loader, not applicable to test_gemm)
----------------------------------------------------------
  tcl  — static model data loaded via XSDB load_nn_static.tcl before the ELF starts
  elf  — static model data embedded in the ELF via .incbin; FSBL loads it

Usage
-----
  # Source the Vitis environment first:
  source ~/Xilinx/2025.2/Vitis/settings64.sh

  vitis -s src/fpga/software/scripts/create_vitis_workspace.py \\
      --xsa         <path/to/design.xsa>                        \\
      --workspace   <path/to/workspace>                         \\
      [--platform-name vta_platform]                            \\
      --runner      run_nn_uart                                  \\
      [--data-loader tcl]                                       \\
      [--cpu        psu_cortexa53_0]

Note on the vitis Python module
--------------------------------
  The `vitis` module ships with Vitis and is only available through the Vitis
  Python interpreter.  Either source the Vitis settings script before running
  this file, or invoke it as:

      $VITIS_INSTALL/bin/python3 src/fpga/software/scripts/create_vitis_workspace.py ...

  where VITIS_INSTALL is e.g. ~/Xilinx/2025.2/Vitis.
"""

import argparse
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository layout (relative to this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent  # src/fpga/software/scripts/
SOFTWARE_DIR = SCRIPT_DIR.parent              # src/fpga/software/
INCLUDE_DIR = SOFTWARE_DIR / "include"
SRC_DIR = SOFTWARE_DIR / "src"
EXAMPLES_DIR = SOFTWARE_DIR / "examples"
TEST_GEMM_DIR = SOFTWARE_DIR / "test_gemm"
CONFIG_DIR = SOFTWARE_DIR / "config"

# ---------------------------------------------------------------------------
# Runner / data-loader configuration
# ---------------------------------------------------------------------------

# Source file for each runner, relative to SOFTWARE_DIR
RUNNER_SOURCE: dict[str, Path] = {
    "run_nn":      EXAMPLES_DIR / "run_nn.cc",
    "run_nn_uart": EXAMPLES_DIR / "run_nn_uart.cc",
    "test_gemm":   TEST_GEMM_DIR / "test_gemm.cc",
}

# Extra files to copy alongside the runner source (e.g. local headers)
RUNNER_EXTRAS: dict[str, list[Path]] = {
    "run_nn":      [],
    "run_nn_uart": [],
    "test_gemm":   [TEST_GEMM_DIR / "init_dram.h"],
}

# Generated config files required by each data-loader
# (placed in config/, must exist before this script runs)
DATA_LOADER_GENERATED: dict[str, list[str]] = {
    "tcl": [
        "nn_ddr_map.h",
        "nn_exec_plan.h",
    ],
    "elf": [
        "nn_ddr_map.h",
        "nn_exec_plan.h",
        "nn_bin_data.S",
        "nn_vta_sections.ld",
    ],
}

# Runners that require a data-loader selection
RUNNERS_WITH_DATA_LOADER = {"run_nn", "run_nn_uart"}

# ---------------------------------------------------------------------------
# Source file collection
# ---------------------------------------------------------------------------


def collect_sources(runner: str, data_loader: str | None) -> dict[Path, Path]:
    """
    Return {dest_relative_path: src_path}.

    Layout inside the app src directory:
      include/*.h        — VTA driver headers
      src/*.cc           — VTA driver sources
      src/<runner>.cc    — the selected runner
      src/<extras>       — runner-specific extra files (e.g. init_dram.h)
      src/<generated>    — config headers / linker / asm from gen_nn_baremetal.py
    """
    files: dict[Path, Path] = {}

    for h in sorted(INCLUDE_DIR.glob("*.h")):
        files[Path("include") / h.name] = h

    for cc in sorted(SRC_DIR.glob("*.cc")):
        files[Path("src") / cc.name] = cc

    runner_src = RUNNER_SOURCE[runner]
    if not runner_src.exists():
        sys.exit(f"ERROR: runner source not found: {runner_src}")
    files[Path("src") / runner_src.name] = runner_src

    for extra in RUNNER_EXTRAS[runner]:
        files[Path("src") / extra.name] = extra

    if data_loader is not None:
        for fname in DATA_LOADER_GENERATED[data_loader]:
            files[Path("src") / fname] = CONFIG_DIR / fname

    return files


# ---------------------------------------------------------------------------
# Vitis API helpers
# ---------------------------------------------------------------------------


def _domain_name(cpu: str) -> str:
    return f"standalone_{cpu}"


def xpfm_path(workspace: Path, platform_name: str) -> Path:
    return (
        workspace / platform_name / "export" / platform_name / f"{platform_name}.xpfm"
    )


def create_workspace_and_platform(
    client,
    workspace: Path,
    xsa: Path,
    platform_name: str,
    cpu: str,
) -> Path:
    print(f"[vitis] Setting workspace: {workspace}")
    client.set_workspace(path=str(workspace))

    xpfm = xpfm_path(workspace, platform_name)
    if xpfm.exists():
        print(f"[vitis] Platform already exists at {xpfm}, skipping creation.")
        return xpfm

    print(f"[vitis] Creating platform '{platform_name}' from {xsa}")
    platform = client.create_platform_component(
        name=platform_name,
        hw_design=str(xsa),
        os="standalone",
        cpu=cpu,
    )

    print("[vitis] Building platform…")
    platform.build()
    print(f"[vitis] Platform built → {xpfm}")
    return xpfm


def create_app(
    client,
    workspace: Path,
    app_name: str,
    xpfm: Path,
    cpu: str,
) -> Path:
    app_src = workspace / app_name / "src"
    if app_src.exists():
        print(f"[vitis] Application src directory already exists: {app_src}")
        return app_src

    print(f"[vitis] Creating application '{app_name}'")
    client.create_app_component(
        name=app_name,
        platform=str(xpfm),
        domain=_domain_name(cpu),
        template="empty_application",
    )

    app_src.mkdir(parents=True, exist_ok=True)
    return app_src


def copy_sources(app_src: Path, runner: str, data_loader: str | None) -> None:
    sources = collect_sources(runner, data_loader)
    print(f"[copy] Copying files to {app_src}")
    for dest_rel, src_path in sources.items():
        if not src_path.exists():
            print(
                f"WARNING: skipping missing file '{dest_rel}' "
                f"(run gen_nn_baremetal.py first, then copy manually)"
            )
            continue
        dest = app_src / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        print(f"       {src_path.relative_to(SOFTWARE_DIR)} → {dest_rel}")


def _app_name(runner: str, data_loader: str | None) -> str:
    if data_loader is None:
        return f"vta_{runner}"
    return f"vta_{runner}_{data_loader}"


def _next_steps(runner: str, data_loader: str | None) -> None:
    dl = data_loader or ""
    print(f"\nNext steps (runner={runner}, data-loader={dl or 'n/a'}):")
    if runner == "test_gemm":
        print("  1. Build the application in Vitis.")
        print("  2. In XSDB: dow application.elf, then con.")
        return
    if dl == "tcl":
        print("  1. Build the application in Vitis.")
        print("  2. In XSDB: dow application.elf")
        print("  3. source config/load_nn_static.tcl   (static model data)")
        if runner == "run_nn":
            print("  4. source config/load_input.tcl       (input_nn.bin)")
            print("  5. con  — board runs inference once and exits.")
        else:
            print("  4. con  — board waits for UART trigger.")
            print("  5. python scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ...")
    elif dl == "elf":
        print("  1. Add src/nn_bin_data.S to UserConfig.cmake sources in Vitis.")
        print("  2. Add inside your platform linker script SECTIONS { ... }:")
        print("       INCLUDE nn_vta_sections.ld")
        print("  3. Build the ELF in Vitis (static model data loaded by FSBL).")
        if runner == "run_nn":
            print("  4. In XSDB: dow application.elf")
            print("  5. source config/load_input.tcl   (input_nn.bin)")
            print("  6. con  — board runs inference once and exits.")
        else:
            print("  4. In XSDB: dow application.elf, then con.")
            print("  5. python scripts/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ...")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Vitis 2025.x workspace for VTA baremetal inference.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--xsa",
        metavar="PATH",
        help=(
            "Path to the Vivado-exported XSA hardware description file. "
            "Omit to add an application to an existing workspace "
            "(the platform must already be built)."
        ),
    )
    parser.add_argument(
        "--workspace",
        default="vitis_workspace",
        metavar="PATH",
        help="Vitis workspace directory (created if it does not exist).",
    )
    parser.add_argument(
        "--platform-name",
        default="vta_platform",
        metavar="NAME",
        help="Name for the hardware platform component.",
    )
    parser.add_argument(
        "--runner",
        choices=list(RUNNER_SOURCE.keys()),
        nargs="+",
        default=["run_nn"],
        metavar="RUNNER",
        help=(
            "One or more runner applications to create as separate app components. "
            "Choices: run_nn, run_nn_uart, test_gemm. "
            "Example: --runner run_nn run_nn_uart"
        ),
    )
    parser.add_argument(
        "--data-loader",
        choices=list(DATA_LOADER_GENERATED.keys()),
        default=None,
        metavar="LOADER",
        help=(
            "Data loading strategy for run_nn / run_nn_uart: "
            "'tcl' = XSDB scripts pre-load static model data; "
            "'elf' = static data embedded in the ELF via .incbin. "
            "Not required for test_gemm."
        ),
    )
    parser.add_argument(
        "--cpu",
        default="psu_cortexa53_0",
        metavar="CPU",
        help="BSP processor instance name (from xparameters.h).",
    )
    parser.add_argument(
        "--app-name",
        metavar="NAME",
        help=(
            "Override the application component name. "
            "Cannot be used with multiple --runner values."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling Vitis APIs.",
    )
    args = parser.parse_args()

    runners: list[str] = list(dict.fromkeys(args.runner))

    # Validate data-loader requirement
    needs_loader = [r for r in runners if r in RUNNERS_WITH_DATA_LOADER]
    if needs_loader and args.data_loader is None:
        sys.exit(
            f"ERROR: --data-loader {{tcl,elf}} is required for runner(s): {needs_loader}"
        )

    if args.app_name and len(runners) > 1:
        sys.exit("ERROR: --app-name cannot be used with multiple --runner values.")

    xsa = Path(args.xsa).resolve() if args.xsa else None
    workspace = Path(args.workspace).resolve()
    xpfm = xpfm_path(workspace, args.platform_name)

    # Resolve data-loader per runner (None for test_gemm)
    def runner_loader(r: str) -> str | None:
        return args.data_loader if r in RUNNERS_WITH_DATA_LOADER else None

    app_names = {
        r: (args.app_name if args.app_name else _app_name(r, runner_loader(r)))
        for r in runners
    }

    if args.dry_run:
        mode = "update (add app to existing workspace)" if xsa is None else "create"
        print("=== DRY RUN ===")
        print(f"  Mode:        {mode}")
        print(f"  XSA:         {xsa or '(not provided — using existing platform)'}")
        print(f"  Workspace:   {workspace}")
        print(f"  Platform:    {args.platform_name}")
        print(f"  CPU:         {args.cpu}")
        for runner in runners:
            dl = runner_loader(runner)
            print()
            print(f"  Application: {app_names[runner]}  "
                  f"(runner={runner}, data-loader={dl or 'n/a'})")
            print("  Files that would be copied:")
            for dest_rel, src_path in collect_sources(runner, dl).items():
                exists = "ok" if src_path.exists() else "MISSING"
                rel = src_path.relative_to(SOFTWARE_DIR)
                print(f"    [{exists:7s}]  {rel} → {dest_rel}")
        return

    if xsa is not None and not xsa.exists():
        sys.exit(f"ERROR: XSA file not found: {xsa}")

    if xsa is None and not xpfm.exists():
        sys.exit(
            f"ERROR: --xsa not provided and no built platform found at:\n"
            f"         {xpfm}\n"
            f"       Provide --xsa to create the platform first, or check --platform-name."
        )

    try:
        import vitis  # type: ignore[import]
    except ModuleNotFoundError:
        sys.exit(
            "ERROR: 'vitis' Python module not found.\n"
            "       Source the Vitis settings script first:\n"
            "         source ~/Xilinx/2025.2/Vitis/settings64.sh\n"
            "       or run this script with the Vitis Python interpreter:\n"
            "         $VITIS_INSTALL/bin/python3 create_vitis_workspace.py ..."
        )

    workspace.mkdir(parents=True, exist_ok=True)
    client = vitis.create_client()
    try:
        if xsa is not None:
            xpfm = create_workspace_and_platform(
                client, workspace, xsa, args.platform_name, args.cpu
            )
        else:
            print(f"[vitis] Setting workspace: {workspace}")
            client.set_workspace(path=str(workspace))
            print(f"[vitis] Using existing platform at {xpfm}")

        app_srcs: dict[str, Path] = {}
        for runner in runners:
            app_srcs[runner] = create_app(
                client, workspace, app_names[runner], xpfm, args.cpu
            )
    finally:
        client.close()

    for runner in runners:
        copy_sources(app_srcs[runner], runner, runner_loader(runner))

    print()
    print("=== Done ===")
    print(f"  Workspace : {workspace}")
    print(f"  Platform  : {workspace / args.platform_name}")
    for runner in runners:
        print(f"  App src   : {app_srcs[runner]}  ({app_names[runner]})")

    for runner in runners:
        _next_steps(runner, runner_loader(runner))


if __name__ == "__main__":
    main()
