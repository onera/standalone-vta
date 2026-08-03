#!/usr/bin/env python3
"""
create_vitis_workspace.py - Automate Vitis 2023.x / 2024.x / 2025.x workspace creation
for standalone VTA baremetal applications.

What this script does:
  1. Creates (or reuses) a Vitis workspace directory.
  2. Creates a hardware platform component from a Vivado XSA file (rebuilt via
     update_hw when the XSA content changed since the platform was built).
  3. Builds the platform.
  4. Creates a bare-metal application component with an empty template.
  5. Copies all VTA driver sources + the chosen runner into the app src directory.

The platform depends only on the XSA (config/board); the applications depend on
the model too. The two halves can run separately:
  --platform-only          workspace + platform from --xsa, no apps (xilffs is
                           enabled so later SD apps need no platform rebuild)
  (no --xsa)               add apps to an existing, already-built platform
  --name-prefix <model>    app components named <model>_<runner>[_<loader>]
                           instead of the default vta_<runner>[_<loader>], so
                           several models coexist in one workspace

Runners (--runner)
------------------
  run_nn            - one-shot inference; input pre-loaded before execution.
  run_nn_uart       - interactive UART loop; input received over UART each iteration
  run_nn_debug      - per-layer VTA isolation check (debug): each layer runs on fsim
                      golden inputs, output compared vs fsim golden output. Requires
                      the elf loader + gen_nn_baremetal.py --emit-layer-check;
                      sets the NN_CHECK_LAYERS compile definition automatically.
                      Add --pl-reset-between-layers to pulse a PL-only fabric reset
                      (ZynqMP pl_resetn0) before each layer.
  run_nn_cpu_debug  - per-CPU-op isolation check (debug, sibling of run_nn_debug):
                      each FORMAT_INPUT / IM2ROW / INT32_CHAIN step runs alone and
                      its output is compared vs the consumer layer's golden input
                      dump.  Requires the elf loader + gen_nn_baremetal.py
                      --emit-layer-check --emit-cpu-check; sets NN_CHECK_CPU_OPS_ISO.
  test_gemm         - standalone GEMM hardware correctness test
                      (requires gen/init_dram.h from `make gen-test_gemm`)
  sd_loader_test    - standalone SD-card -> DRAM read test.  Depends only on the
                      Xilinx BSP + xilffs (FatFs); no VTA driver, no generated
                      headers, no data-loader.  Enables the xilffs BSP library on
                      the platform.  See docs/fpga/sdcard_loader.md.

Data loaders (--data-loader, not applicable to test_gemm / sd_loader_test)
----------------------------------------------------------
  tcl  - static model data loaded via XSDB load_nn_static.tcl before the ELF starts
  elf  - static model data embedded in the ELF via .incbin; FSBL loads it

Generated files copied for every non-standalone app (produced by gen_nn_baremetal.py)
  vta_hw_config.h   - C++ type aliases (vta_inp_t, vta_out_t, ...) derived from the
                      hardware config; required by vta_cpu_ops.cc at compile time.
                      Copied unconditionally (test_gemm needs it too, despite
                      having no data-loader).

Generated files copied for both data loaders
  nn_ddr_map.h      - LayerDesc array with per-layer DDR addresses
  nn_exec_plan.h    - typed execution step array (VTA + CPU ops)
  nn_debug_map.h    - (run_nn_debug only) DebugLayerDesc array with per-layer golden
                      input/output addresses and the input destination buffer

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

SCRIPT_DIR = Path(__file__).resolve().parent  # src/fpga/software/host/
SOFTWARE_DIR = SCRIPT_DIR.parent  # src/fpga/software/
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
    "run_nn": EXAMPLES_DIR / "run_nn.cc",
    "run_nn_uart": EXAMPLES_DIR / "run_nn_uart.cc",
    "run_nn_debug": EXAMPLES_DIR / "run_nn_debug.cc",
    "run_nn_cpu_debug": EXAMPLES_DIR / "run_nn_cpu_debug.cc",
    "test_gemm": TEST_GEMM_DIR / "test_gemm.cc",
    "sd_loader_test": EXAMPLES_DIR / "sd_loader_test.cc",
}

# Extra files to copy alongside the runner source (e.g. local headers),
# named relative to the gen dir (see --gen-dir / gen_dir below) - resolved by
# collect_sources(), not baked in here, so a --gen-dir override applies to
# these too.
RUNNER_EXTRAS: dict[str, list[str]] = {
    "run_nn": [],
    "run_nn_uart": [],
    "run_nn_debug": [],
    "run_nn_cpu_debug": [],
    "test_gemm": ["init_dram.h"],
    "sd_loader_test": [],
}

# Extra generated headers (from CONFIG_DIR) required by specific runners,
# beyond what the data-loader already provides.
RUNNER_GENERATED_EXTRA: dict[str, list[str]] = {
    "run_nn_debug": ["nn_debug_map.h"],  # gen_nn_baremetal.py --emit-layer-check
    "run_nn_cpu_debug": [
        "nn_debug_map.h",  # CPU-op debug shares the same golden DRAM regions
        "nn_cpu_debug_map.h",  # gen_nn_baremetal.py --emit-cpu-check
    ],
}

# Extra compile definitions for specific runners.
RUNNER_DEFINES: dict[str, list[str]] = {
    "run_nn_debug": ["NN_CHECK_LAYERS"],  # enables the VTA isolation checker
    "run_nn_cpu_debug": [
        "NN_CHECK_CPU_OPS_ISO"
    ],  # enables the CPU-op isolation checker
}

# Generated config files required by each data-loader
# (placed in config/, must exist before this script runs)
# vta_hw_config.h is NOT listed here: it is required by every non-standalone
# app regardless of data-loader (see collect_sources), so it is copied
# unconditionally instead of being duplicated across these lists.
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
    "sd": [
        "nn_ddr_map.h",
        "nn_exec_plan.h",
        "nn_sd_manifest.h",  # file -> DDR map read by driver/src/vta_sd.cc
    ],
}

# Runners that require a data-loader selection.  run_nn_debug and
# run_nn_cpu_debug embed their golden data via .incbin, so they only make
# sense with the "elf" loader.
RUNNERS_WITH_DATA_LOADER = {
    "run_nn",
    "run_nn_uart",
    "run_nn_debug",
    "run_nn_cpu_debug",
}

# Standalone runners depend only on the Xilinx BSP; they do NOT pull in the VTA
# driver sources, generated headers, or a data-loader.  Their single .cc is
# compiled by Vitis' aux_source_directory, so UserConfig.cmake is left untouched.
STANDALONE_RUNNERS = {"sd_loader_test"}

# Runners that require the xilffs (FatFs) BSP library enabled on the platform
# domain.  Must be enabled before platform.build() so the BSP is generated with
# the library available to the application.
XILFFS_RUNNERS = {"sd_loader_test"}

# ---------------------------------------------------------------------------
# Source file collection
# ---------------------------------------------------------------------------


def collect_sources(
    runner: str, data_loader: str | None, gen_dir: Path
) -> dict[Path, Path]:
    """
    Return {dest_relative_path: src_path} for files copied into the app.

    Driver headers and sources are NOT copied - they are referenced directly
    from the repository via absolute paths written into UserConfig.cmake by
    _patch_user_config().  Only runner-specific files are copied:

      <runner>.cc   - runner entry point (root; picked up by aux_source_directory)
      <extras>      - e.g. init_dram.h for test_gemm (root)
      <generated>   - nn_ddr_map.h, nn_exec_plan.h, nn_bin_data.S, ... (root)

    gen_dir is where gen_nn_baremetal.py output lives - defaults to
    CONFIG_DIR (software/gen) but can be any directory (e.g. a Mill
    genBaremetal() cache dir for a specific model/config).
    """
    files: dict[Path, Path] = {}

    runner_src = RUNNER_SOURCE[runner]
    if not runner_src.exists():
        sys.exit(f"ERROR: runner source not found: {runner_src}")
    files[Path(runner_src.name)] = runner_src

    for extra in RUNNER_EXTRAS[runner]:
        files[Path(extra)] = gen_dir / extra

    if runner not in STANDALONE_RUNNERS:
        # Required by vta_cpu_ops.cc (and hence every VTA-driver app) at
        # compile time, independent of runner or data-loader selection.
        files[Path("vta_hw_config.h")] = gen_dir / "vta_hw_config.h"

    if data_loader is not None:
        for fname in DATA_LOADER_GENERATED[data_loader]:
            files[Path(fname)] = gen_dir / fname

    for fname in RUNNER_GENERATED_EXTRA.get(runner, []):
        files[Path(fname)] = gen_dir / fname

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


def _enable_xilffs(platform, cpu: str) -> None:
    """Add the xilffs (FatFs) library to the BSP so apps can read the SD card.

    Must be called before platform.build() so the BSP is generated with the
    library available.  Harmless for apps that do not use it.  The default
    xilffs interface targets the SD/eMMC controller, so no interface override
    is needed for a standard SD-card read.

    Long filenames are enabled (XILFFS_use_lfn=1): the sd data-loader opens the
    compiler basenames (e.g. "instructions_L0.bin") which exceed FAT 8.3.  The
    phase-1 sd_loader_test uses an 8.3 name so it does not depend on this.
    """
    try:
        domain = platform.get_domain(name=_domain_name(cpu))
        domain.set_lib(lib_name="xilffs")
        try:
            domain.set_config(
                option="lib", lib_name="xilffs", param="XILFFS_use_lfn", value="1"
            )
            print("[vitis] xilffs: long filenames enabled (XILFFS_use_lfn=1)")
        except Exception as exc:  # noqa: BLE001 - LFN param name may differ
            print(
                f"[vitis] WARNING: could not set XILFFS_use_lfn: {exc}\n"
                "         Long SD filenames (>8.3) may fail to open; check the"
                " exact param via domain.list_params('lib', lib_name='xilffs')."
            )
        print(f"[vitis] Enabled xilffs (FatFs) on domain {_domain_name(cpu)}")
    except Exception as exc:  # noqa: BLE001 - surface the failure, keep going
        print(
            f"[vitis] WARNING: could not enable xilffs: {exc}\n"
            "         SD apps will fail to compile (ff.h missing).\n"
            "         Enable it manually in the Vitis BSP settings."
        )


def _xsa_fingerprint(xsa: Path) -> str:
    import hashlib

    return hashlib.sha256(xsa.read_bytes()).hexdigest()


def create_workspace_and_platform(
    client,
    workspace: Path,
    xsa: Path,
    platform_name: str,
    cpu: str,
    enable_xilffs: bool = False,
) -> Path:
    print(f"[vitis] Setting workspace: {workspace}")
    client.set_workspace(path=str(workspace))

    xpfm = xpfm_path(workspace, platform_name)
    # Content fingerprint of the XSA the platform was built from: on rerun with
    # an identical XSA the platform is reused as-is; with a different one it is
    # refreshed in place via update_hw (no fresh workspace needed).
    stamp = workspace / f".{platform_name}.xsa.sha256"
    fingerprint = _xsa_fingerprint(xsa)
    if xpfm.exists():
        if stamp.exists() and stamp.read_text().strip() == fingerprint:
            print(f"[vitis] Platform up to date at {xpfm}, skipping build.")
            if enable_xilffs:
                print(
                    "[vitis] NOTE: platform already built; xilffs not (re)enabled.\n"
                    "         For sd_loader_test, build into a fresh --workspace dir."
                )
            return xpfm
        print(f"[vitis] XSA changed - updating platform '{platform_name}' from {xsa}")
        platform = client.get_component(name=platform_name)
        platform.update_hw(hw_design=str(xsa))
        print("[vitis] Rebuilding platform...")
        platform.build()
        stamp.write_text(fingerprint + "\n")
        print(f"[vitis] Platform rebuilt -> {xpfm}")
        return xpfm

    print(f"[vitis] Creating platform '{platform_name}' from {xsa}")
    platform = client.create_platform_component(
        name=platform_name,
        hw_design=str(xsa),
        os="standalone",
        cpu=cpu,
    )

    if enable_xilffs:
        _enable_xilffs(platform, cpu)

    print("[vitis] Building platform...")
    platform.build()
    stamp.write_text(fingerprint + "\n")
    print(f"[vitis] Platform built -> {xpfm}")
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


def _patch_user_config(
    app_src: Path, baud: int = 115200, extra_defines: list[str] | None = None
) -> None:
    """Append driver paths and compile definitions to UserConfig.cmake.

    The driver is referenced from its repository location, so no files are
    copied.  Appending at the end overrides the empty USER_* declarations
    that Vitis wrote earlier in the file; CMakeLists.txt reads the final
    values after the full include() of UserConfig.cmake completes.

    extra_defines are added to USER_COMPILE_DEFINITIONS (e.g. NN_CHECK_LAYERS
    for the run_nn_debug isolation app).
    """
    cfg = app_src / "UserConfig.cmake"
    if not cfg.exists():
        print(f"[copy] WARNING: UserConfig.cmake not found at {cfg}.")
        return
    marker = "# VTA driver - referenced in-place from the repository"
    if marker in cfg.read_text():
        print("[copy] UserConfig.cmake already patched, skipping.")
        return
    # Absolute paths work fine here; only the separator style matters, since
    # CMake wants forward slashes even on Windows.
    include_dir = INCLUDE_DIR.as_posix()
    src_dir = SRC_DIR.as_posix()
    defines = [f"VTA_UART_BAUD={baud}"] + list(extra_defines or [])
    defines_str = ";".join(defines)
    with cfg.open("a") as f:
        f.write(
            "\n# VTA driver - referenced in-place from the repository\n"
            f'set(USER_INCLUDE_DIRECTORIES "{include_dir}")\n'
            f'file(GLOB _drv_sources "{src_dir}/*.cc")\n'
            # Also glob *.S at the app root: picks up nn_bin_data.S for the ELF
            # data-loader; empty glob is harmless for the TCL loader.
            'file(GLOB _asm_sources "${CMAKE_CURRENT_SOURCE_DIR}/*.S")\n'
            "set(USER_COMPILE_SOURCES ${_drv_sources} ${_asm_sources})\n"
            f'set(USER_COMPILE_DEFINITIONS "{defines_str}")\n'
        )
    print(
        f"[copy] Added driver paths and definitions [{defines_str}] to UserConfig.cmake."
    )


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


def copy_sources(
    app_src: Path,
    runner: str,
    data_loader: str | None,
    gen_dir: Path,
    baud: int = 115200,
    extra_defines: list[str] | None = None,
) -> None:
    sources = collect_sources(runner, data_loader, gen_dir)
    print(f"[copy] Copying files to {app_src}")
    for dest_rel, src_path in sources.items():
        if not src_path.exists():
            print(
                f"WARNING: skipping missing file '{dest_rel}' "
                f"(run `make gen` first, then copy manually)"
            )
            continue
        dest = app_src / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        try:
            rel = src_path.relative_to(SOFTWARE_DIR)
        except ValueError:
            rel = src_path
        print(f"       {rel} -> {dest_rel}")
    if runner in STANDALONE_RUNNERS:
        # Standalone app: only its own .cc, compiled against the BSP (xilffs).
        # No VTA driver sources/includes, so UserConfig.cmake is left as-is.
        print(
            f"[copy] {runner} is standalone: no VTA driver sources added; "
            "app compiles against the BSP (xilffs) only."
        )
        return
    defines = list(RUNNER_DEFINES.get(runner, []))
    defines += list(extra_defines or [])
    if data_loader == "sd":
        # Activates the guarded SD-load path in run_nn / run_nn_uart and the
        # body of driver/src/vta_sd.cc (compiled to empty otherwise).
        defines.append("NN_SD_LOADER")
    _patch_user_config(app_src, baud, defines)
    if data_loader == "elf":
        # nn_bin_data.S already carries absolute POSIX .incbin paths from the
        # codegen, so it is copied in as-is.
        _patch_linker_script(app_src, "nn_vta_sections.ld")


def _app_name(prefix: str, runner: str, data_loader: str | None) -> str:
    if data_loader is None:
        return f"{prefix}_{runner}"
    return f"{prefix}_{runner}_{data_loader}"


def _next_steps(runner: str, data_loader: str | None) -> None:
    dl = data_loader or ""
    print(f"\nNext steps (runner={runner}, data-loader={dl or 'n/a'}):")
    if runner == "test_gemm":
        print("  1. Build the application in Vitis.")
        print("  2. In XSDB: dow application.elf, then con.")
        return
    if runner == "sd_loader_test":
        print("  1. Format a microSD as FAT32 and copy test.bin to its root.")
        print(
            "     Host checksum: python host/sd_checksum.py test.bin"
            "   (compare vs UART)."
        )
        print("  2. Build the application in Vitis.")
        print("  3. In XSDB, init the PS so the SD MIO/clocks are configured:")
        print("       fpga <design.bit>; targets -set -filter {name=~APU*}; rst")
        print("       loadhw <design.xsa>        (runs ps7_init/psu_init -> SD MIO)")
        print("       dow <fsbl.elf>; con; stop  (belt-and-suspenders PS init)")
        print("  4. dow sd_loader_test.elf; con")
        print("  5. Read UART: expect a byte count, checksum, and 'READBACK OK'.")
        return
    if runner == "run_nn_debug":
        if dl == "sd":
            print(
                "  1. Generate sources with --emit-sd-manifest --emit-layer-check"
                " --ref-dir <simulators_output> (--sd-dir <model> optional)."
            )
            print("  2. Copy gen/sd_card/* to a FAT32 SD card; insert it.")
            print(
                "  3. Build in Vitis (NN_SD_LOADER + NN_CHECK_LAYERS set; BSP has"
                " xilffs). Static model + golden refs are read from the card."
            )
            print("  4. In XSDB: program the bitstream, run ps7_init/psu_init (SD")
            print("     MIO + clocks), then: dow application.elf; con")
            print("  5. Read UART: each layer prints PASS or 'k/N mismatches'.")
            print("     The first mismatching layer is the VTA-introduced corruption.")
            return
        if dl != "elf":
            print(
                "  WARNING: run_nn_debug needs golden data in DDR; use the 'elf'"
                " (.incbin) or 'sd' data-loader. 'tcl' will not load the references."
            )
        print(
            "  1. Build the ELF in Vitis (static model data + golden in/out"
            " loaded by FSBL/.incbin; NN_CHECK_LAYERS is set)."
        )
        print("  2. In XSDB: dow application.elf, then con.")
        print("  3. Read UART: each layer prints PASS or 'k/N mismatches'.")
        print("     The first mismatching layer is the VTA-introduced corruption.")
        return
    if runner == "run_nn_cpu_debug":
        if dl == "sd":
            print(
                "  1. Generate sources with --emit-sd-manifest --emit-layer-check"
                " --emit-cpu-check --ref-dir <simulators_output>"
                " (--sd-dir <model> optional)."
            )
            print("  2. Copy gen/sd_card/* to a FAT32 SD card; insert it.")
            print(
                "  3. Build in Vitis (NN_SD_LOADER + NN_CHECK_CPU_OPS_ISO set; BSP"
                " has xilffs). Static model, raw input + goldens read from the card."
            )
            print("  4. In XSDB: program the bitstream, run ps7_init/psu_init (SD")
            print("     MIO + clocks), then: dow application.elf; con")
            print(
                "  5. Read UART: each FORMAT_INPUT / IM2ROW / INT32_CHAIN step"
                " prints PASS or 'k/N mismatches'."
            )
            print(
                "     The first mismatching step is the CPU-op-introduced corruption."
            )
            return
        if dl != "elf":
            print(
                "  WARNING: run_nn_cpu_debug needs golden data in DDR; use the 'elf'"
                " (.incbin) or 'sd' data-loader. 'tcl' will not load references."
            )
        print(
            "  1. Generate sources with --emit-layer-check --emit-cpu-check"
            " (the CPU-op map references the layer-check golden regions)."
        )
        print("  2. Build the ELF in Vitis (NN_CHECK_CPU_OPS_ISO is set).")
        print("  3. In XSDB: dow application.elf, then con.")
        print(
            "  4. Read UART: each FORMAT_INPUT / IM2ROW / INT32_CHAIN step"
            " prints PASS or 'k/N mismatches'."
        )
        print("     The first mismatching step is the CPU-op-introduced corruption.")
        return
    if dl == "sd":
        print("  1. Generate the manifest + staged files:")
        print("       make gen-sd CONFIG=<cfg> DDR_BASE=<base>")
        print("  2. Copy gen/sd_card/* to the root of a FAT32 SD card; insert it.")
        print("  3. Build the application in Vitis (NN_SD_LOADER set, BSP has xilffs).")
        print("  4. In XSDB: program the bitstream, then run ps7_init/psu_init so the")
        print("     SD MIO + clocks are configured, then: dow application.elf")
        if runner == "run_nn":
            print(
                "  5. con  - board reads model+input from SD, runs once, prints result."
            )
        else:
            print("  5. con  - board reads model from SD, then waits for UART input.")
            print(
                "  6. python host/uart_nn.py --port /dev/ttyUSB1 --input input_nn.bin ..."
            )
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
            print(
                "  5. python host/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ..."
            )
    elif dl == "elf":
        print("  1. Add src/nn_bin_data.S to UserConfig.cmake sources in Vitis.")
        print("  2. Build the ELF in Vitis (static model data loaded by FSBL).")
        if runner == "run_nn":
            print("  3. In XSDB: dow application.elf")
            print("  4. source gen/load_input.tcl   (input_nn.bin)")
            print("  5. con  - board runs inference once and exits.")
        else:
            print("  3. In XSDB: dow application.elf, then con.")
            print(
                "  4. python host/uart_nn.py --port /dev/ttyUSB0 --input input_nn.bin ..."
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _import_vitis():
    try:
        import vitis  # type: ignore[import]

        return vitis
    except ModuleNotFoundError:
        sys.exit(
            "ERROR: 'vitis' Python module not found.\n"
            "       Source the Vitis settings script first:\n"
            "         source /opt/Xilinx/2025.2/Vitis/settings64.sh\n"
            "       or run this script with the Vitis Python interpreter:\n"
            "         $VITIS_INSTALL/bin/python3 create_vitis_workspace.py ..."
        )


def _lock_is_free(lock: Path) -> bool:
    """Whether no live process currently holds `lock`.

    POSIX: probe with a non-blocking flock, the same advisory lock the Vitis
    server takes.  A failure to acquire it means the owner is still alive.

    Windows: `fcntl` does not exist there, and there is no portable equivalent.
    Report the lock as free and let the unlink itself be the probe: Windows
    refuses to delete a file that a live process holds open (the JVM does not
    open it with FILE_SHARE_DELETE), so the caller gets a PermissionError
    instead of silently dropping a live lock.
    """
    try:
        import fcntl
    except ModuleNotFoundError:
        return True
    try:
        with open(lock, "a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
            fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        # Cannot even open it (permissions, exotic filesystem): assume held.
        return False
    return True


def _clear_stale_workspace_lock(workspace: Path) -> None:
    """Drop the workspace lock left behind by a previous Vitis run.

    Vitis never removes _ide/.wsdata/.lock when its server exits, so the next
    set_workspace() on a persistent workspace fails with "is already in use".
    The file is only removed when no live process holds it.
    """
    lock = workspace / "_ide" / ".wsdata" / ".lock"
    if not lock.exists():
        return
    if not _lock_is_free(lock):
        print(f"[vitis] Workspace lock held by a live process, keeping it: {lock}")
        return
    try:
        lock.unlink()
    except OSError as exc:
        # On Windows this is how a live owner shows up (PermissionError).
        print(f"[vitis] WARNING: could not remove workspace lock {lock}: {exc}")
        return
    print(f"[vitis] Removed stale workspace lock: {lock}")


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
            "Choices: run_nn, run_nn_uart, test_gemm, run_nn_debug, "
            "run_nn_cpu_debug, sd_loader_test. "
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
            "One or more data loading strategies for the data-loader runners: "
            "'tcl' = XSDB scripts pre-load static model data; "
            "'elf' = static data (and debug goldens) embedded in the ELF via "
            ".incbin; 'sd' = the board reads the .bin set (and, for the debug "
            "runners, the golden refs) from a FAT32 SD card at boot. "
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
        "--platform-only",
        action="store_true",
        help=(
            "Create/refresh the workspace and platform from --xsa and stop: "
            "no application components. xilffs (FatFs) is enabled on the "
            "platform so SD-loader apps added later need no platform rebuild. "
            "--runner / --data-loader are ignored."
        ),
    )
    parser.add_argument(
        "--name-prefix",
        default="vta",
        metavar="PREFIX",
        help=(
            "Prefix of the application component names "
            "(<prefix>_<runner>[_<loader>]). Pass the model name to keep the "
            "apps of several models apart in a shared workspace."
        ),
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
        "--gen-dir",
        default=str(CONFIG_DIR),
        metavar="PATH",
        help=(
            "Directory containing the baremetal codegen output (vta_hw_config.h, "
            "nn_ddr_map.h, nn_exec_plan.h, ...). Defaults to <software>/gen; "
            "override to point at a specific model/config's generated headers "
            "(e.g. a Mill genBaremetal() cache dir)."
        ),
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        metavar="RATE",
        help="UART baud rate passed to VTA_UART_BAUD compile definition.",
    )
    parser.add_argument(
        "--pl-reset-between-layers",
        action="store_true",
        help=(
            "run_nn_debug only: pulse a PL-only fabric reset (ZynqMP pl_resetn0 "
            "= GPIO pin 173) before each layer so every layer runs on pristine "
            "VTA hardware state. Adds the NN_PL_RESET_BETWEEN_LAYERS define. "
            "Ignored for other runners."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling Vitis APIs.",
    )
    args = parser.parse_args()

    if args.platform_only:
        if args.xsa is None:
            sys.exit("ERROR: --platform-only requires --xsa")
        xsa = Path(args.xsa).resolve()
        workspace = Path(args.workspace).resolve()
        if args.dry_run:
            print("=== DRY RUN ===")
            print("  Mode:        platform-only (workspace + platform, no apps)")
            print(f"  XSA:         {xsa}")
            print(f"  Workspace:   {workspace}")
            print(f"  Platform:    {args.platform_name}")
            print(f"  CPU:         {args.cpu}")
            print("  BSP library: xilffs (FatFs) + LFN enabled")
            return
        if not xsa.exists():
            sys.exit(f"ERROR: XSA file not found: {xsa}")
        vitis = _import_vitis()
        workspace.mkdir(parents=True, exist_ok=True)
        _clear_stale_workspace_lock(workspace)
        client = vitis.create_client()
        try:
            xpfm = create_workspace_and_platform(
                client,
                workspace,
                xsa,
                args.platform_name,
                args.cpu,
                enable_xilffs=True,
            )
        finally:
            client.close()
            vitis.dispose()
        print()
        print("=== Done ===")
        print(f"  Workspace : {workspace}")
        print(f"  Platform  : {xpfm}")
        return

    runners: list[str] = list(dict.fromkeys(args.runner))
    data_loaders: list[str] | None = (
        list(dict.fromkeys(args.data_loader)) if args.data_loader else None
    )

    # Validate data-loader requirement
    needs_loader = [r for r in runners if r in RUNNERS_WITH_DATA_LOADER]
    if needs_loader and data_loaders is None:
        sys.exit(
            f"ERROR: --data-loader {{tcl,elf,sd}} is required for runner(s): {needs_loader}"
        )

    # Build (runner, data_loader) combos - one app per pair
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
    gen_dir = Path(args.gen_dir).resolve()
    xpfm = xpfm_path(workspace, args.platform_name)

    app_names = {
        (r, dl): (
            args.app_name if args.app_name else _app_name(args.name_prefix, r, dl)
        )
        for r, dl in combos
    }

    # --pl-reset-between-layers only applies to the per-layer isolation runner.
    def _extra_defines_for(runner: str) -> list[str]:
        if args.pl_reset_between_layers and runner == "run_nn_debug":
            return ["NN_PL_RESET_BETWEEN_LAYERS"]
        return []

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
            print(
                f"  Application: {app_names[(runner, dl)]}  "
                f"(runner={runner}, data-loader={dl or 'n/a'})"
            )
            print("  Files that would be copied:")
            for dest_rel, src_path in collect_sources(runner, dl, gen_dir).items():
                exists = "ok" if src_path.exists() else "MISSING"
                try:
                    rel = src_path.relative_to(SOFTWARE_DIR)
                except ValueError:
                    rel = src_path
                print(f"    [{exists:7s}]  {rel} -> {dest_rel}")
            for d in RUNNER_DEFINES.get(runner, []) + _extra_defines_for(runner):
                print(f"  Define: {d}")
            if dl == "sd":
                print("  Define: NN_SD_LOADER")
            if runner in STANDALONE_RUNNERS:
                print(
                    "  Standalone: no VTA driver sources; UserConfig.cmake left as-is."
                )
            if runner in XILFFS_RUNNERS or dl == "sd":
                print(
                    "  BSP library: xilffs (FatFs) + LFN enabled on the platform domain."
                )
            if dl == "elf":
                print(
                    "  Linker script: lscript.ld <- INCLUDE nn_vta_sections.ld (appended)"
                )
        return

    if xsa is not None and not xsa.exists():
        sys.exit(f"ERROR: XSA file not found: {xsa}")

    if xsa is None and not xpfm.exists():
        sys.exit(
            f"ERROR: --xsa not provided and no built platform found at:\n"
            f"         {xpfm}\n"
            f"       Provide --xsa to create the platform first, or check --platform-name."
        )

    vitis = _import_vitis()

    workspace.mkdir(parents=True, exist_ok=True)
    _clear_stale_workspace_lock(workspace)
    client = vitis.create_client()
    try:
        if xsa is not None:
            xpfm = create_workspace_and_platform(
                client,
                workspace,
                xsa,
                args.platform_name,
                args.cpu,
                enable_xilffs=(
                    any(r in XILFFS_RUNNERS for r in runners)
                    or (data_loaders is not None and "sd" in data_loaders)
                ),
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
        vitis.dispose()

    for (runner, dl), app_src in app_srcs.items():
        copy_sources(
            app_src, runner, dl, gen_dir, args.baud, _extra_defines_for(runner)
        )

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
