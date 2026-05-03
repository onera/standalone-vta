#!/usr/bin/env python3
"""
create_vitis_workspace.py — Automate Vitis 2023.x / 2024.x / 2025.x workspace creation
for standalone VTA baremetal applications.

What this script does:
  1. Creates (or reuses) a Vitis workspace directory.
  2. Creates a hardware platform component from a Vivado XSA file.
  3. Optionally adds BSP libraries (xilffs for SD card runner).
  4. Builds the platform.
  5. Creates a bare-metal application component with an empty template.
  6. Copies all VTA driver sources + the chosen runner into the app src directory.

Runners (one or more may be selected)
--------------------------------------
  xsdb  — run_nn.cc : DDR pre-initialised via XSDB load_nn.tcl
  elf   — run_nn.cc : model data embedded in the ELF, loaded by FSBL

Usage
-----
  # Source the Vitis environment first:
  source /tools/Xilinx/Vitis/2025.2/settings64.sh

  vitis -s src/fpga/software/scripts/create_vitis_workspace.py \\
      --xsa       <path/to/design.xsa>                         \\
      --workspace <path/to/workspace>                          \\
      [--platform-name vta_platform]                           \\
      [--runner        xsdb elf]                               \\
      [--cpu           psu_cortexa53_0]

Note on the vitis Python module
--------------------------------
  The `vitis` module ships with Vitis and is only available through the Vitis
  Python interpreter.  Either source the Vitis settings script before running
  this file, or invoke it as:

      $VITIS_INSTALL/bin/python3 src/fpga/software/scripts/create_vitis_workspace.py ...

  where VITIS_INSTALL is e.g. /tools/Xilinx/Vitis/2025.2.
"""

import argparse
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository layout (relative to this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent  # src/fpga/software/scripts/
SOFTWARE_DIR = SCRIPT_DIR.parent  # src/fpga/software/
INCLUDE_DIR = SOFTWARE_DIR / "include"
SRC_DIR = SOFTWARE_DIR / "src"
EXAMPLES_DIR = SOFTWARE_DIR / "examples"
CONFIG_DIR = SOFTWARE_DIR / "config"

# ---------------------------------------------------------------------------
# Runner configuration
# ---------------------------------------------------------------------------

RUNNER_FILES: dict[str, str] = {
    "xsdb": "run_nn.cc",
    "elf": "run_nn.cc",
}

# Generated files required by each runner (placed in config/, must exist before this script)
RUNNER_GENERATED_FILES: dict[str, list[str]] = {
    "xsdb": ["nn_ddr_map.h", "nn_exec_plan.h", "nn_platform.h"],
    "elf": [
        "nn_ddr_map.h",
        "nn_exec_plan.h",
        "nn_platform.h",
        "nn_bin_data.S",
        "nn_vta_sections.ld",
    ],
}

# BSP libraries required by each runner
RUNNER_BSP_LIBS: dict[str, list[str]] = {
    "xsdb": [],
    "elf": [],
}

# ---------------------------------------------------------------------------
# Source file collection
# ---------------------------------------------------------------------------


def collect_sources(runner: str) -> dict[Path, Path]:
    """
    Return {dest_relative_path: src_path} preserving the subfolder tree:
      software/include/*.h   → include/
      software/src/*.cc      → src/
      software/examples/…    → examples/
      software/config/…      → config/   (generated; may be absent)
    Always includes generated config files (even if absent) so callers can warn.
    """
    files: dict[Path, Path] = {}

    for h in sorted(INCLUDE_DIR.glob("*.h")):
        files[Path("include") / h.name] = h

    for cc in sorted(SRC_DIR.glob("*.cc")):
        files[Path("src") / cc.name] = cc

    runner_cc = EXAMPLES_DIR / RUNNER_FILES[runner]
    if not runner_cc.exists():
        sys.exit(f"ERROR: runner file not found: {runner_cc}")
    files[Path("src") / runner_cc.name] = runner_cc

    for fname in RUNNER_GENERATED_FILES[runner]:
        files[Path("src") / fname] = CONFIG_DIR / fname

    return files


# ---------------------------------------------------------------------------
# Vitis API helpers
# ---------------------------------------------------------------------------


def _domain_name(cpu: str) -> str:
    """Standard Vitis domain name for a bare-metal CPU."""
    return f"standalone_{cpu}"


def create_workspace_and_platform(
    client,
    workspace: Path,
    xsa: Path,
    platform_name: str,
    cpu: str,
    bsp_libs: list[str],
) -> Path:
    """
    Create platform component, add BSP libraries, build, and return the .xpfm path.
    """
    print(f"[vitis] Setting workspace: {workspace}")
    client.set_workspace(path=str(workspace))

    xpfm = (
        workspace / platform_name / "export" / platform_name / f"{platform_name}.xpfm"
    )

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

    if bsp_libs:
        print(f"[vitis] Adding BSP libraries: {bsp_libs}")
        domain_name = _domain_name(cpu)
        domain = platform.get_domain(domain_name)
        for lib in bsp_libs:
            domain.set_lib(lib)

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
    """
    Create an empty bare-metal application component and return its src directory.
    """
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


def copy_sources(app_src: Path, runner: str) -> None:
    """Copy all VTA driver and example files into the application src directory,
    preserving the include/ src/ examples/ subfolder tree."""
    sources = collect_sources(runner)
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
        required=True,
        metavar="PATH",
        help="Path to the Vivado-exported XSA hardware description file.",
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
        choices=["xsdb", "elf"],
        nargs="+",
        default=["xsdb"],
        metavar="RUNNER",
        help=(
            "One or more runners to create as separate app components: "
            "'xsdb' = XSDB pre-loaded DDR, "
            "'elf' = ELF-embedded data (FSBL loads model). "
            "Example: --runner xsdb elf"
        ),
    )
    parser.add_argument(
        "--cpu",
        default="psu_cortexa53_0",
        metavar="CPU",
        help="BSP processor instance name (from xparameters.h).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling Vitis APIs.",
    )
    args = parser.parse_args()

    # Deduplicate while preserving order
    runners: list[str] = list(dict.fromkeys(args.runner))
    invalid = [r for r in runners if r not in RUNNER_FILES]
    if invalid:
        sys.exit(f"ERROR: unknown runner(s): {invalid}")

    xsa = Path(args.xsa).resolve()
    workspace = Path(args.workspace).resolve()

    if not xsa.exists():
        sys.exit(f"ERROR: XSA file not found: {xsa}")

    # BSP libs: union across all selected runners
    bsp_libs: list[str] = []
    for r in runners:
        for lib in RUNNER_BSP_LIBS[r]:
            if lib not in bsp_libs:
                bsp_libs.append(lib)

    app_names = {r: f"vta_run_nn_{r}" for r in runners}

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"  XSA:           {xsa}")
        print(f"  Workspace:     {workspace}")
        print(f"  Platform:      {args.platform_name}")
        print(f"  CPU:           {args.cpu}")
        print(f"  BSP libraries: {bsp_libs or '(none)'}")
        for runner in runners:
            print()
            print(
                f"  Application: {app_names[runner]}  (runner={runner}, src={RUNNER_FILES[runner]})"
            )
            print("  Files that would be copied:")
            for dest_rel, src_path in collect_sources(runner).items():
                exists = "ok" if src_path.exists() else "MISSING"
                rel = src_path.relative_to(SOFTWARE_DIR)
                print(f"    [{exists:7s}]  {rel} → {dest_rel}")
        return

    # Import vitis here so --dry-run works without Vitis installed
    try:
        import vitis  # type: ignore[import]
    except ModuleNotFoundError:
        sys.exit(
            "ERROR: 'vitis' Python module not found.\n"
            "       Source the Vitis settings script first:\n"
            "         source /tools/Xilinx/Vitis/2025.2/settings64.sh\n"
            "       or run this script with the Vitis Python interpreter:\n"
            "         $VITIS_INSTALL/bin/python3 create_vitis_workspace.py ..."
        )

    workspace.mkdir(parents=True, exist_ok=True)

    client = vitis.create_client()
    try:
        xpfm = create_workspace_and_platform(
            client, workspace, xsa, args.platform_name, args.cpu, bsp_libs
        )
        app_srcs: dict[str, Path] = {}
        for runner in runners:
            app_srcs[runner] = create_app(
                client, workspace, app_names[runner], xpfm, args.cpu
            )
    finally:
        client.close()

    for runner in runners:
        copy_sources(app_srcs[runner].parent, runner)

    print()
    print("=== Done ===")
    print(f"  Workspace : {workspace}")
    print(f"  Platform  : {workspace / args.platform_name}")
    for runner in runners:
        print(f"  App src   : {app_srcs[runner]}  ({runner})")

    for runner in runners:
        print()
        if runner == "xsdb":
            print(f"Next steps ({runner}):")
            print("  1. Run gen_nn_baremetal.py to regenerate config/ files:")
            print("       --out-header --out-exec-plan --out-platform --out-tcl")
            print("  2. Build the application in Vitis.")
            print("  3. In XSDB: source load_nn.tcl, then con.")
        elif runner == "elf":
            print(f"Next steps ({runner}):")
            print("  1. Run gen_nn_baremetal.py to regenerate config/ files:")
            print("       --out-header --out-exec-plan --out-platform")
            print("       --out-asm --out-lscript --out-input-tcl")
            print("  2. In your platform linker script, add inside SECTIONS { ... }:")
            print("       INCLUDE nn_vta_sections.ld")
            print(
                "  3. Build the ELF in Vitis (model data loaded by FSBL, no XSDB needed)."
            )
            print("  4. In XSDB: source load_input.tcl, then con.")


if __name__ == "__main__":
    main()
