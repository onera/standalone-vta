#!/usr/bin/env python3
"""
create_vitis_workspace.py - Automate Vitis 2023.x / 2024.x / 2025.x workspace creation
for standalone VTA baremetal applications.

What this script does:
  1. Creates (or reuses) a Vitis workspace directory.
  2. Creates a hardware platform component from a Vivado XSA file.
  3. Builds the platform.
  4. Creates a bare-metal application component with an empty template.
  5. Copies all VTA driver sources + the chosen runner into the app src directory.

Runners (--runner)
------------------
  run_nn       - one-shot inference; input pre-loaded before execution
  run_nn_uart  - interactive UART loop; input received over UART each iteration
  test_gemm    - standalone GEMM hardware correctness test (no generated headers needed)

Data loaders (--data-loader, not applicable to test_gemm)
----------------------------------------------------------
  tcl  - static model data loaded via XSDB load_nn_static.tcl before the ELF starts
  elf  - static model data embedded in the ELF via .incbin; FSBL loads it

Generated files copied for both data loaders (produced by gen_nn_baremetal.py)
  vta_hw_config.h   - C++ type aliases (vta_inp_t, vta_out_t, …) derived from the
                      hardware config; required by vta_cpu_ops.cc at compile time
  nn_ddr_map.h      - LayerDesc array with per-layer DDR addresses
  nn_exec_plan.h    - typed execution step array (VTA + CPU ops)

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
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository layout (relative to this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent  # src/fpga/software/host/
SOFTWARE_DIR = SCRIPT_DIR.parent              # src/fpga/software/
INCLUDE_DIR = SOFTWARE_DIR / "driver" / "include"
SRC_DIR = SOFTWARE_DIR / "driver" / "src"
EXAMPLES_DIR = SOFTWARE_DIR / "apps"
TEST_GEMM_DIR = SOFTWARE_DIR / "apps" / "test_gemm"
CONFIG_DIR = SOFTWARE_DIR / "gen"

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
        "vta_hw_config.h",  # type aliases (vta_inp_t etc.) used by vta_cpu_ops.cc
        "nn_ddr_map.h",
        "nn_exec_plan.h",
    ],
    "elf": [
        "vta_hw_config.h",  # type aliases (vta_inp_t etc.) used by vta_cpu_ops.cc
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
    Return {dest_relative_path: src_path} for files copied into the app.

    Driver headers and sources are NOT copied - they are referenced directly
    from the repository via absolute paths written into UserConfig.cmake by
    _patch_user_config().  Only runner-specific files are copied:

      <runner>.cc   - runner entry point (root; picked up by aux_source_directory)
      <extras>      - e.g. init_dram.h for test_gemm (root)
      <generated>   - nn_ddr_map.h, nn_exec_plan.h, nn_bin_data.S, … (root)
    """
    files: dict[Path, Path] = {}

    runner_src = RUNNER_SOURCE[runner]
    if not runner_src.exists():
        sys.exit(f"ERROR: runner source not found: {runner_src}")
    files[Path(runner_src.name)] = runner_src

    for extra in RUNNER_EXTRAS[runner]:
        files[Path(extra.name)] = extra

    if data_loader is not None:
        for fname in DATA_LOADER_GENERATED[data_loader]:
            files[Path(fname)] = CONFIG_DIR / fname

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


def _patch_user_config(app_src: Path, baud: int = 921600) -> None:
    """Append driver paths and compile definitions to UserConfig.cmake.

    The driver is referenced from its repository location, so no files are
    copied.  Appending at the end overrides the empty USER_* declarations
    that Vitis wrote earlier in the file; CMakeLists.txt reads the final
    values after the full include() of UserConfig.cmake completes.
    """
    cfg = app_src / "UserConfig.cmake"
    if not cfg.exists():
        print(f"[copy] WARNING: UserConfig.cmake not found at {cfg}.")
        return
    include_rel = Path(os.path.relpath(INCLUDE_DIR, app_src)).as_posix()
    src_rel = Path(os.path.relpath(SRC_DIR, app_src)).as_posix()
    with cfg.open("a") as f:
        f.write(
            "\n# VTA driver - referenced in-place from the repository\n"
            f'set(USER_INCLUDE_DIRECTORIES "{include_rel}")\n'
            f'file(GLOB _drv_sources "{src_rel}/*.cc")\n'
            # Also glob *.S at the app root: picks up nn_bin_data.S for the ELF
            # data-loader; empty glob is harmless for the TCL loader.
            'file(GLOB _asm_sources "${CMAKE_CURRENT_SOURCE_DIR}/*.S")\n'
            "set(USER_COMPILE_SOURCES ${_drv_sources} ${_asm_sources})\n"
            f'set(USER_COMPILE_DEFINITIONS "VTA_UART_BAUD={baud}")\n'
        )
    print(f"[copy] Added driver paths and VTA_UART_BAUD={baud} to UserConfig.cmake.")


def _patch_linker_script(app_src: Path, ld_fragment: str) -> None:
    """Append INCLUDE <ld_fragment> to the Vitis linker script.

    The fragment file is expected to be in the same directory as lscript.ld
    (i.e. already copied to app_src).  GNU ld resolves the INCLUDE path
    relative to the script that contains it, so no path prefix is needed.
    Appending at the end works for any linker script since GNU ld allows
    multiple SECTIONS commands and top-level INCLUDE directives.
    """
    lscript = app_src / "lscript.ld"
    if not lscript.exists():
        print(f"[ld] WARNING: lscript.ld not found at {lscript}.")
        return
    include_line = f"INCLUDE {ld_fragment}"
    text = lscript.read_text()
    if include_line in text:
        print(f"[ld] lscript.ld already includes {ld_fragment}, skipping.")
        return
    with lscript.open("a") as f:
        f.write(f"\n{include_line}\n")
    print(f"[ld] Added '{include_line}' to lscript.ld.")


def _patch_asm_incbin(app_src: Path) -> None:
    """Rewrite .incbin paths in nn_bin_data.S to be relative to app_src.

    gen_nn_baremetal.py embeds absolute POSIX paths so the file is portable
    across copy destinations; this function relativizes them once the file
    lands in its final location.
    """
    import re
    asm = app_src / "nn_bin_data.S"
    if not asm.exists():
        return
    pattern = re.compile(r'^(\s*\.incbin\s+")([^"]+)(")')
    lines = asm.read_text(encoding="utf-8").splitlines(keepends=True)
    patched = []
    for line in lines:
        m = pattern.match(line)
        if m:
            rel = Path(os.path.relpath(m.group(2), app_src)).as_posix()
            line = m.group(1) + rel + m.group(3) + line[m.end():]
        patched.append(line)
    asm.write_text("".join(patched), encoding="utf-8")
    print(f"[asm] Patched .incbin paths in nn_bin_data.S relative to {app_src}")


def copy_sources(
    app_src: Path, runner: str, data_loader: str | None, baud: int = 921600
) -> None:
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
    _patch_user_config(app_src, baud)
    if data_loader == "elf":
        _patch_asm_incbin(app_src)
        _patch_linker_script(app_src, "nn_vta_sections.ld")


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
        print("  3. source gen/load_nn_static.tcl   (static model data)")
        if runner == "run_nn":
            print("  4. source gen/load_input.tcl       (input_nn.bin)")
            print("  5. con  - board runs inference once and exits.")
        else:
            print("  4. con  - board waits for UART trigger.")
            print("  5. python host/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ...")
    elif dl == "elf":
        print("  1. Add src/nn_bin_data.S to UserConfig.cmake sources in Vitis.")
        print("  2. Add inside your platform linker script SECTIONS { ... }:")
        print("       INCLUDE nn_vta_sections.ld")
        print("  3. Build the ELF in Vitis (static model data loaded by FSBL).")
        if runner == "run_nn":
            print("  4. In XSDB: dow application.elf")
            print("  5. source gen/load_input.tcl   (input_nn.bin)")
            print("  6. con  - board runs inference once and exits.")
        else:
            print("  4. In XSDB: dow application.elf, then con.")
            print("  5. python host/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ...")


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
        nargs="+",
        default=None,
        metavar="LOADER",
        help=(
            "One or more data loading strategies for run_nn / run_nn_uart: "
            "'tcl' = XSDB scripts pre-load static model data; "
            "'elf' = static data embedded in the ELF via .incbin. "
            "Multiple values create one app component per strategy. "
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
        "--baud",
        type=int,
        default=921600,
        metavar="RATE",
        help="UART baud rate passed to VTA_UART_BAUD compile definition.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling Vitis APIs.",
    )
    args = parser.parse_args()

    runners: list[str] = list(dict.fromkeys(args.runner))
    data_loaders: list[str] | None = (
        list(dict.fromkeys(args.data_loader)) if args.data_loader else None
    )

    # Validate data-loader requirement
    needs_loader = [r for r in runners if r in RUNNERS_WITH_DATA_LOADER]
    if needs_loader and data_loaders is None:
        sys.exit(
            f"ERROR: --data-loader {{tcl,elf}} is required for runner(s): {needs_loader}"
        )

    # Build (runner, data_loader) combos — one app per pair
    combos: list[tuple[str, str | None]] = []
    for r in runners:
        if r in RUNNERS_WITH_DATA_LOADER:
            for dl in data_loaders:  # type: ignore[union-attr]
                combos.append((r, dl))
        else:
            combos.append((r, None))

    if args.app_name and len(combos) > 1:
        sys.exit(
            "ERROR: --app-name cannot be used with multiple --runner / --data-loader values."
        )

    xsa = Path(args.xsa).resolve() if args.xsa else None
    workspace = Path(args.workspace).resolve()
    xpfm = xpfm_path(workspace, args.platform_name)

    app_names = {
        (r, dl): (args.app_name if args.app_name else _app_name(r, dl))
        for r, dl in combos
    }

    if args.dry_run:
        mode = "update (add app to existing workspace)" if xsa is None else "create"
        print("=== DRY RUN ===")
        print(f"  Mode:        {mode}")
        print(f"  XSA:         {xsa or '(not provided - using existing platform)'}")
        print(f"  Workspace:   {workspace}")
        print(f"  Platform:    {args.platform_name}")
        print(f"  CPU:         {args.cpu}")
        for runner, dl in combos:
            print()
            print(f"  Application: {app_names[(runner, dl)]}  "
                  f"(runner={runner}, data-loader={dl or 'n/a'})")
            print("  Files that would be copied:")
            for dest_rel, src_path in collect_sources(runner, dl).items():
                exists = "ok" if src_path.exists() else "MISSING"
                rel = src_path.relative_to(SOFTWARE_DIR)
                print(f"    [{exists:7s}]  {rel} → {dest_rel}")
            if dl == "elf":
                print("  Linker script: lscript.ld ← INCLUDE nn_vta_sections.ld (appended)")
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

        app_srcs: dict[tuple[str, str | None], Path] = {}
        for runner, dl in combos:
            app_srcs[(runner, dl)] = create_app(
                client, workspace, app_names[(runner, dl)], xpfm, args.cpu
            )
    finally:
        client.close()

    for (runner, dl), app_src in app_srcs.items():
        copy_sources(app_src, runner, dl, args.baud)

    print()
    print("=== Done ===")
    print(f"  Workspace : {workspace}")
    print(f"  Platform  : {workspace / args.platform_name}")
    for (runner, dl), app_src in app_srcs.items():
        print(f"  App src   : {app_src}  ({app_names[(runner, dl)]})")

    for runner, dl in combos:
        _next_steps(runner, dl)


if __name__ == "__main__":
    main()
