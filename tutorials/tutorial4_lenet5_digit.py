import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="lenet5 over UART")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # lenet5 over UART — draw a digit

    Draw a digit, send it to the FPGA, get a **10-way class score** vector
    back. Config and target board are selectable below; the model is fixed
    to `examples/onnx/lenet5.onnx` (a classic LeNet-5: two 5x5-conv+maxpool
    stages then three 1x1 "fully-connected-as-conv" stages, entirely
    ONNX Runtime QOperator INT8). For the detection-style qyolo family
    (RGB photo in, per-class score *grid* out), see
    `tutorial3_qyolo_uart.py` instead — this notebook is specific to
    single-channel, whole-image classifiers.

    **Driven entirely through Mill**, same as tutorial3: `./mill
    -Dvta.board.name=<board> examples.onnx[lenet5,<config>].runUart` (plus
    `.buildVitisApp` / `.flashBoard`) run here as subprocesses.

    **No board? Run the same drawing through a simulator.** *1 - Connection*
    offers four back ends: the board over UART, `fsim`, `vsim` and plain
    `onnxruntime`. lenet5 is small enough that both simulators are quick.
    See *2b*.

    **32x32 vs. the graph's declared 28x28 input.** The classic LeNet-5 takes
    a 32x32 image; `lenet5.onnx`'s graph input is declared `[1,1,28,28]`
    instead - but its first conv has `pads=[2,2,2,2]`, i.e. it *implicitly*
    zero-pads that 28x28 input out to 32x32 before convolving. So the two are
    the same network, and the canvas below draws directly at the model's real
    28x28 - no separate crop needed.
    """)
    return


@app.cell
def _():
    # --- paths & imports -------------------------------------------------------
    import sys
    import time
    from pathlib import Path

    import numpy as np

    REPO_ROOT = Path(__file__).resolve().parent.parent
    HOST_DIR = REPO_ROOT / "modules/fpga/software/host"
    if str(HOST_DIR) not in sys.path:
        sys.path.insert(0, str(HOST_DIR))

    import board_discovery as bd
    import model_io as mio
    from digit_canvas import DigitCanvasWidget

    ONNX_PATH = REPO_ROOT / "examples/onnx/lenet5.onnx"
    MILL = REPO_ROOT / "mill"
    SCRATCH_DIR = REPO_ROOT / "out" / "lenet5_notebook"
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    return (
        DigitCanvasWidget,
        MILL,
        ONNX_PATH,
        REPO_ROOT,
        SCRATCH_DIR,
        bd,
        mio,
        np,
        time,
    )


@app.cell
def _(REPO_ROOT, bd, mo):
    # --- 0 - Configuration: model is fixed to lenet5.onnx, pick config/board --
    def _dd(options, preferred, label):
        opts = options or ["(none found)"]
        value = preferred if preferred in opts else opts[0]
        return mo.ui.dropdown(options=opts, value=value, label=label)

    config_dd = _dd(bd.list_configs(REPO_ROOT), "vta_config", "VTA config (config/*.json)")
    board_dd = _dd(bd.list_boards(REPO_ROOT), "zcu104", "Target board (modules/fpga/boards/*.json)")
    loader_dd = _dd(bd.list_loaders(), "sd", "Model binaries loader mode")
    mo.md(
        f"""
    ### 0 - Configuration

    Model: **`lenet5.onnx`** (fixed - this notebook is lenet5-specific)

    {mo.hstack([config_dd, board_dd,loader_dd], justify="start", gap=2)}
            """
    )
    return board_dd, config_dd, loader_dd


@app.cell
def _(ONNX_PATH, REPO_ROOT, config_dd, mio, mo):
    # --- 0b - Model spec: introspect lenet5.onnx (+ config for block size) ----
    config_path = REPO_ROOT / "config" / f"{config_dd.value}.json"

    _err = None
    spec = None
    if not ONNX_PATH.exists():
        _err = f"**{ONNX_PATH}** does not exist."
    else:
        try:
            spec = mio.load_model_spec(ONNX_PATH, config_path)
        except Exception as e:
            _err = f"Could not read {ONNX_PATH.name}'s shapes: `{e}`"
        else:
            if not spec.is_grayscale_image_input:
                _err = (
                    f"**{ONNX_PATH.name}** takes `[1,{spec.in_c},{spec.in_h},{spec.in_w}]`, "
                    "not the square single-channel input this notebook expects. "
                    "Has the bundled lenet5.onnx changed shape?"
                )

    mo.stop(_err is not None, mo.md(f"⚠️ {_err}"))
    mo.md(
        f"**{spec.name}** — in `{spec.in_c}×{spec.in_h}×{spec.in_w}` (grayscale, "
        f"q={spec.input_scale:g}·x+{spec.input_zp}) → "
        f"out `{spec.out_c}×{spec.out_h}×{spec.out_w}` "
        f"(q={spec.output_scale:g}·x+{spec.output_zp}), VTA block {spec.block}, "
        f"{len(spec.class_names)} classes (digits 0-9)"
    )
    return (spec,)


@app.cell
def _(REPO_ROOT, bd, board_dd, mo):
    port = mo.ui.text(value=bd.default_port(REPO_ROOT, board_dd.value), label="Serial port")
    # Rates from the board JSON's uart_baud_choices; the first is the default.
    _bauds = bd.baud_choices(REPO_ROOT, board_dd.value)
    baud = mo.ui.dropdown(
        options={str(_b): _b for _b in _bauds},
        value=str(_bauds[0]),
        label="UART baud",
    )
    source = mo.ui.radio(
        options={
            "FPGA board (mill runUart over UART)": "board",
            "fsim - functional C++ simulator (mill runFsim)": "fsim",
            "vsim - Verilated RTL simulator (mill runVsim)": "vsim",
            "Local onnxruntime (no board needed)": "local",
        },
        value="FPGA board (mill runUart over UART)",
        label="Where to run the model",
    )
    mo.md(
        f"""
    ### 1 - Connection

    {mo.hstack([source, port, baud], justify="start", gap=2)}

    Port and baud apply to the **board** leg only - `fsim`, `vsim` and
    `onnxruntime` all run on this host and ignore them (see *2b*).

    The baud rate drives **both** ends through one Mill option
    (`-Dvta.uart.baud`): the firmware's `VTA_UART_BAUD` and the host script's
    `--baud`. Changing it therefore needs a **rebuild + reflash** (section 2)
    before the next run - otherwise the two ends disagree and the host reads
    noise instead of the banner. At 115200 the two payload transfers dominate
    a round-trip, and the rate divides them almost exactly, so raising it is
    the cheapest speed-up available short of moving the payload off UART
    entirely.
            """
    )
    return baud, port, source


@app.cell
def _(MILL, baud, board_dd, config_dd, loader_dd, mo, spec):
    build_btn = mo.ui.run_button(label=f"Build + flash {board_dd.value} (mill)")
    _build_cmd = (
        f"pixi run {MILL} -Dvta.board.name={board_dd.value} "
        f"-Dvta.uart.baud={baud.value} "
        f"'examples.onnx[{spec.name},{config_dd.value}].buildVitisApp' "
        f"--runner run_nn_uart --dataLoader {loader_dd.value}"
    )
    _flash_cmd = (
        f"pixi run {MILL} -Dvta.board.name={board_dd.value} "
        f"-Dvta.uart.baud={baud.value} "
        f"'examples.onnx[{spec.name},{config_dd.value}].flashBoard' "
        f"--runner run_nn_uart --dataLoader {loader_dd.value}"
    )
    mo.md(
        f"""
    ### 2 - (optional) put `run_nn_uart` on the board

    Same two Mill tasks as tutorial3 - **`buildVitisApp`** then
    **`flashBoard`** - just addressed at the `lenet5` cross key instead of
    `qyolo`. An `_sd` app needs its static model data on the SD card as
    `1:/{spec.name}/` (`./mill ...sdCard` stages the files, copying them to
    the card is still a manual step).

    ```sh
    {_build_cmd}
    {_flash_cmd}
    ```

    {build_btn}
            """
    )
    return (build_btn,)


@app.cell
def _(MILL, REPO_ROOT, baud, board_dd, build_btn, config_dd, loader_dd, mo, spec):
    mo.stop(not build_btn.value, mo.md("*idle — press the button above to build + flash*"))
    import subprocess

    def _run(cmd, timeout):
        return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)

    with mo.status.spinner(title=f"mill buildVitisApp ({board_dd.value}) …"):
        _cp1 = _run(
            ["pixi", "run", str(MILL), f"-Dvta.board.name={board_dd.value}",
             f"-Dvta.uart.baud={baud.value}",
             f"examples.onnx[{spec.name},{config_dd.value}].buildVitisApp",
             "--runner", "run_nn_uart", "--dataLoader", loader_dd.value],
            timeout=600,
        )
    _out1 = "\n".join((_cp1.stdout + _cp1.stderr).splitlines()[-20:])
    if _cp1.returncode != 0:
        mo.stop(
            True,
            mo.md(f"**buildVitisApp exit {_cp1.returncode}** ❌\n\n```\n{_out1}\n```"),
        )

    with mo.status.spinner(title=f"mill flashBoard ({board_dd.value}) …"):
        _cp2 = _run(
            ["pixi", "run", str(MILL), f"-Dvta.board.name={board_dd.value}",
             f"-Dvta.uart.baud={baud.value}",
             f"examples.onnx[{spec.name},{config_dd.value}].flashBoard",
             "--runner", "run_nn_uart", "--dataLoader", loader_dd.value],
            timeout=300,
        )
    _out2 = "\n".join((_cp2.stdout + _cp2.stderr).splitlines()[-20:])
    mo.md(
        f"**buildVitisApp** ✅\n```\n{_out1}\n```\n"
        f"**flashBoard exit {_cp2.returncode}** "
        f"{'✅' if _cp2.returncode == 0 else '❌'} — give an `_sd` loader ~90 s "
        f"to finish before the first inference.\n\n```\n{_out2}\n```"
    )
    return


@app.cell
def _(MILL, config_dd, mo, spec):
    # --- 2b - the no-board legs: fsim and vsim --------------------------------
    sim_timeout = mo.ui.number(
        start=60, stop=86400, step=60, value=1800,
        label="simulator timeout (s)",
    )
    _fsim_cmd = (
        f"pixi run {MILL} 'examples.onnx[{spec.name},{config_dd.value}].runFsim' "
        f"--input <digit.bin> --output <out.bin>"
    )
    _vsim_cmd = (
        f"pixi run {MILL} 'examples.onnx[{spec.name},{config_dd.value}].runVsim' "
        f"--input <digit.bin> --output <out.bin>"
    )
    mo.md(
        f"""
    ### 2b - (no board) run it in a simulator instead

    Same compiled `{spec.name}` binaries, same INT8 buffers, three different
    things executing them - so a disagreement localises itself:

    | leg | what runs the network | catches |
    | --- | --- | --- |
    | `fsim` | `modules/simulator` C++ behavioural model | a **compiler** bug (bad tiling, bad DRAM map, bad ISA) |
    | `vsim` | the real Chisel RTL, Verilated | an **RTL** bug: fsim-vs-vsim is exactly what `./mill ...check` compares |
    | board | the same RTL on silicon | a **platform** bug (DDR base, loader, UART framing) |

    Two Mill tasks, `runFsim` / `runVsim`, do for the simulators what
    `runUart` does for the board: they take *your* drawing instead of the
    random `input_nn.bin` the ONNX reference generates.

    ```sh
    {_fsim_cmd}
    {_vsim_cmd}
    ```

    The payload is the same flat INT8 `[H*W][C]` buffer every back end takes
    - for lenet5 just the {spec.in_h}x{spec.in_w} canvas, one byte a pixel;
    what comes back is the flat NCHW INT8 tensor `onnxruntime` returns,
    already un-blocked. ▶ below builds the simulator and compiles the
    model if either is stale, so the first run is the slowest - `vsim`'s also
    Verilates the RTL.

    Even the cycle-accurate leg finishes in a reasonable time here (unlike
    tutorial3's 640x640 qyolo), though still far slower than `fsim`. The RTL
    cycle timeout is off for these runs, so the bound below is the only one.

    {sim_timeout}
            """
    )
    return (sim_timeout,)


@app.cell
def _(DigitCanvasWidget, mo, spec):
    canvas = mo.ui.anywidget(DigitCanvasWidget(grid_size=spec.in_h))
    mo.md(
        f"""
    ### 3 - Draw a digit

    Drag to draw, shift-drag (or right-drag) to erase, **Clear** to reset.
    Draw big and centered - {spec.name} was trained on centred MNIST digits.
    The canvas is {spec.in_h}×{spec.in_w}, the model's native input
    resolution, so what you draw is exactly what gets sent - no crop or
    resize in between.

    {canvas}
            """
    )
    return (canvas,)


@app.cell
def _(canvas, mio, np, spec):
    # Canvas is already spec.in_h x spec.in_w - feed it straight through.
    model_input = np.array(canvas.value["pixels"], dtype=np.uint8).reshape(spec.in_h, spec.in_w)
    payload = mio.board_input_bytes(model_input, size=spec.in_h, input_zp=spec.input_zp, in_c=1)
    return model_input, payload


@app.cell
def _(mo):
    run_btn = mo.ui.run_button(label="▶ Run inference")
    mo.md(f"### 4 - Run\n\n{run_btn}  &nbsp; *(re-press after redrawing or changing the configuration)*")
    return (run_btn,)


@app.cell
def _(ONNX_PATH, mo, spec):
    # onnxruntime session, built once and reused across runs.
    import onnxruntime as _ort

    trunc_sess = _ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    mo.md(f"onnxruntime session ready — {spec.name}: ✅")
    return (trunc_sess,)


@app.cell
def _(
    MILL,
    REPO_ROOT,
    SCRATCH_DIR,
    baud,
    board_dd,
    config_dd,
    mio,
    mo,
    model_input,
    payload,
    port,
    run_btn,
    sim_timeout,
    source,
    spec,
    time,
    trunc_sess,
):
    import subprocess as _sp

    mo.stop(not run_btn.value, mo.md("*press ▶ Run inference*"))

    _t0 = time.time()
    if source.value == "board":
        in_path = SCRATCH_DIR / "input.bin"
        out_path = SCRATCH_DIR / "output.bin"
        in_path.write_bytes(payload)
        if out_path.exists():
            out_path.unlink()
        _cmd = [
            "pixi", "run", str(MILL), f"-Dvta.board.name={board_dd.value}",
            f"-Dvta.uart.baud={baud.value}",
            f"examples.onnx[{spec.name},{config_dd.value}].runUart",
            "--port", port.value,
            "--input", str(in_path),
            "--output", str(out_path),
            "--banner-timeout", "240",
            "--ready-timeout", "180",
        ]
        with mo.status.spinner(
            title=f"mill runUart on {board_dd.value} "
            f"(first run after flashing ≈ 90 s for the SD load)…"
        ):
            _cp = _sp.run(_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=420)
        # runUart checks against the random input's golden, so it exits 1 on a
        # real drawing; the output file is what counts.
        mo.stop(
            not out_path.exists() or out_path.stat().st_size == 0,
            mo.md(
                f"❌ **mill runUart** produced no output (exit {_cp.returncode}).\n\n"
                f"```\n{(_cp.stdout + _cp.stderr)[-3000:]}\n```"
            ),
        )
        raw_out = out_path.read_bytes()
        probs = mio.detile_output(
            raw_out, spec.out_c, spec.out_h, spec.out_w, spec.block,
            spec.output_scale, spec.output_zp,
        )
        run_info = (
            f"mill runUart ({board_dd.value}, {config_dd.value}) · "
            f"got {len(raw_out)} B · {time.time() - _t0:.1f} s"
        )
    elif source.value in ("fsim", "vsim"):
        _task = "runFsim" if source.value == "fsim" else "runVsim"
        in_path = SCRATCH_DIR / "input.bin"
        out_path = SCRATCH_DIR / f"{source.value}_output.bin"
        in_path.write_bytes(payload)
        if out_path.exists():
            out_path.unlink()
        _cmd = [
            "pixi", "run", str(MILL),
            f"examples.onnx[{spec.name},{config_dd.value}].{_task}",
            "--input", str(in_path),
            "--output", str(out_path),
        ]
        with mo.status.spinner(
            title=f"mill {_task} ({config_dd.value}) - builds the simulator "
            f"and compiles the model first if either is stale…"
        ):
            _cp = _sp.run(
                _cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                timeout=sim_timeout.value,
            )
        # No golden check here, so a non-zero exit is a real failure.
        mo.stop(
            not out_path.exists() or out_path.stat().st_size == 0,
            mo.md(
                f"❌ **mill {_task}** produced no output (exit {_cp.returncode}).\n\n"
                f"```\n{(_cp.stdout + _cp.stderr)[-3000:]}\n```"
            ),
        )
        raw_out = out_path.read_bytes()
        # No de-tile: the simulators un-block before writing.
        probs = mio.probs_from_sim_output(
            raw_out, spec.out_c, spec.out_h, spec.out_w,
            spec.output_scale, spec.output_zp,
        )
        run_info = (
            f"mill {_task} ({config_dd.value}) · "
            f"got {len(raw_out)} B · {time.time() - _t0:.1f} s"
        )
    else:
        _out = trunc_sess.run(
            None,
            {trunc_sess.get_inputs()[0].name:
             mio.onnx_input_nchw(model_input, spec.in_h, spec.input_zp, in_c=1)},
        )[0]
        probs = mio.probs_from_onnx_output(
            _out, spec.out_c, spec.out_h, spec.out_w, spec.output_scale, spec.output_zp
        )
        run_info = f"local onnxruntime ({spec.name}) · {time.time() - _t0:.2f} s"

    mo.md(f"✅ **{run_info}**")
    return probs, run_info


@app.cell
def _(mio, mo, probs, run_info, spec):
    import matplotlib.pyplot as plt

    scores = mio.global_class_scores(probs)  # (10,) - max over the 1x1 grid
    pred = int(scores.argmax())

    fig, ax = plt.subplots(figsize=(6, 3.2))
    colors = ["steelblue"] * 10
    colors[pred] = "crimson"
    ax.bar(spec.class_names, scores, color=colors)
    ax.set_ylim(0, 1)
    ax.set_ylabel("score")
    ax.set_title(f"prediction: {spec.class_names[pred]}  (p={scores[pred]:.3f})")
    fig.tight_layout()

    mo.vstack(
        [
            mo.md(f"### 5 - Result &nbsp; · &nbsp; *{run_info}*"),
            fig,
            mo.ui.table(
                [
                    {"digit": spec.class_names[i], "score": round(float(scores[i]), 3)}
                    for i in scores.argsort()[::-1]
                ],
                selection=None,
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
