# Measurement campaigns

A campaign is a list of *legs*. A leg is one (model, config, board, app opt
level, compiler flags) cell measured on a board. `vta_campaign` expands a
campaign file into legs and runs each one as a short sequence of mill tasks
around two `tools/uart_bench.py` sessions. It keeps each leg's status, so an
interrupted campaign resumes where it stopped.

```sh
pixi run campaign --help
pixi run campaign-test                          # unit tests, no board needed
```

## Quick start

```sh
C=tools/campaign/campaigns/config-matrix.toml

pixi run campaign prepare  $C                   # compile + fsim every pair
pixi run campaign stage-sd $C                   # SD data into the host card trees
# copy <cards>/<board>/<model>_<config>/ to each board's SD card
pixi run campaign run $C --boards zcu104 &      # the two boards in parallel,
pixi run campaign run $C --boards vck190        # one process each
pixi run campaign status $C
```

Every command takes `--dry-run`, which prints the commands instead of running
them.

## One leg

Every mill call carries the leg's properties: `vta.board.name`, `vta.sd.dir`,
`vta.app.opt`, `vta.uart.baud`, optionally `vta.jtag.cable` and `vta.hw.dir`,
`vta.ddr.base=0x1000000` for SD-loader legs (the base `stage-sd` stages the
cards at, which their streams embed), then the correctness and variant flags.
The steps, in order:

| step | command | what it does |
|---|---|---|
| build | `buildVitisApp --runner run_nn_uart --data-loader <loader>` | the app ELF, on the synthesized hardware or the prebuilt `vta.hw.dir` export |
| flash | `flashBoard ...`, under the JTAG lock | bitstream + FSBL on ZynqMP, PDI on Versal |
| info | `show runInfo --snapshot-dir <leg dir>` | copies the input out of `out/`, and reports the ELF and hardware hashes and every `vta.*` option in effect |
| capture | `uart_bench --runs 1 --save-output <leg dir>/out.bin` | one inference's raw output |
| check | `checkBoardOutput --output <leg dir>/out.bin` | de-tiles it and compares it byte for byte with the cached fsim run (`layerDumps`). A mismatch ends the leg before any measurement. |
| measure | `uart_bench --runs N [--reuse-input]`, per mode | `<results>/<tag>-<mode>-<timestamp>/` plus its `experiment.json` |

Each step can be run by hand with the same `./mill` command, which the
`--dry-run` output prints.

Some design notes:

- **The UART sessions run outside mill.** mill runs one command at a time per
  `out/`, so a benchmark run inside mill would make the other board's process
  wait for hours. The mill steps queue behind each other. They are short once
  `prepare` has run, which builds every hardware platform (synthesis
  included) up front.
- **The JTAG lock is still taken around flashing.** Two checkouts or worktrees
  have one `out/` each but share one hw_server, so the lock is one file for
  the whole host (`jtag_lock` in `settings.toml`).
- **`experiment.json`** holds `run` (runInfo as mill reported it) and
  `campaign` (which leg, mode and flags, from which commit).
- **An `OK` counts only for the options it ran with.** When a flag, a default
  or a persisted option changes, the leg shows as `stale` and runs again.
- **Options persisted with `./mill configure` apply to every leg.** The tool
  prints a warning listing them, then runs and records the legs with them.
  Run `./mill configure --reset` first when a baseline must be all-off.
- **The port is checked before use.** ttyUSB numbering shifts when a board is
  unplugged. A board with a `uart_usb_model` must report it as its udev
  `ID_MODEL`, and no other board's port may.

## Where things go

| what | where |
|---|---|
| measurements | `<results>/<tag>-<mode>-<timestamp>/`: `runs.csv`, `steps.csv`, `stats.md`, `raw.log`, `meta.json` (from `uart_bench`), `experiment.json` |
| leg status | `<work>/status/<campaign>/<tag>.json` |
| input copies, captured output | `<work>/legs/<campaign>/<tag>/` |
| logs | `<work>/logs/<tag>_<step>.log` |

`<work>`, `<results>`, `<cards>` and `<archive>` come from `settings.toml`.
That file also holds each board's UART port, baud rate, USB model and JTAG
cable. Pass your own file with `--settings`: it only needs the keys it
changes, and it may add boards. To override a single port, use
`--port vck190=/dev/ttyUSB0`.

## Campaign files

```toml
name = "opt-sweep"          # status and record key
n_runs = 30                 # uart_bench --runs
mode = "reuse"              # reuse | upload | both
apply_correctness = true    # default

[variants]                  # named flag sets; "base" (no flag) is implicit
directconv = ["-Dvta.direct.conv=true"]

[[group]]                   # cartesian product of the lists below
configs = ["vta_config"]
boards = ["vck190"]
models = ["resnet18"]
app_opts = ["O0"]
variants = ["base", "directconv"]   # default ["base"]
loader = "elf"                      # elf | sd
tag = "OPT-{variant}-{model}-{config}-{board}"
# Optional prebuilt hardware export (-Dvta.hw.dir), holding vta_<board>.xsa
# and its .bit or .pdi. Without it, mill synthesizes (cached). {archive} is
# the settings' archive path. Per config: hw_dirs = { cfg = "..." }
hw_dir = "{archive}/vta_config__{board}__axi128"
```

Legs nest config > board > model > app opt > variant, so legs that share a
bitstream run back to back. Tags must be unique within a campaign. A leg whose
`hw_dir` has no XSA is skipped as `NO_HW`. An SD-loader leg with no staged
card data is skipped as `NO_SD_DATA`.

`correctness.toml` lists the flags each (model, config) pair needs to compute
the right answer, with the evidence. Every leg gets them before its own variant
flags.

The campaigns in `campaigns/` are the ones behind the ISORC 27 results. They
also serve as examples.

## Other commands

- **`prepare`** builds, up front, the hardware platform of every (config,
  board), synthesizing where there is no `hw_dir`. It then compiles and
  simulates (`layerDumps`) every distinct (model, config, flags), so a compile
  failure surfaces before hours of board time. mill keeps one cached run per
  (model, config). A pair measured with several flag sets therefore
  recompiles and re-simulates in its legs' check step, which takes minutes.
- **`stage-sd`** runs `sdCard` with `-Dvta.ddr.base=0x1000000` for the
  SD-loader legs. It copies the result to `<cards>/<board>/<model>_<config>/`
  and parks any previous copy as `.superseded-*`.
- **`sim-timing`** times the fsim/vsim binaries alone, after building
  everything untimed. The CSV goes in `<work>/sim-timing.csv`.

## The seed

The reference input is drawn from the `vta.ref.seed` build option (default
`1234`). It is a `Task.Input` of `reference`, so the input changes only when
the seed does, whatever flag recompiles the model. Before this, `reference`
re-ran on every recompile and drew a new random input. Two invocations could
then leave the fsim golden, the board input and `reference` describing
different inputs. That defect caused the earlier false exclusion of
qyolo/`vta_config_8b`.
