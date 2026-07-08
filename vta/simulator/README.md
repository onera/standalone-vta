# Functional Simulator (C++)

C++ simulator for the VTA. Reads the binary streams produced by the compiler
(`compiler_output/`) and runs them through one of two backends:

- **`build/fsim`** - pure C++ functional model. Fast, no RTL involved.
- **`build/vsim`** - Verilator-driven RTL simulation of `VTAShell`. Slower,
  cycle-accurate. Selected by binary, not by a runtime flag.

Both binaries share the same source tree and the same CLI surface; the
backend is baked in at compile time. By default each binary runs the full NN
graph; pass `--layer N` to instead run a single VTA IR.

## Build & run

```bash
# C++ functional backend
make fsim                  # build + run build/fsim on the full NN

# Verilator RTL backend
make vsim                  # build + run build/vsim on the full NN

# Canned vsim configurations (wipe the cached archive, rebuild, run)
make vsim-debug            # enable firtool debug printfs (e.g. [Compute] start gemm)
make vsim-hazard           # randomize init values + unique X-state for hazard hunting

# Build only
make build/fsim
make build/vsim
```

Single-layer runs are just an additional `--layer N` flag:

```bash
./build/fsim  --layer 3
./build/vsim  --layer 3 --no-timeout
```

The Verilator archive (`build/verilated/VVTAShell/VTest__ALL.a`) is the slow
build step (~20 s) and is cached. The RTL sources for it come from
`../cycle_accurate_simulator/build/emitted/vta-sim-shell/`, which must be
emitted first:

```bash
cd ../cycle_accurate_simulator && ./mill emitVtaSimConfig
```

Override the VTA configuration: `make CONFIG=../../../config/vta_config_8b.json ...`
(the configs live at the repository root, three levels up from here).

## CLI

```
Usage: ./build/{fsim,vsim} [OPTIONS]

Mode:
  --layer N             Run only VTA IR layer N (default: full NN graph)

Runtime:
  --verbose             Print the layer result to stdout (single-layer only)
  --output DIR          Directory for every file the simulator writes
                        (final_output, dumps, traces, log). Defaults to the
                        compile-time output dir when omitted.
  --comp-dir DIR        Directory the compiler outputs are read from. Defaults
                        to the compile-time compiler-output dir when omitted.
  --dump-layers         Dump per-layer raw input/output to the output dir

vsim only:
  --dram-base 0xADDR    Shift every DRAM buffer by this base
  --no-hw-reset         Reset the VTA only on the first layer
  --trace               Per-layer waveform to <output-dir>/trace_<layer>.{fst,vcd}
  --sv-log PATH         Capture every SystemVerilog $display/$fwrite line in PATH
                        and silence them on the console; C++ stdout is untouched
  --timeout-cycles N    Abort after N RTL cycles (default: 500000)
  --no-timeout          Disable the cycle timeout
```

By default the SV `$display`/`$fwrite` stream prints to stderr - handy when
exploring, noisy when piping. Pass `--sv-log PATH` to route it into a file:

```bash
# from this directory; RUNTIME_FLAGS is forwarded to ./build/vsim
make vsim RUNTIME_FLAGS='--sv-log sv.log'
#   sv.log   <- SystemVerilog printfs; C++ stdout stays on the console
```

`examples/`'s `vsim_inference` target pins `RUNTIME_FLAGS=--no-timeout` on its
sub-make, so extra runtime flags cannot be passed through it - run `make vsim`
here instead (that target redirects C++ stdout to
`log_output/tsim_report.txt`).

When the archive is built with the firtool debug printf layer enabled
(`make vsim-debug` or `VTA_VERIF_DEBUG=1 make build/vsim`), the binary
auto-defaults `--sv-log` to `simulators_output/verilator.log` so the firehose
doesn't flood the console. The path is printed at the end of the run
(`SystemVerilog log written to …`, right after the final-output line), and
`--sv-log PATH` still overrides the destination.

## Toolchain

| Variable | Default | Effect |
| -------- | ------- | ------ |
| `CXX`    | `$CXX` from the environment, else `g++` | C++ compiler used for every object here and for the final link. |

Inside the pixi environment `CXX` is exported and points at the environment's
toolchain (`x86_64-conda-linux-gnu-c++`), so no override is needed. Outside
pixi it falls back to whatever `g++` is on `PATH`.

Two things to know:

- **Do not set `CC` to select the compiler.** In a conda/pixi environment `CC`
  is the *C* driver and cannot link libstdc++. Everything here is C++, so the
  knob is `CXX`.
- **The Verilated archive does not follow `CXX`.** `verilator --build` compiles
  `VTest__ALL.a` with *its own* configured compiler (`verilator --getenv CXX`),
  and `build/vsim` links that archive against objects built with `$(CXX)`. If
  the two disagree, the resulting binary mixes compilers. Building inside pixi
  keeps them the same; check with:

  ```bash
  verilator --getenv CXX      # what builds the archive
  echo $CXX                   # what builds everything else
  ```

When `CONDA_PREFIX` is set, the Makefile adds that environment's include and
library search paths (the conda toolchain compiles against its own sysroot and
would otherwise not find `zlib.h`). Only search paths are taken, never the
environment's `CPPFLAGS` / `CXXFLAGS`: those carry `-O2 -DNDEBUG` and
`-march=nocona`, which would disable asserts and change float codegen. fsim and
vsim must agree bit-for-bit, so codegen flags stay under this Makefile's
control.

## Compile-time knobs

These are `+define+`s baked into the Verilated archive. Toggle them and wipe
the archive - make doesn't track them as a dependency:

```bash
rm -f build/verilated/VVTAShell/VTest__ALL.a
```

| Variable           | Default                            | Effect                                                                           |
| ------------------ | ---------------------------------- | -------------------------------------------------------------------------------- |
| `VTA_VERIF_DEBUG`  | `0`                                | When `1`, enables firtool debug printfs (e.g. `[Compute] start gemm`).           |
| `TRACE_FORMAT`     | `fst`                              | Set to `vcd` for VCD output.                                                     |
| `RANDOMIZE`        | `0`                                | Shorthand for `RANDOMIZE_REG=1 RANDOMIZE_MEM=1`.                                 |
| `RANDOMIZE_REG`    | `$(RANDOMIZE)`                     | Randomize register init values.                                                  |
| `RANDOMIZE_MEM`    | `$(RANDOMIZE)`                     | Randomize memory init values.                                                    |
| `NONDET_RANDOM`    | `0`                                | When `1`, use `$urandom` instead of the deterministic `$random` for init values. |
| `VERILATOR_XFLAGS` | `--x-assign fast --x-initial fast` | Use `--x-assign unique --x-initial unique` to seed X-state from Verilator's RNG. |
| `SIM_THREADS`      | `8`                                | Verilator simulation threads.                                                    |

The SystemVerilog assertion layer (emitted by firtool alongside the design) is
always compiled in. Any assertion failure prints `%Error … Assertion failed`
and stops the simulation. No flag needed.

## Recipes

### Run a NN to completion against the RTL

```bash
cd ../cycle_accurate_simulator && ./mill emitVtaSimConfig && cd -
make vsim
```

### Run a single layer

```bash
./build/fsim --layer 3                     # C++ backend
./build/vsim --layer 3 --no-timeout        # RTL backend
```

### Dump a waveform

```bash
make build/vsim
./build/vsim --no-timeout --trace
gtkwave ../../../simulators_output/trace_<layer>.fst
```

One trace file is written per layer to `simulators_output/`. Switch to VCD
by rebuilding the archive with `TRACE_FORMAT=vcd`.

### See what the RTL is doing each cycle

```bash
make vsim-debug
```

(Equivalent to `rm -f build/verilated/VVTAShell/VTest__ALL.a && VTA_VERIF_DEBUG=1 make vsim`.)
You'll get `[Compute] start gemm`, `[Compute] done alu`, etc., for every op.

### Hunt uninitialised-state hazards

```bash
make vsim-hazard
```

(Equivalent to a clean rebuild with `RANDOMIZE=1 NONDET_RANDOM=1
VERILATOR_XFLAGS='--x-assign unique --x-initial unique'`.) If any assertion
catches the design reading uninitialised state, this is the path that
surfaces it.

### Exercise the HW address datapath at a non-zero DRAM base

```bash
./build/vsim --no-timeout --dram-base 0x10000000
```

### Per-layer raw input/output dumps

```bash
./build/fsim --dump-layers       # writes simulators_output/input<layer>.bin / output<layer>.bin
```

## Clean

```bash
make clean   # delete every file under build/
```
