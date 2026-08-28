# Advanced usage: driving the build with Mill

The root `Makefile` (see the [Quickstart](README.md#2-quickstart)) is a thin
front end over Mill: every target is one `./mill` invocation with a few
`-Dvta.*` flags. This document covers everything the Makefile does not expose:
the module layout, the full task list, per-model caching, the FPGA and Vitis
tasks, the global options and tab completion.

No prior Mill knowledge is assumed. For the tool itself, the
[official documentation](https://mill-build.org/mill/index.html) is the
reference.

Run the commands below from the repository root, inside the Pixi environment
(`pixi shell`, or prefix each one with `pixi run`).

1. [Mill essentials](#1-mill-essentials) - modules, tasks, caching, how to call them
2. [What the build contains](#2-what-the-build-contains) - the module map and the global options
3. [Running a model](#3-running-a-model) - compile, simulate, check
4. [FPGA, Vitis and baremetal](#4-fpga-vitis-and-baremetal) - synthesis through to the board
5. [Working on a single module](#5-working-on-a-single-module)
6. [Reference](#6-reference) - output layout, cleaning, tab completion

## 1. Mill essentials

### How this build is put together

Five ideas carry the whole build. They are worth ten minutes, because every
section below is a consequence of them.

**Modules and tasks.** A Mill build is a tree of _modules_, each holding
_tasks_. You address a task by its path through the tree, with a dot between
segments, and that is also the command line:

```bash
./mill modules.hardware.compile    # the `compile` task of the `modules.hardware` module
```

**A cached task is a function of its inputs.** It declares what it depends on
(other tasks, source files, the config JSON), and Mill re-runs it only when one
of those changes. Ask for it twice in a row and the second call does nothing but
hand back the previous result. Ask for a task deep in the graph and everything it
needs is built first, if stale. `compile` is a cached task: `fsim` depends on it,
so running `fsim` compiles the model on a fresh clone and skips straight to the
simulator afterwards.

**Every task owns one output directory.** A task writes into its own
`out/<task path>.dest/` and nowhere else, which is what makes the caching safe:
two tasks can never fight over a file. That directory is the task's result, and
it survives until the task is invalidated or cleaned. See
[Where the outputs land](#where-the-outputs-land).

**A command always runs.** Some tasks are _commands_ rather than cached tasks:
they are actions, not artifacts, so Mill never skips them, and they accept
trailing arguments from the command line. Running a simulator is a command
(`fsim`, `vsim`); producing the binaries it consumes is a cached task
(`compile`). The task tables below mark which is which. In practice:

```bash
./mill "default.fsim"                      # compiles if stale, then always simulates
./mill "default.fsim" --layer 3 --verbose  # trailing args reach the simulator binary
```

**Cross modules give one cached instance per combination.** Most things here are
built for a particular _(model, config)_ or _(config, board)_ pair, and each pair
has to be cached separately: a bitstream for `zcu104` says nothing about
`vek280`. Mill expresses that with a _cross module_, which is a module
parameterised by one or more axes. You select an instance by putting the axis
values in brackets:

```bash
./mill "run[lenet5,vta_config].fsim"    # model lenet5, config vta_config
./mill run.lenet5.vta_config.fsim       # the same thing, dot notation
```

Because each instance caches independently, switching model, config or board
never invalidates the one you were using before: switching back finds it ready.

### Calling Mill

Five rules cover almost everything.

- **Quote the task path.** The `[...]` cross selector is glob syntax in most
  shells, so `./mill "run[lenet5,vta_config].fsim"` and not the bare form. The
  dot notation needs no quoting.
- **Chain tasks in one invocation** by separating them with `+`. This is cheaper
  than several invocations, which each pay daemon startup:
  `./mill "run[lenet5,vta_config].fsim" + "run[lenet5,vta_config].vsim"`.
- **`_` matches one segment, `__` matches any number.** A cross selector needs
  one entry per axis, so `run[_,_]` matches every instance of a two-axis module
  while `run[_]` matches nothing at all.
- **Add `--keep-going` (`-k`)** when selecting many instances, to see every
  failure instead of stopping at the first.
- **Trailing arguments go to the underlying tool**, for commands only (`fsim`,
  `vsim`, `createVitisProject`, ...).

Cross modules have default keys, taken from the `-Dvta.*` options, so all of
these address the same instance (the default `vta.onnx.file` and
`vta.config.file`):

```bash
./mill "run[lenet5,vta_config].fsim"   # explicit
./mill "run[].fsim"                    # both axes at their default
./mill default.fsim                    # `default` is an alias for that instance
```

### Finding tasks

You are not expected to memorise the task names. Three commands enumerate them,
and tab completion does it interactively:

```bash
./mill resolve "run[_,_]"                    # what instances exist
./mill resolve "run[lenet5,vta_config]._"    # what tasks exist there
./mill inspect "run[lenet5,vta_config].fsim" # what a task does, and its arguments
./mill show "run[lenet5,vta_config].compile" # a cached task's result, as JSON
```

`inspect` prints the task's doc comment and its direct inputs, which is the
fastest way to see why something re-ran. `make inspect` is the Makefile's
shortcut for the current model and config. Setting up `<Tab>` on task names is a
one-off worth doing early: see [Tab completion](#tab-completion).

## 2. What the build contains

### The module map

| Address                                                                                 | What it is                                                                                                            |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `run[<model>,<config>]`                                                                 | The full ONNX pipeline for the model named by `-Dvta.onnx.file`, built for `<config>`. What the root Makefile drives. |
| `default`                                                                               | Alias for the `run[...]` instance selected by the current `-Dvta.onnx.file` / `-Dvta.config.file`, i.e. `run[]`.      |
| `examples.onnx[<model>,<config>]`                                                       | The same pipeline, for models under `examples/onnx/`: every model is a cross key, not only the selected one.          |
| `examples.ir[<fixture>,<config>]`                                                       | Compile and simulate a hand-written VTA IR fixture from `examples/vta_ir/`.                                           |
| `targets[<config>,<board>]`                                                             | The Vivado build: IP packaging, project, synthesis, XSA, Vitis platform.                                              |
| `modules.hardware`, `modules.simulator[<config>]`, `modules.compiler`, `modules.fpga.*` | The per-module tasks the pipelines are built from.                                                                    |

The cross keys are read from the filesystem, so **adding a config to `config/`,
a model to `examples/onnx/`, a fixture to `examples/vta_ir/` or a board JSON to
`modules/fpga/boards/` adds its cross entries with no build-file edit.**

```bash
./mill resolve "run[_,_]"                # the selected model, every config
./mill resolve "examples.onnx[_,_]"      # every (model, config) pair
./mill resolve "targets[_,_]"            # every (config, board) pair
```

### Global options

Anything that is not a cross axis is passed as a JVM property. These also supply
the default cross keys, which is why they matter before you run anything:

| Property                | Default                     | Effect                                                                                                    |
| ----------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------- |
| `vta.onnx.file`         | `examples/onnx/lenet5.onnx` | Model run by `run[...]` / `default`; its basename is the model cross key. The root Makefile overrides it. |
| `vta.config.file`       | `vta_config.json`           | Config for the flat, non-crossed tasks, and the config segment of `run[]` / `targets[]`.                  |
| `vta.board.name`        | `zcu104`                    | Board for the pipeline tasks that need one, and the board segment of `targets[]`.                         |
| `vta.ddr.base`          | `0x0`                       | DDR base address baked into the baremetal codegen. Must match the board.                                  |
| `vta.verilator.threads` | `4`                         | Verilator build threads. Changing it invalidates the `vsim` tasks.                                        |
| `vta.vivado.jobs`       | `4`                         | Vivado parallel jobs. A runtime flag: changing it does not invalidate anything.                           |
| `vta.xil.out`           | unset                       | Shallow root for the heavy Vivado/Vitis trees (`<dir>/<config>/<board>/`), for Windows long-path limits.  |

#### Pinning options between runs

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

## 3. Running a model

### The pipeline tasks

This is the everyday loop, and the pipeline that the root Makefile drives. All
of these tasks exist on `run[...]`, on `default`, and on
`examples.onnx[...]` alike, since the three share the same traits.

| Task                        | Kind    | What it does                                                                          |
| --------------------------- | ------- | ------------------------------------------------------------------------------------- |
| `compile`                   | cached  | `nn_compiler` + `vta_compiler`: the `.bin` / `.csv` streams.                          |
| `reference`                 | cached  | The ONNX reference: `input_nn.bin` (network input) + `reference.bin` (golden output). |
| `fsim`                      | command | Run the functional (C++) simulator, then check against the reference.                 |
| `vsim`                      | command | Run the Verilated RTL simulator, then check against the reference.                    |
| `check`                     | command | Run both simulators on the same cached compile and byte-compare their outputs.        |
| `layerDumps`                | cached  | Per-layer fsim goldens (`--dump-layers`), shared by the debug and post-synth flows.   |
| `genBaremetal`              | cached  | The baremetal PS headers (`nn_exec_plan.h`, `nn_ddr_map.h`, ...). No Vivado needed.   |
| `genBaremetalDebug`         | cached  | `genBaremetal` plus the debug maps, wired to `layerDumps`.                            |
| `sdCard` / `sdCardDebug`    | command | Stage the `.bin` set (and, for `Debug`, the goldens) for a FAT32 card.                |
| `createVitisProject`        | command | Add this model's app components to the (config, board) Vitis workspace.               |
| `createVitisProjectFromXsa` | command | Same, from an XSA you already have, with no Vivado run.                               |
| `addVitisDebugApps`         | command | Add the on-board isolation apps (`run_nn_debug`, `run_nn_cpu_debug`).                 |
| `runUart`                   | command | Drive a board running `run_nn_uart` over a serial port and check its output.          |
| `postSynth`                 | command | Gate-level xsim check of a layer subset against the fsim goldens.                     |

The first four are the loop:

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

Being commands, `fsim` and `vsim` forward their trailing arguments to the
simulator binary: `--layer 3 --verbose` for either, `--no-timeout --trace` for
`vsim`. Neither re-invokes the Python compiler itself. Both depend on `compile`,
which re-runs only when the model, the config or the compiler sources actually
change.

The remaining tasks in the table are the baremetal and FPGA flows, covered in
[chapter 4](#4-fpga-vitis-and-baremetal).

### `run` or `examples.onnx`: which entry point

Both expose the same tasks, both are crossed on **(model, config)**, and both
cache every pair independently under `out/.../<model>/<config>/`. They differ
only in **which model keys exist**:

- `run[<model>,<config>]` has **one model key at a time**, the basename of
  `-Dvta.onnx.file`, which may point anywhere on disk. Use it (or the Makefile)
  for a single model you iterate on, including one outside `examples/onnx/`.
  `run[_,_]` therefore means "the selected model, every config".
- `examples.onnx[<model>,<config>]` has **one key per model** in
  `examples/onnx/`, all addressable at once. Use it to move between example
  models, or to build several in one command:

  ```bash
  ./mill "examples.onnx[_,vta_config].fsim"   # every model, one config
  ./mill "examples.onnx[_,_].fsim"            # every (model, config) pair
  ```

Switching model needs nothing beyond the flag: the model key is a watched value
(`BuildCtx.watchValue` in `build.mill`), so the daemon re-instantiates the build
and re-lists the axis. Each model keeps its own directory, so switching back
finds the previous results cached:

```bash
./mill -Dvta.onnx.file=path/to/other.onnx "run[].fsim"
```

Everything below is written with `examples.onnx[lenet5,vta_config]`; substitute
`run[lenet5,vta_config]` (plus `-Dvta.onnx.file=<path>`), or just `default`, to
get the Makefile's behaviour.

### Raw VTA IR fixtures

The fixtures in `examples/vta_ir/` are VTA IR already, so they skip
`nn_compiler` and with it the ONNX reference, which is why they have no golden to
check against. `check` is the substitute: it runs both simulators on the same
cached compile and byte-compares their outputs, failing the build on any
difference.

```bash
./mill "examples.ir[matmul_16x16,vta_config].compile"
./mill "examples.ir[matmul_16x16,vta_config].check"   # fsim vs vsim, byte for byte
./mill "examples.ir[_,_].check"                       # every fixture, every config
```

`fsim` and `vsim` exist here too, and run the fixture's single layer. The root
Makefile exposes only the sweep, as `make check_irs`.

The baremetal, Vitis and post-synthesis tasks are deliberately absent from
`examples.ir`: they consume full-network artifacts, namely `dependency.csv`,
which only `nn_compiler` writes, and `input_nn.bin`, which only the ONNX
reference writes.

## 4. FPGA, Vitis and baremetal

This chapter is one chain, and you can enter it at any point: synthesize a
bitstream, build the Vitis apps that drive it, stage the data the board reads,
and check the result layer by layer. The Vivado steps live on
`targets[<config>,<board>]`; everything that depends on a compiled model lives on
the pipeline modules of the previous chapter.

### FPGA targets

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

### Vitis workspaces

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

#### From an existing XSA

When a suitable XSA already exists (a colleague's build, a GUI-made design, an
archived handoff), `createVitisProjectFromXsa` skips synthesis entirely and
hands the file straight to `create_vitis_workspace.py`:

```bash
./mill "examples.onnx[lenet5,vta_config].createVitisProjectFromXsa" \
    --xsa vta_zcu104.xsa --runner run_nn --data-loader elf
```

Nothing in this command's task graph reaches Vivado. Mill fills in the workspace
directory (`build/vitis/<model>_<config>`, kept across runs so the platform is
not rebuilt), this model's `genBaremetal` output and the app-name prefix; repeat
any of those flags to override them, since the script keeps the last occurrence.
Everything else is yours, including `--cpu` for a non-ZynqMP board (it defaults
to `psu_cortexa53_0`).

> [!warning]
> The XSA is _not_ checked against the active config: a bitstream synthesized for
> a different block size than the compiled binaries will run and produce garbage.

### SD-card file sets

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

### On-board isolation debugging

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

### Post-synthesis gate-level check

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

## 5. Working on a single module

Below the pipelines, each module exposes its own tasks. These are what you want
when working on one component in isolation, without dragging a whole model
through it. The commands below are the common ones; for the full set, and for
what each module actually does, read its own README:
[compiler](modules/compiler/README.md), [simulator](modules/simulator/README.md),
[hardware](modules/hardware/README.md), [fpga](modules/fpga/README.md)
([synthesis](modules/fpga/synthesis/README.md),
[software](modules/fpga/software/README.md)).

### Per-module tasks

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

### Flat pass-through commands

Beside the crossed modules sits a set of flat, uncached commands
(`modules.hardware.emitVta*`, `modules.fpga.synthesis.*`,
`modules.fpga.software.*`). Each takes its config from the global
`-Dvta.config.file` and forwards its arguments to the underlying Scala or Python
entry point. They are escape hatches for reaching a tool with unusual arguments:
prefer the crossed tasks above, which cache. The module READMEs linked above
document the ones each owns, with the arguments they accept.

### The per-module Makefiles

`examples/Makefile`, `modules/simulator/Makefile` and
`modules/fpga/software/Makefile` predate the Mill build and remain available for
standalone use outside it. They select their config through their own `CONFIG`
variables rather than `-Dvta.config.file`; see `make help` in each.

## 6. Reference

### Where the outputs land

Every task writes into its own directory under `out/`, mirroring the task path:

```text
out/run/<model>/<config>/               compile.dest/, fsim.dest/, vsim.dest/, ...
out/examples/onnx/<model>/<config>/     same set, one per (model, config)
out/examples/ir/<fixture>/<config>/     compile.dest/, check.dest/{fsim,vsim}/
out/targets/<config>/<board>/           ipRepo.dest/, fpgaProject.dest/, synth.dest/, ...
out/modules/simulator/<config>/         fsimBinary.dest/, vsimBinary.dest/
```

The C++/Verilator simulator is built once per config and cached, and the FPGA
bitstream once per (config, board) pair, so switching config, board, model, or
adding a new example model does not rebuild everything.

Clean selectively rather than deleting `out/`, since `clean` takes the same
selectors as any other task:

```bash
./mill clean "run[lenet5,vta_config]"    # one (model, config) instance
./mill clean "run[]"                     # the same, for the current defaults
./mill clean "run[_,_]"                  # the selected model, every config
./mill clean run                         # everything under out/run, all models
./mill clean "targets[vta_config,zcu104]"
```

Vivado and Vitis trees that are not worth content-hashing live outside `out/`,
under `build/` (or under `-Dvta.xil.out` when set).

### Tab completion

`./mill <Tab>` completes task names and shows each task's description (its
`/** ... */` doc comment in the `*.mill` files). The hook calls
`mill --tab-complete` on every keypress, so the candidates always match the
current build. Enable it once per clone, with your clone's path:

```bash
# bash / zsh - add to ~/.bashrc or ~/.zshrc
source /path/to/standalone-vta/tools/completions/mill-completion.sh

# fish - add to ~/.config/fish/config.fish
source /path/to/standalone-vta/tools/completions/mill-completion.fish
```

Restart the shell (or re-`source` the rc file) and press `<Tab>` after `./mill`.

With [`fzf`](https://github.com/junegunn/fzf) (it ships in the pixi env),
`<Tab>` opens a drill-down picker instead of a plain menu: descriptions show in a
preview pane, `<Tab>` descends into a module's sub-tasks (`examples` -> `onnx` ->
model -> config), `<Left>` goes back up, `<Enter>` accepts. Without fzf it falls
back to a single-line menu. Both need the `mill-fzf-level` helper, so keep the
three `tools/completions/` files together.

Mill also ships an installer for the bash/zsh hook:
`./mill mill.tabcomplete/install`.

A task shows a description only if it has a doc comment.
