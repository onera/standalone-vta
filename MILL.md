# Advanced usage: driving the build with Mill

The root `Makefile` (see the [Quickstart](README.md#3-quickstart)) is a thin
front end over Mill: every target is one `./mill` invocation with a few
`-Dvta.*` flags. This document covers everything the Makefile does not expose:
the module layout, the full task list, per-model caching, the FPGA and Vitis
tasks, the global options and tab completion.
For more information using mill, refer to the [official documentation](https://mill-build.org/mill/index.html).

Run the commands below from the repository root, inside the Pixi environment
(`pixi shell`, or prefix each one with `pixi run`).

- [Invoking Mill](#invoking-mill)
- [Build layout](#build-layout)
- [`run` vs `examples.onnx`: what gets cached](#run-vs-examplesonnx-what-gets-cached)
- [Pipeline tasks](#pipeline-tasks)
- [Raw VTA IR fixtures](#raw-vta-ir-fixtures)
- [FPGA targets](#fpga-targets)
- [Vitis workspaces](#vitis-workspaces)
- [SD-card file sets](#sd-card-file-sets)
- [On-board isolation debugging](#on-board-isolation-debugging)
- [Post-synthesis gate-level check](#post-synthesis-gate-level-check)
- [Module-level tasks](#module-level-tasks)
- [Global options](#global-options)
- [Where the outputs land](#where-the-outputs-land)
- [Tab completion](#tab-completion)

## Invoking Mill

A mill build is made of Modules and Tasks, which can be invoked with a dot-notation.
For example to compile the module `modules/hardware` we run:

```bash
./mill modules.hardware.compile
```

In this build, cross modules are defined to cleanly separate cached artifacts alongside several axis: model, VTA hardware config, FPGA board.
For example, the module run is a cross configuration module. To access it you call `./mill` with the `run[configKey]` notation:

```bash
./mill "run[vta_config].fsim"
```

The dot-notation also works:

```bash
./mill run.vta_config.fsim
```

> [!note]
> Cross modules have default keys, so the following command is valid and equivalent.
>
> ```bash
> ./mill run[].fsim
> ```

- **Quote the task path.** The `[...]` cross selector is glob syntax in most
  shells.
- **Use `-i` (or `--no-daemon`) in scripts.** Mill runs a long-lived daemon by
  default, which may be killed during a long invocation such as an FPGA
  synthesis. The root Makefile passes `-i` for that reason.
- **Chain tasks in one invocation** by separating them with `+`:
  `./mill "run[vta_config].fsim" + "run[vta_config].vsim"`.
- **`_` matches one segment, `__` matches several segments.** Add `--keep-going`
  (`-k`) to see every failure rather than only the first.
- **Trailing arguments go to the underlying tool** for tasks declared as
  commands (`fsim`, `vsim`, `createVitisProject`, ...).

Two introspection commands are worth knowing:

```bash
./mill resolve "run[vta_config]._"   # what tasks exist here
./mill inspect "run[vta_config].fsim" # what a task does, and its arguments
```

## Build layout

| Address                                                                                 | What it is                                                                                                            |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `run[<config>]`                                                                         | The full ONNX pipeline for the model named by `-Dvta.onnx.file`, built for `<config>`. What the root Makefile drives. |
| `examples.onnx[<model>,<config>]`                                                       | The same pipeline, but keyed by both the model and the config, for models under `examples/onnx/`.                     |
| `examples.ir[<fixture>,<config>]`                                                       | Compile and simulate a hand-written VTA IR fixture from `examples/vta_ir/`.                                           |
| `targets[<config>,<board>]`                                                             | The Vivado build: IP packaging, project, synthesis, XSA, Vitis platform.                                              |
| `modules.hardware`, `modules.simulator[<config>]`, `modules.compiler`, `modules.fpga.*` | The per-module tasks the pipelines are built from.                                                                    |

The cross keys are read from the filesystem, so **adding a config to `config/`,
a model to `examples/onnx/`, a fixture to `examples/vta_ir/` or a board JSON to
`modules/fpga/boards/` adds its cross entries with no build-file edit.**

```bash
./mill resolve "examples.onnx[_,_]"      # every (model, config) pair
./mill resolve "targets[_,_]"            # every (config, board) pair
```

## `run` vs `examples.onnx`: what gets cached

Both expose exactly the same tasks (they are the same pipeline traits), and
they differ only in what identifies an instance:

- `run[<config>]` is crossed on the **config only**. The model comes from the
  global `-Dvta.onnx.file` property, so it can be any `.onnx` file anywhere in
  the repository, but **switching model overwrites the previous model's results**
  in the same task directories.
- `examples.onnx[<model>,<config>]` is crossed on **both**. Each pair is
  independently cached, so several models and configs coexist and none of them
  invalidates the others. Restricted to the models in `examples/onnx/`.

Use `run[...]` (or the Makefile) for a single model you iterate on; use
`examples.onnx[...]` when you are moving between models, or want to build a set
in one command:

```bash
./mill "examples.onnx[_,vta_config].fsim"   # every model, one config
./mill "examples.onnx[_,_].fsim"            # every (model, config) pair
```

Everything below is written with `examples.onnx[lenet5,vta_config]`; substitute
`run[vta_config]` (plus `-Dvta.onnx.file=<path>`) to get the Makefile's
behaviour.

## Pipeline tasks

| Task                        | Kind    | What it does                                                                          |
| --------------------------- | ------- | ------------------------------------------------------------------------------------- |
| `compile`                   | cached  | `nn_compiler` + `vta_compiler`: the `.bin` / `.csv` streams.                          |
| `reference`                 | cached  | The ONNX reference: `input_nn.bin` (network input) + `reference.bin` (golden output). |
| `fsim`                      | command | Run the functional (C++) simulator, then check against the reference.                 |
| `vsim`                      | command | Run the Verilated RTL simulator, then check against the reference.                    |
| `layerDumps`                | cached  | Per-layer fsim goldens (`--dump-layers`), shared by the debug and post-synth flows.   |
| `genBaremetal`              | cached  | The baremetal PS headers (`nn_exec_plan.h`, `nn_ddr_map.h`, ...). No Vivado needed.   |
| `genBaremetalDebug`         | cached  | `genBaremetal` plus the debug maps, wired to `layerDumps`.                            |
| `sdCard` / `sdCardDebug`    | command | Stage the `.bin` set (and, for `Debug`, the goldens) for a FAT32 card.                |
| `createVitisProject`        | command | Add this model's app components to the (config, board) Vitis workspace.               |
| `createVitisProjectFromXsa` | command | Same, from an XSA you already have, with no Vivado run.                               |
| `addVitisDebugApps`         | command | Add the on-board isolation apps (`run_nn_debug`, `run_nn_cpu_debug`).                 |
| `runUart`                   | command | Drive a board running `run_nn_uart` over a serial port and check its output.          |
| `postSynth`                 | command | Gate-level xsim check of a layer subset against the fsim goldens.                     |

```bash
# Compile (both compiler stages) and produce the ONNX reference
./mill "examples.onnx[lenet5,vta_config].compile"

# Simulate and check: functional first, then the Verilated RTL. Each compiles
# first if stale, then always simulates.
./mill "examples.onnx[lenet5,vta_config].fsim"
./mill "examples.onnx[lenet5,vta_config].vsim"

# Same model, a different config: independent, cached, buildable together
./mill "examples.onnx[lenet5,vta_w8b].fsim"
```

`fsim` and `vsim` are commands, so trailing arguments go straight to the
simulator binary: `./mill "examples.onnx[lenet5,vta_config].fsim" --layer 3
--verbose`, or `--no-timeout --trace` for `vsim`. Neither re-invokes the Python
compiler itself: both depend on `compile`, which only re-runs when the model,
config or compiler sources actually change.

## Raw VTA IR fixtures

The fixtures in `examples/vta_ir/` are VTA IR already, so they skip
`nn_compiler` and with it the ONNX reference, which is why they have no golden
to check against. `check` runs both simulators on the same cached compile and
byte-compares their outputs instead, failing the build on any difference:

```bash
./mill "examples.ir[matmul_16x16,vta_config].compile"
./mill "examples.ir[matmul_16x16,vta_config].check"   # fsim vs vsim, byte for byte
./mill "examples.ir[_,_].check"                       # every fixture, every config
```

`fsim` and `vsim` exist here too, and run the fixture's single layer. There is
no Makefile target for these: IR fixtures are Mill-only.

The baremetal, Vitis and post-synthesis tasks are deliberately absent from
`examples.ir`: they consume full-network artifacts, namely `dependency.csv`,
which only `nn_compiler` writes, and `input_nn.bin`, which only the ONNX
reference writes.

## FPGA targets

An FPGA build is identified by both its config (which fixes the RTL) and its
board (which fixes the pinout and XSA), so each pair is independently
addressable and cached. Flipping between boards does not re-synthesize the
other one.

| Task            | What it does                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------- |
| `ipRepo`        | Package the emitted Xilinx shell as a Vivado IP. Fast, and cached on the RTL and board part only. |
| `fpgaProject`   | Create the Vivado project, stopping before synthesis. Persistent, so GUI edits survive.           |
| `synth`         | Synthesize and implement: bitstream, XSA, reports and `manifest.json`. Slow.                      |
| `oocNetlist`    | OOC-synthesize the debug shell to a gate-level netlist, the DUT of `postSynth`.                   |
| `vitisPlatform` | Create/refresh the Vitis workspace and hardware platform from the synthesized XSA.                |
| `boardJson`     | The board definition this target reads (content-tracked).                                         |

```bash
./mill "targets[vta_w8b,zcu104].synth"         # bitstream + XSA
./mill "targets[vta_w8b,vek280].fpgaProject"   # Vivado project only
```

Boards are the JSONs under `modules/fpga/boards/`. The pipeline tasks that need
a board (`createVitisProject`, `addVitisDebugApps`, `postSynth`) pick theirs
from `-Dvta.board.name` (default `zcu104`), since they are not board-crossed:

```bash
./mill -Dvta.board.name=vek280 "examples.onnx[lenet5,vta_w8b].createVitisProject"
```

## Vitis workspaces

`createVitisProject` adds this model's **app components** to the workspace owned
by `targets[<config>,<board>].vitisPlatform`, which it builds first if stale
(synthesizing the XSA if needed). The platform is model-independent, so several
models coexist in one workspace per (config, board); the components are named
`<model>_<runner>[_<loader>]`. Requires Vivado and Vitis.

```bash
./mill "examples.onnx[lenet5,vta_config].createVitisProject" \
    --runner run_nn run_nn_uart --data-loader elf sd
```

`--runner` and `--data-loader` both accept several values, creating one app
component per combination. Runners: `run_nn`, `run_nn_uart`, `run_nn_debug`,
`run_nn_cpu_debug`, `test_gemm`, `sd_loader_test`. Loaders: `tcl` (XSDB pushes
the data over JTAG), `elf` (data embedded via `.incbin`), `sd` (the board reads
a FAT32 card at boot). See
[`modules/fpga/software/README.md`](modules/fpga/software/README.md).

### From an existing XSA

When a suitable XSA already exists (a colleague's build, a GUI-made design, an
archived handoff), `createVitisProjectFromXsa` skips synthesis entirely and
hands the file straight to `create_vitis_workspace.py`:

```bash
./mill "examples.onnx[lenet5,vta_config].createVitisProjectFromXsa" \
    --xsa vta_zcu104.xsa --runner run_nn --data-loader elf
```

The two commands share only the generated headers; nothing in this one's task
graph reaches Vivado. Mill fills in the workspace directory
(`build/vitis/<model>_<config>` here, kept across runs so the platform is not
rebuilt), this model's `genBaremetal` output and the app-name prefix. Repeat any
of those flags to override them, since the script keeps the last occurrence.
Everything else is yours, including `--cpu` for a non-ZynqMP board (the script
defaults to `psu_cortexa53_0`).

> [!warning]
> The XSA is _not_ checked against the active config: a bitstream synthesized for
> a different block size than the compiled binaries will run and produce garbage.

## SD-card file sets

`genBaremetal` always emits `nn_sd_manifest.h`, so `--data-loader sd` builds
with no extra step. It does not copy the `.bin` streams themselves, which would
bloat every cached gen dir. `sdCard` stages those:

```bash
./mill "examples.onnx[lenet5,vta_config].sdCard"
```

It prints the folder to copy to the root of a FAT32 card. Files land in a
per-model subfolder (`0:/lenet5/instructions_L0.bin`), so one card can hold
several models, and the codegen is deterministic, so the staged addresses match
the app built from `genBaremetal`.

`xilffs` (FatFs) is enabled when the platform is _created_, so a workspace built
before any SD app was requested cannot build one. Point `--workspace` at a fresh
directory.

## On-board isolation debugging

`run_nn_debug` and `run_nn_cpu_debug` check every layer on the board against the
fsim goldens instead of only the final output. That needs an fsim
`--dump-layers` run, a codegen wired to those dumps, and an app built with the
debug runner. `addVitisDebugApps` chains all three:

```bash
./mill "examples.onnx[lenet5,vta_config].addVitisDebugApps"
./mill "examples.onnx[lenet5,vta_config].addVitisDebugApps" --runner run_nn_cpu_debug
```

It defaults to `--runner run_nn_debug --data-loader elf` and shares the
workspace and platform of `createVitisProject`, so it synthesizes if the
bitstream is stale. The goldens (`layerDumps`) are cached and shared with
`postSynth`. For `--data-loader sd`, stage the card with `sdCardDebug` rather
than `sdCard`: the plain set carries no goldens, and a debug run without them
has nothing to compare against.

## Post-synthesis gate-level check

`postSynth` compiles the model, dumps the per-layer fsim goldens, emits the
post-synth testbench, runs xsim behavioral and netlist simulations, and compares
the netlist output to the golden. It takes the layer subset as its argument:

```bash
./mill "examples.onnx[lenet5,vta_config].postSynth" QLinearConv1,MaxPool2
```

The slow OOC synthesis is not redone per run: the netlist comes from the cached
`targets[<config>,<board>].oocNetlist`, which depends on config and board only,
so changing the model or the layer subset re-runs just the xsim legs. Requires
Vivado and xsim on `PATH`.

## Module-level tasks

Below the pipelines, each module exposes its own tasks. These are useful when
working on one component in isolation.

```bash
# Chisel tests (cycle-accurate simulation of the RTL)
./mill modules.hardware.test                 # everything
./mill modules.hardware.test.unittest        # only the vta.tags.UnitTests-tagged ones
./mill modules.hardware.test.testOnly simulatorTest.ComputeTest
./mill modules.hardware.test.testWaves simulatorTest.ComputeTest   # + FST traces

# Emit SystemVerilog for one config
./mill "modules.hardware.configs[vta_w8b].vtaSimConfig"   # simulation shell (DPI)
./mill "modules.hardware.configs[vta_w8b].vtaFpgaConfig"  # Xilinx RTL + package_ip.tcl

# Build the simulators for one config
./mill "modules.simulator[vta_w8b].fsimBinary"
./mill "modules.simulator[vta_w8b].vsimBinary"
```

The Chisel tests run against the bundled
`modules/hardware/src/test/resources/vta_config_test.json` unless
`-Dvta.config.file` names another config.

A set of flat pass-through commands takes the config from the global
`-Dvta.config.file` and forwards its arguments to the underlying Scala or
Python entry point: `modules.hardware.emitVtaSimConfig`,
`modules.hardware.emitVtaFpgaConfig`, `modules.hardware.emitVtaPostSynthTb`,
`modules.fpga.synthesis.buildFpga`, `modules.fpga.synthesis.packageIp`,
`modules.fpga.synthesis.oocNetlist`, `modules.fpga.synthesis.runXsim`,
`modules.fpga.synthesis.compareOut`, `modules.fpga.software.genNnBaremetal`,
`modules.fpga.software.createVitisWorkspace`,
`modules.fpga.software.checkOutput`, `modules.fpga.software.auditDram`. They are
uncached escape hatches: prefer the crossed tasks above, which cache.

The per-module Makefiles (`examples/Makefile`, `modules/simulator/Makefile`,
`modules/fpga/software/Makefile`) predate the Mill build and remain available
for standalone use outside it. They read `-Dvta.config.file`-style config
selection through their own `CONFIG` variables; see `make help` in each.

## Global options

Options that are not cross axes are passed as JVM properties:

| Property                | Default                     | Effect                                                                                                   |
| ----------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------- |
| `vta.onnx.file`         | `examples/onnx/lenet5.onnx` | Model compiled by `run[<config>]`.                                                                       |
| `vta.config.file`       | `vta_config.json`           | Config for the flat, non-crossed tasks.                                                                  |
| `vta.board.name`        | `zcu104`                    | Board for the pipeline tasks that need one.                                                              |
| `vta.ddr.base`          | `0x0`                       | DDR base address baked into the baremetal codegen. Must match the board.                                 |
| `vta.verilator.threads` | `4`                         | Verilator build threads. Changing it invalidates the `vsim` tasks.                                       |
| `vta.vivado.jobs`       | `4`                         | Vivado parallel jobs. A runtime flag: changing it does not invalidate anything.                          |
| `vta.xil.out`           | unset                       | Shallow root for the heavy Vivado/Vitis trees (`<dir>/<config>/<board>/`), for Windows long-path limits. |

### Pinning options between runs

Rather than repeating `-Dvta.*` flags on every invocation, persist them:

```bash
./mill configure vta.board.name=te0803 vta.ddr.base=0x10000000
```

This writes a generated, git-ignored `.mill-jvm-opts` at the repository root,
which applies from the next `./mill` invocation onwards. Later calls merge into
it, so options not mentioned are kept:

```bash
./mill configure                 # show the options in effect
./mill configure vta.ddr.base=   # drop one option, back to its default
./mill configure --reset         # drop all of them
```

A flag still wins for a single run: `./mill -Dvta.ddr.base=0xBEEF <task>`.

Do not hand-edit `.mill-jvm-opts`. It replaces (rather than adds to) the
`//| mill-jvm-opts` header of `build.mill`, so it has to carry
`-Dchisel.project.root`, which `configure` emits for you. Any other line you put
there, such as an `-Xmx` setting for the build JVM, is preserved across
`configure` runs, but `--reset` deletes the file and everything in it.

## Where the outputs land

Every task writes into its own directory under `out/`, mirroring the task path:

```text
out/run/<config>/                       compile.dest/, fsim.dest/, vsim.dest/, ...
out/examples/onnx/<model>/<config>/     same set, one per (model, config)
out/examples/ir/<fixture>/<config>/     compile.dest/, check.dest/{fsim,vsim}/
out/targets/<config>/<board>/           ipRepo.dest/, fpgaProject.dest/, synth.dest/, ...
out/modules/simulator/<config>/         fsimBinary.dest/, vsimBinary.dest/
```

The C++/Verilator simulator is built once per config and cached, and the FPGA
bitstream once per (config, board) pair, so switching config, board, or adding a
new example model does not rebuild everything.

Clean selectively rather than deleting `out/`:

```bash
./mill clean "run[vta_config]"           # one config's run artifacts
./mill clean "run._"                     # every config's
./mill clean "targets[vta_config,zcu104]"
```

Vivado and Vitis trees that are not worth content-hashing live outside `out/`,
under `build/` (or under `-Dvta.xil.out` when set).

## Tab completion

`./mill <Tab>` can complete task names and show each task's description (its
`/** ... */` doc comment in the `*.mill` build files). Completion is a shell
hook that calls `mill --tab-complete` live on every keypress, so the candidate
list always matches the current build. Enable it once per clone by sourcing the
script for your shell (use your clone's path):

```bash
# bash / zsh - add to ~/.bashrc or ~/.zshrc
source /path/to/standalone-vta/tools/completions/mill-completion.sh

# fish - add to ~/.config/fish/config.fish
source /path/to/standalone-vta/tools/completions/mill-completion.fish
```

Restart the shell (or re-`source` the rc file) and press `<Tab>` after `./mill`.

If [`fzf`](https://github.com/junegunn/fzf) is installed (it ships in the pixi
env), `<Tab>` opens a drill-down picker instead of the plain menu: the full
description shows in a preview pane, `<Tab>` descends into a module's sub-tasks
(e.g. `examples` -> `onnx` -> model -> config), `<Left>` goes back up, and
`<Enter>` accepts the highlighted path. Without fzf it falls back to a native
single-line menu. Both rely on the `mill-fzf-level` helper beside these scripts,
so keep the three `tools/completions/` files together.

Mill also ships an installer that writes the bash/zsh hook and edits your rc
files for you: `./mill mill.tabcomplete/install`.

A task shows a description only if it has a doc comment; add a `/** ... */`
above a `def ... = Task { ... }` to describe it.
