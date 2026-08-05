# host-golden fixtures

Golden snapshot of the Scala `fpga.host.GenNnBaremetal` port, used as regression
fixtures for the host-golden exporter tests. The `.bin` compiler outputs are
**not committed** — they are regenerated on demand from the committed ONNX models
by a Mill task (see below), so only the small text golden lives here.

## Layout

Each committed `<case>/` holds:

- `config.json` — the VTA hardware config used (copied from `config/<name>.json`).
- `CASE.txt` — `case=`, `config=` (original name), `ddr_base=`, `model=`.
- `gen/` — expected output of `GenNnBaremetal.generate(...)` (default mode):
  `vta_hw_config.h`, `nn_ddr_map.h`, `nn_exec_plan.h`, `load_nn_static.tcl`,
  `load_nn.tcl`, `load_input.tcl`, `nn_bin_data.S`, `nn_vta_sections.ld`.
- `gen-debug/` — `--emit-cpu-check` mode: `nn_debug_map.h`, `nn_cpu_debug_map.h`
  (raw), `nn_bin_data.S`, `nn_vta_sections.ld` (canonicalized).
- `gen-sd/` — `--emit-sd-manifest` mode: `nn_sd_manifest.h` (raw) and
  `staged_files.txt` (the sorted relative listing of the staged `sd_card/` set).

There is **no** committed `compiler_output/`.

## The compiler_output binaries (generated, not committed)

The `compiler_output/*.bin`/`*.csv` are produced by the Mill task
`modules.fpga.software.test.goldenOutputs`, which compiles each committed ONNX model with
the Python VTA compiler (`modules/compiler`, run in the pixi env) into a gitignored
generated-resources root. That root is added to the test classpath as
`host-golden-bin/<case>/compiler_output/...`; `GoldenSupport` reads the golden
from `host-golden/` and the binaries from `host-golden-bin/`.

Determinism: the compiler fills placeholder accumulator buffers (e.g. MaxPool,
no real bias) with `np.random`; `modules/fpga/test-tools/seed_runner.py` seeds numpy
so the output is byte-stable. `goldenOutputs` is cached on its inputs (ONNX,
configs, compiler sources, and the test-tools), so
Python only re-runs when one of those changes.

Env to (re)generate: `pixi shell` at the repo root, then `execstack -c` the
onnxruntime `.so` on hardened kernels (see the project guide). `./mill
modules.fpga.software.test` runs the task automatically.

## Cases

Full cross product of the two committed models and two committed configs:

- `lenet5-default` — `lenet5.onnx`, `vta_config.json`, DDR base `0x0`.
- `lenet5-w8b` — `lenet5.onnx`, `vta_w8b.json`, DDR base `0x10000000` (exercises
  non-zero base-address arithmetic across every emitter).
- `qyolo-default` — `qyolo_pattern.onnx`, `vta_config.json`, DDR base `0x0`.
- `qyolo-w8b` — `qyolo_pattern.onnx`, `vta_w8b.json`, DDR base `0x10000000`.

`gemm-test` is a separate, self-contained case (a seeded in-Scala 16x16 GEMM, no
compiler_output) holding only `init_dram.h` for `GenInitDramTestGemmTest`.

## Canonicalization

In the loader/asm artifacts (`nn_bin_data.S`, `load_*.tcl`, `nn_vta_sections.ld`)
the absolute compiler-output path is replaced by the token `@COMP_DIR@` so the
golden is checkout-independent. The tests apply the same replacement to their
runtime output before comparing.

## Regenerating the golden

The golden is a snapshot of the port. To re-baseline after an intentional change
to `GenNnBaremetal`'s output (or to the compiler), run:

```
./mill modules.fpga.software.test.regenHostGolden
```

This recompiles the binaries (via `goldenOutputs`) and rewrites `gen/`,
`gen-debug/`, `gen-sd/`, `CASE.txt`, and `config.json` for every case. Review the
diff and commit. (`init_dram.h` for `gemm-test` is re-baselined separately via
`./mill modules.fpga.software.genInitDramTestGemm --outdir <gemm-test dir> --filename init_dram.h`.)
