import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Qyolo-NAS over UART")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def intro(mo):
    mo.vstack([
        mo.md(
            r"""
    # Quantized YOLO-NAS on the VTA

    **One picture. Four ways to run it. They should all agree.**

    Pick a model and a photo, then send that same photo down the pipeline: first
    to plain `onnxruntime` on this machine, then to a simulator, then to the real
    hardware simulated gate by gate, and finally to the FPGA itself.

    Each step is one notch closer to the silicon, and each has its own \u25b6.
    Run one, or run all four. Section 6 lays the results side by side.

    The point is the *disagreement*. All four should produce the same numbers, so
    whichever step is the first to differ tells you where the fault lives:

    | if it first breaks at | the problem is in |
    | --- | --- |
    | 3 &nbsp; `onnxruntime` | your image, or the quantisation |
    | 4a `fsim` | the VTA **compiler** |
    | 4b `vsim` | the **hardware design** |
    | 5 &nbsp; the board | the **platform**: memory, loader, cabling |
            """
        ),
        mo.accordion({
            "What the model actually is": mo.md(
                r"""
    `examples/onnx/qyolo.onnx` is YOLO-NAS-S cut off at `head3/cls_pred`. Its
    only output is an `int8[1, 80, 20, 20]` tensor: 80 COCO class scores on a
    20x20 grid.

    The box-regression branch and the two finer heads are **not** in the
    subgraph, so there is no box tensor. The most any leg here can say is
    *"this grid cell fired for class c"* - which is why results are drawn as a
    heatmap with coarse cell-boxes rather than tight bounding boxes. The green
    boxes in section 3 come from the *full* model, for comparison only.

    Any other model you pick is treated the same way: RGB image in, class grid
    out. If it is not shaped like that, section 1 says so and stops rather than
    guessing. For `lenet5.onnx` (grayscale, draw-a-digit) use
    `tutorial4_lenet5_digit.py` instead.
                """
            ),
            "How it is driven": mo.md(
                r"""
    Every \u25b6 shells out to the same Mill task you would type by hand -
    `./mill examples.onnx[<model>,<config>].runFsim` / `.runVsim` / `.runUart`,
    plus `buildVitisApp` and `flashBoard` for the board. Nothing is
    reimplemented here, so the notebook cannot drift from the CLI.
                """
            ),
        }),
    ])
    return


@app.cell
def _():
    # --- paths & imports -------------------------------------------------------
    import json
    import re
    import subprocess
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

    FULL_ONNX = REPO_ROOT / "examples/onnx/quantise_extract/yolo_nas_s.onnx"
    MILL = REPO_ROOT / "mill"
    SCRATCH_DIR = REPO_ROOT / "out" / "qyolo_notebook"
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    return (
        FULL_ONNX,
        MILL,
        Path,
        REPO_ROOT,
        SCRATCH_DIR,
        bd,
        json,
        mio,
        np,
        re,
        subprocess,
        time,
    )


@app.cell
def config(REPO_ROOT, SCRATCH_DIR, bd, json, mo):
    UI_STATE = SCRATCH_DIR / "ui_state.json"

    def _remembered():
        """The selection from last time, so re-running an upstream cell (or
        reopening the notebook) does not silently snap everything back."""
        try:
            return json.loads(UI_STATE.read_text())
        except (OSError, ValueError):
            return {}

    _last = _remembered()

    def _dd(options, preferred, label, key):
        opts = options or ["(none found)"]
        _want = _last.get(key, preferred)
        if _want not in opts:
            _want = preferred if preferred in opts else opts[0]
        return mo.ui.dropdown(options=opts, value=_want, label=label)

    model_dd = _dd(bd.list_models(REPO_ROOT), "qyolo.onnx", "Model", "model")
    config_dd = _dd(bd.list_configs(REPO_ROOT), "vta_config", "VTA config", "config")
    board_dd = _dd(bd.list_boards(REPO_ROOT), "zcu104", "Board", "board")
    loader_dd = _dd(bd.list_loaders(), "sd", "Model data loader", "loader")
    mo.vstack([
        mo.md(
            f"""
    ## 1 - What to run

    {mo.hstack([model_dd, config_dd, board_dd, loader_dd], justify="start", gap=2)}
            """
        ),
        mo.accordion({
            "About these choices": mo.md(
                """
    These lists are simply what the repo contains. Whether a given combination
    has actually been compiled and flashed is checked below, and again when you
    press a \u25b6.

    **Model data loader** decides how the model\'s weights reach the board.
    `sd` reads them from the SD card as the application starts, while `elf` and
    `tcl` push them across the JTAG cable beforehand. Either way it is paid once,
    when the application loads - section 5 shows what it comes to.

    Your selection here, and the photo in *2*, are remembered between runs.
                """
            ),
        }),
    ])
    return UI_STATE, board_dd, config_dd, loader_dd, model_dd


@app.cell(hide_code=True)
def remember_config(UI_STATE, board_dd, config_dd, json, loader_dd, model_dd):
    # Separate cell so the config cell does not read its own output back.
    UI_STATE.write_text(
        json.dumps(
            {
                "model": model_dd.value,
                "config": config_dd.value,
                "board": board_dd.value,
                "loader": loader_dd.value,
            },
            indent=1,
        )
    )
    None
    return


@app.cell
def model_spec(REPO_ROOT, config_dd, mio, mo, model_dd):
    # --- 1b - introspect the chosen .onnx (+ config for block size) ------------
    onnx_path = REPO_ROOT / "examples/onnx" / model_dd.value
    config_path = REPO_ROOT / "config" / f"{config_dd.value}.json"

    _err = None
    spec = None
    if not onnx_path.exists():
        _err = f"**{onnx_path}** does not exist."
    else:
        try:
            spec = mio.load_model_spec(onnx_path, config_path)
        except Exception as e:
            _err = f"Could not read {onnx_path.name}\'s shapes: `{e}`"
        else:
            if not spec.is_rgb_image_input:
                _err = (
                    f"**{model_dd.value}** expects `[1,{spec.in_c},{spec.in_h},"
                    f"{spec.in_w}]`, which is not a square colour photo. This "
                    "notebook only drives photo-in / class-grid-out models. Pick "
                    "another model above, or use `tutorial4_lenet5_digit.py` for "
                    "`lenet5.onnx`."
                )

    mo.stop(_err is not None, mo.md(f"\u26a0\ufe0f {_err}"))
    mo.vstack([
        mo.md(
            f"""
    **{spec.name}** \u2014 a {spec.in_h}\u00d7{spec.in_w} colour photo in,
    **{len(spec.class_names)} class scores** on a
    {spec.out_h}\u00d7{spec.out_w} grid out
    {"(COCO)" if spec.out_c == 80 else "(generic labels, not COCO)"}.
    Each grid cell covers {spec.stride}\u00d7{spec.stride} pixels of the input.
            """
        ),
        mo.accordion({
            "Numbers": mo.md(
                f"""
    | | |
    | --- | --- |
    | input | `int8[1, {spec.in_c}, {spec.in_h}, {spec.in_w}]`, quantised as {spec.input_scale:g}\u00b7x + {spec.input_zp} |
    | output | `int8[1, {spec.out_c}, {spec.out_h}, {spec.out_w}]`, quantised as {spec.output_scale:g}\u00b7x + {spec.output_zp} |
    | grid stride | {spec.stride} px |
    | VTA block | {spec.block} (from `{config_dd.value}.json`) |

    The VTA block size decides how the output tensor is tiled in memory, which
    is why the board returns more bytes than the tensor strictly needs.
                """
            ),
        }),
    ])
    return (spec,)


@app.cell
def image_pick(mo):
    img_upload = mo.ui.file(
        filetypes=[".jpg", ".jpeg", ".png", ".bmp", ".webp"],
        kind="button",
        label="Upload an image",
    )
    sample_url = mo.ui.text(
        value="https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg",
        label="\u2026or fetch a URL",
        full_width=True,
    )
    fetch_btn = mo.ui.run_button(label="Fetch URL")
    mo.md(
        f"""
    ## 2 - Pick a photo

    Whatever you choose here is squared off, quantised, and handed to every back
    end below unchanged - so they are all answering the same question.

    {img_upload}

    {mo.hstack([sample_url, fetch_btn], justify="start", gap=1)}
            """
    )
    return fetch_btn, img_upload, sample_url


@app.cell
def image_decode(SCRATCH_DIR, fetch_btn, img_upload, mo, np, sample_url):
    import io
    import urllib.request

    from PIL import Image

    # A run_button is only True for the run it triggered, so the photo is
    # cached on disk and read back when no button was pressed.
    IMAGE_CACHE = SCRATCH_DIR / "source_image.bin"
    IMAGE_CACHE_NAME = SCRATCH_DIR / "source_image.name"

    _raw = None
    _src_name = None
    _from_cache = False
    _uploaded = list(img_upload.value or [])
    if _uploaded:
        _raw = _uploaded[0].contents
        _src_name = _uploaded[0].name
    elif fetch_btn.value:
        with mo.status.spinner(title=f"GET {sample_url.value}"):
            _req = urllib.request.Request(
                sample_url.value, headers={"User-Agent": "marimo"}
            )
            _raw = urllib.request.urlopen(_req, timeout=20).read()
            _src_name = sample_url.value.rsplit("/", 1)[-1] or "downloaded image"

    if _raw is not None:
        IMAGE_CACHE.write_bytes(_raw)
        IMAGE_CACHE_NAME.write_text(_src_name)
    elif IMAGE_CACHE.exists() and IMAGE_CACHE.stat().st_size:
        _raw = IMAGE_CACHE.read_bytes()
        _src_name = (
            IMAGE_CACHE_NAME.read_text() if IMAGE_CACHE_NAME.exists() else "cached image"
        )
        _from_cache = True

    mo.stop(_raw is None, mo.md("\u2b06\ufe0f *upload a file or fetch a URL to continue*"))

    # PIL sniffs the format from the bytes, so the cache needs no extension.
    image_rgb = np.asarray(Image.open(io.BytesIO(_raw)).convert("RGB"))
    src_name = _src_name
    mo.md(
        f"**{src_name}** \u2014 {image_rgb.shape[1]}\u00d7{image_rgb.shape[0]} px"
        + (" &nbsp;\u00b7&nbsp; \U0001f4be *restored from cache*" if _from_cache else "")
    )
    return (image_rgb,)


@app.cell
def image_payload(image_rgb, mio, mo, spec):
    from PIL import Image as _Image

    lb_img, lb = mio.letterbox_image(image_rgb, size=spec.in_h)
    payload = mio.board_input_bytes(lb_img, size=spec.in_h, input_zp=spec.input_zp)
    mo.hstack(
        [
            mo.image(_Image.fromarray(image_rgb), caption="original", width=320),
            mo.image(
                _Image.fromarray(lb_img),
                caption=f"letterboxed {spec.in_h}×{spec.in_w} (what {spec.name} sees)",
                width=320,
            ),
        ],
        justify="start",
    )
    return lb, lb_img, payload


@app.cell
def thresholds(mo):
    # Shared by every results panel; they re-filter, never re-run.
    conf_cell = mo.ui.slider(
        0.05, 0.9, value=0.30, step=0.01, label="cell threshold", show_value=True
    )
    conf_ref = mo.ui.slider(
        0.1, 0.9, value=0.35, step=0.01, label="reference score threshold",
        show_value=True,
    )
    merge = mo.ui.switch(value=True, label="merge adjacent cells")
    mo.md(
        f"""
    ### Display thresholds

    {mo.hstack([conf_cell, merge, conf_ref], justify="start", gap=2)}
            """
    )
    return conf_cell, conf_ref, merge


@app.cell
def render_helpers(conf_cell, conf_ref, image_rgb, lb, merge, mio, mo, spec):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    # One drawing routine for every back end, so the panels are comparable.

    def _draw_boxes(ax, dets, color):
        for d in dets:
            x0, y0, x1, y1 = d.box_xyxy
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=2, ec=color))
            ax.text(
                x0, max(y0 - 3, 8), f"{d.name} {d.score:.2f}", color="black",
                fontsize=8, bbox=dict(fc=color, ec="none", pad=1),
            )

    def _grid_extent():
        # maps the letterboxed output grid back onto the original image's axes
        return [
            -lb.pad_x / lb.scale, (spec.in_w - lb.pad_x) / lb.scale,
            (spec.in_h - lb.pad_y) / lb.scale, -lb.pad_y / lb.scale,
        ]

    def leg_detections(probs):
        """Coarse per-cell boxes at the shared threshold."""
        return mio.grid_detections(
            probs, lb, spec.class_names, spec.stride,
            conf=conf_cell.value, merge=merge.value,
        )

    def leg_rows(dets, kind):
        return [
            {
                "src": kind, "class": d.name, "score": round(d.score, 3),
                "cells": d.n_cells or "",
                "box xyxy": [round(v) for v in d.box_xyxy.tolist()],
            }
            for d in dets
        ]

    def leg_heatmap(ax, probs, title, vmax=None):
        """Class-score heatmap over the photo, plus this leg\'s cell boxes."""
        heat = probs.max(0)
        ax.imshow(image_rgb)
        hm = ax.imshow(
            heat, extent=_grid_extent(), alpha=0.45, cmap="turbo",
            vmin=0, vmax=vmax if vmax else max(0.15, float(heat.max())),
        )
        ax.set_xlim(0, image_rgb.shape[1])
        ax.set_ylim(image_rgb.shape[0], 0)
        _draw_boxes(ax, leg_detections(probs), "orange")
        ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        return hm

    def leg_panel(probs, info, label):
        """A whole section\'s results block: heatmap, top-8 bars, detection table."""
        if probs is None:
            return mo.md(info or f"*{label} \u2014 not run yet.*")
        dets = leg_detections(probs)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
        hm = leg_heatmap(axes[0], probs, f"{label} \u2014 {len(dets)} cell-box(es)")
        fig.colorbar(hm, ax=axes[0], fraction=0.046, pad=0.04, label="max class prob")
        top = mio.topk_classes(probs, spec.class_names, k=8)
        axes[1].barh([t[1] for t in top][::-1], [t[2] for t in top][::-1], color="steelblue")
        axes[1].set_title("top-8 class score (max over grid)", fontsize=10)
        axes[1].set_xlim(0, 1)
        fig.tight_layout()
        return mo.vstack(
            [
                fig,
                mo.md(f"`{info}` &nbsp;\u00b7&nbsp; grid max prob = **{probs.max():.3f}**"),
                mo.ui.table(leg_rows(dets, label), selection=None),
            ]
        )

    def ref_box_panel(dets_all):
        """The full yolo_nas_s reference: real NMS-decoded boxes. Section 3 only -
        it is the one thing the host reference produces that no other leg can."""
        dets = [d for d in dets_all if d.score >= conf_ref.value]
        fig, ax = plt.subplots(figsize=(5.6, 5.6))
        ax.imshow(image_rgb)
        _draw_boxes(ax, dets, "lime")
        ax.set_title(f"reference yolo_nas_s \u2014 {len(dets)} box(es)", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        return mo.vstack([fig, mo.ui.table(leg_rows(dets, "reference"), selection=None)])

    return leg_detections, leg_heatmap, leg_panel, leg_rows, plt, ref_box_panel


@app.cell(hide_code=True)
def leg_cache(SCRATCH_DIR, config_dd, mio, spec, time):
    # Each leg keeps its raw output next to the payload, keyed by config: it
    # survives a re-run of the cell, and a mill cache hit does not rewrite it.
    def leg_out_path(kind):
        return SCRATCH_DIR / f"{kind}_{config_dd.value}_output.bin"

    def decode_sim(raw):
        """fsim/vsim un-block before writing, so the tensor is already NCHW."""
        return mio.probs_from_sim_output(
            raw, spec.out_c, spec.out_h, spec.out_w, spec.output_scale, spec.output_zp
        )

    def decode_board(raw):
        """The board returns the tensor still blocked at VTA block size."""
        return mio.detile_output(
            raw, spec.out_c, spec.out_h, spec.out_w, spec.block,
            spec.output_scale, spec.output_zp,
        )

    def cached_result(kind, decode):
        """The last output on disk for this leg+config, or (None, None)."""
        out_bin = leg_out_path(kind)
        if not out_bin.exists() or not out_bin.stat().st_size:
            return None, None
        when = time.strftime("%H:%M", time.localtime(out_bin.stat().st_mtime))
        return decode(out_bin.read_bytes()), (
            f"\U0001f4be cached \u2014 {out_bin.name} from {when} "
            "(press \u25b6 to re-run)"
        )

    return cached_result, decode_board, decode_sim, leg_out_path


@app.cell
def ref_header(mo, spec):
    ref_btn = mo.ui.run_button(label="\u25b6 Run onnxruntime")
    mo.vstack([
        mo.md(
            f"""
    ## 3 - On this computer

    Run **{spec.name}** with `onnxruntime`, right here. No VTA involved at all:
    no compiler, no hardware, no cable. Takes about a second, and whatever it
    says is what every later step is trying to reproduce.

    It also runs the *complete* YOLO-NAS-S, which still has its box branch, to
    draw real boxes for comparison.

    {ref_btn}
            """
        ),
        mo.accordion({
            "Why two models": mo.md(
                """
    The model on the board is truncated - it emits class scores on a grid and
    nothing else, so it cannot draw a box. The full `yolo_nas_s.onnx` can, and
    its green boxes are here purely to give your eye something to check the
    heatmap against. It is never compared numerically.
                """
            ),
        }),
    ])
    return (ref_btn,)


@app.cell
def ref_sessions(FULL_ONNX, mo, spec):
    # onnxruntime sessions, built once. The yolo_nas_s.onnx reference only
    # applies to an 80-class (COCO) output.
    import onnxruntime as _ort

    trunc_sess = _ort.InferenceSession(str(spec.path), providers=["CPUExecutionProvider"])
    full_sess = (
        _ort.InferenceSession(str(FULL_ONNX), providers=["CPUExecutionProvider"])
        if FULL_ONNX.exists() and spec.out_c == 80
        else None
    )
    mo.md(
        f"onnxruntime sessions ready — {spec.name}: ✅ · "
        f"reference `yolo_nas_s`: "
        f"{'✅' if full_sess else '❌ (file missing or model is not COCO-80-class)'}"
    )
    return full_sess, trunc_sess


@app.cell
def ref_run(full_sess, lb, lb_img, mio, ref_btn, spec, time, trunc_sess):
    # `None` rather than mo.stop(), so later sections can render "not run yet".
    probs_local = None
    info_local = None
    ref_dets_all = []

    if ref_btn.value:
        _t0 = time.time()
        _out = trunc_sess.run(
            None,
            {trunc_sess.get_inputs()[0].name:
             mio.onnx_input_nchw(lb_img, spec.in_h, spec.input_zp)},
        )[0]
        probs_local = mio.probs_from_onnx_output(
            _out, spec.out_c, spec.out_h, spec.out_w, spec.output_scale, spec.output_zp
        )
        info_local = f"onnxruntime ({spec.name}) \u00b7 {time.time() - _t0:.2f} s"
        # Low threshold; the panel re-filters with the slider.
        if full_sess is not None:
            ref_dets_all = mio.reference_detections(
                full_sess, lb_img, lb, mio.COCO_NAMES, conf=0.05
            )
    return info_local, probs_local, ref_dets_all


@app.cell
def ref_results(
    info_local,
    leg_panel,
    mo,
    probs_local,
    ref_box_panel,
    ref_dets_all,
):
    mo.vstack(
        [
            leg_panel(probs_local, info_local, "onnxruntime"),
            mo.md("---\n#### full `yolo_nas_s` \u2014 what a complete model sees")
            if ref_dets_all else mo.md(""),
            ref_box_panel(ref_dets_all) if ref_dets_all else mo.md(""),
        ]
    )
    return


@app.cell
def sim_header(mo):
    sim_timeout = mo.ui.number(
        start=60, stop=86400, step=60, value=1800, label="simulator timeout (s)"
    )
    mo.vstack([
        mo.md(
            f"""
    ## 4 - Without a board

    From here on the photo really is compiled for the VTA. The model, the
    instructions and the data are exactly what the FPGA would run - only the
    thing *executing* them changes.

    Two steps, cheap first: **4a** runs it in software, **4b** runs the actual
    hardware design. Give up on a run with the bound below.

    {sim_timeout}
            """
        ),
        mo.accordion({
            "How your photo gets in": mo.md(
                """
    Left alone, the VTA examples run on a random `input_nn.bin` generated
    alongside the ONNX reference. `runFsim` and `runVsim` take an `--input`
    instead, which is how your picture reaches the simulators - the same way
    `runUart` feeds the board.
                """
            ),
        }),
    ])
    return (sim_timeout,)


@app.cell(hide_code=True)
def sim_helper(
    MILL,
    REPO_ROOT,
    SCRATCH_DIR,
    cached_result,
    config_dd,
    decode_sim,
    leg_out_path,
    mo,
    payload,
    sim_timeout,
    spec,
    subprocess,
    time,
):
    def sim_leg(task, pressed):
        """Drive one `mill runFsim`/`runVsim` leg over the shared payload.

        Returns (probs, info). Un-pressed falls back to the cached output; on
        failure probs is None and info carries the log tail, so the section
        renders the error where the result would have been.
        """
        out_bin = leg_out_path(task)
        if not pressed:
            return cached_result(task, decode_sim)

        _t0 = time.time()
        in_bin = SCRATCH_DIR / "input.bin"
        in_bin.write_bytes(payload)
        stamp = out_bin.stat().st_mtime if out_bin.exists() else None
        cmd = [
            "pixi", "run", str(MILL),
            f"examples.onnx[{spec.name},{config_dd.value}].{task}",
            "--input", str(in_bin), "--output", str(out_bin),
        ]
        with mo.status.spinner(
            title=f"mill {task} ({config_dd.value}) - builds the simulator and "
            "compiles the model first if either is stale\u2026"
        ):
            cp = subprocess.run(
                cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                timeout=sim_timeout.value,
            )
        fresh = out_bin.exists() and out_bin.stat().st_mtime != stamp
        # A non-zero exit with nothing written is a real failure.
        if not out_bin.exists() or not out_bin.stat().st_size or (
            not fresh and cp.returncode != 0
        ):
            return None, (
                f"\u274c **mill {task}** produced no output (exit {cp.returncode}).\n\n"
                f"```\n{(cp.stdout + cp.stderr)[-3000:]}\n```"
            )
        raw = out_bin.read_bytes()
        return decode_sim(raw), (
            f"mill {task} ({config_dd.value}) \u00b7 {len(raw)} B \u00b7 "
            f"{time.time() - _t0:.1f} s"
            + ("" if fresh else " \u00b7 mill cache hit, output unchanged")
        )

    return (sim_leg,)


@app.cell
def fsim_header(MILL, config_dd, mo, spec):
    fsim_btn = mo.ui.run_button(label="\u25b6 Run fsim")
    mo.vstack([
        mo.md(
            f"""
    ### 4a - in software

    A C++ model of the VTA executes the compiled instructions. It gets the right
    answers without pretending to be hardware, so it is fast, and it is the
    first place your result can go wrong.

    If this disagrees with section 3, the **compiler** is at fault. Start here.

    {fsim_btn}
            """
        ),
        mo.accordion({
            "Command": mo.md(
                f"""
    ```sh
    pixi run {MILL} \'examples.onnx[{spec.name},{config_dd.value}].runFsim\' \\
      --input <image.bin> --output <out.bin>
    ```

    Builds the simulator and compiles the model first if either is stale, so the
    first run is much slower than the rest.
                """
            ),
        }),
    ])
    return (fsim_btn,)


@app.cell(hide_code=True)
def fsim_run(fsim_btn, sim_leg):
    probs_fsim, info_fsim = sim_leg("runFsim", fsim_btn.value)
    return info_fsim, probs_fsim


@app.cell
def fsim_results(info_fsim, leg_panel, probs_fsim):
    leg_panel(probs_fsim, info_fsim, "fsim")
    return


@app.cell
def vsim_header(MILL, config_dd, mo, spec):
    vsim_btn = mo.ui.run_button(label="\u25b6 Run vsim")
    mo.vstack([
        mo.md(
            f"""
    ### 4b - the real hardware design

    The same instructions, this time through the actual circuit description,
    simulated signal by signal. Everything 4a checked is checked again, plus the
    hardware itself.

    If 4a agreed and this does not, the **hardware design** is at fault.

    \u26a0\ufe0f Slow - it simulates every clock tick of a
    {spec.in_h}\u00d7{spec.in_w} network. Minutes at best. Try 4a first.

    {vsim_btn}
            """
        ),
        mo.accordion({
            "Command": mo.md(
                f"""
    ```sh
    pixi run {MILL} \'examples.onnx[{spec.name},{config_dd.value}].runVsim\' \\
      --input <image.bin> --output <out.bin>
    ```

    `./mill ...check` is exactly an fsim-against-vsim diff, which is why a
    difference appearing here and not in 4a points at the RTL.
                """
            ),
        }),
    ])
    return (vsim_btn,)


@app.cell(hide_code=True)
def vsim_run(sim_leg, vsim_btn):
    probs_vsim, info_vsim = sim_leg("runVsim", vsim_btn.value)
    return info_vsim, probs_vsim


@app.cell
def vsim_results(info_vsim, leg_panel, probs_vsim):
    leg_panel(probs_vsim, info_vsim, "vsim")
    return


@app.cell
def board_header(mo):
    mo.vstack([
        mo.md(
            """
    ## 5 - On the board

    The same design again, this time on the actual chip, with the photo travelling
    over the serial cable. Everything the simulators checked is checked again -
    what is new is the board itself: its memory, how the model got there, and the
    cable.

    If 4b agreed and this does not, the fault is in the **platform**, not in the
    design.
            """
        ),
        mo.accordion({
            "Choosing the serial port": mo.md(
                """
    The list below is the USB serial adapters currently attached. A Xilinx cable
    usually offers several - the board's console is normally the one named in its
    board file, which is preselected. Plugged the board in just now? Press
    **Rescan**.
                """
            ),
            "Changing the baud rate": mo.md(
                """
    The speed is compiled into *both* ends, so picking a new one here does
    nothing until you rebuild and reflash (5a). Otherwise the two ends disagree
    and the host reads noise instead of the start-up banner.
                """
            ),
        }),
    ])
    return


@app.cell(hide_code=True)
def port_rescan(mo):
    # A run_button does not re-run its own cell, so the scan lives here.
    rescan_btn = mo.ui.run_button(label="\U0001f504 Rescan ports")
    return (rescan_btn,)


@app.cell
def board_conn(REPO_ROOT, bd, board_dd, mo, rescan_btn):
    rescan_btn.value  # pressing Rescan re-runs this cell

    def detect_ports():
        """Attached USB serial adapters, as {label: device}.

        Motherboard /dev/ttyS* ports have no USB vendor id and are dropped - there
        are 32 of them here and none is ever the board.
        """
        try:
            from serial.tools import list_ports
        except ImportError:
            return {}
        found = {}
        for p in sorted(list_ports.comports(), key=lambda p: p.device):
            if p.vid is None:
                continue
            # description is often "JTAG+3Serial - JTAG+3Serial"; keep one half
            _d = (p.description or "").split(" - ")[0].strip()
            who = " ".join(
                x for x in (p.manufacturer, _d) if x and x not in ("n/a", "")
            ) or "unknown"
            found[f"{p.device} \u2014 {who}"] = p.device
        return found

    _detected = detect_ports()
    _want = bd.default_port(REPO_ROOT, board_dd.value)
    if not _detected:
        # No device found (or no pyserial): fall back to the board JSON default.
        _detected = {f"{_want} \u2014 not detected": _want}
    _pick = next((k for k, v in _detected.items() if v == _want), list(_detected)[0])
    port = mo.ui.dropdown(options=_detected, value=_pick, label="Serial port")

    _bauds = bd.baud_choices(REPO_ROOT, board_dd.value)
    baud = mo.ui.dropdown(
        options={str(_b): _b for _b in _bauds},
        value=str(_bauds[0]),
        label="UART baud",
    )
    mo.hstack([port, baud, rescan_btn], justify="start", gap=2)
    return baud, port


@app.cell
def board_estimate(
    Path,
    REPO_ROOT,
    baud,
    config_dd,
    loader_dd,
    mo,
    payload,
    re,
    spec,
):
    def _fmt_dur(seconds):
        if seconds < 90:
            return f"{seconds:.0f} s"
        return f"{int(seconds // 60)} min {int(seconds % 60):02d} s"

    def _fmt_size(n):
        return f"{n / 1e6:.2f} MB" if n >= 1e6 else f"{n / 1e3:.1f} kB"

    def uart_out_bytes():
        """What the board sends back: the output tensor still block-tiled, so
        ceil(H*W/B) x ceil(C/B) blocks of B*B - bigger than the tensor itself."""
        _n = spec.out_h * spec.out_w
        return (
            -(-_n // spec.block) * -(-spec.out_c // spec.block) * spec.block ** 2
        )

    def loader_static_bytes():
        """Static model data the elf/tcl loaders move, summed from the file list in
        the generated load_nn.tcl. None when the model has not been built yet."""
        _tcl = (
            REPO_ROOT / "out/examples/onnx" / spec.name / config_dd.value
            / "genBaremetal.dest" / "load_nn.tcl"
        )
        if not _tcl.exists():
            return None
        _seen = {Path(m) for m in re.findall(r"\{([^}]+\.bin)\}", _tcl.read_text())}
        return sum(p.stat().st_size for p in _seen if p.exists())

    # 8N1 framing, no flow control: bytes x 10 / baud.
    _up = len(payload)
    _down = uart_out_bytes()
    _secs = (_up + _down) * 10 / baud.value
    _uart = mo.md(
        f"""
    #### Round trip &nbsp; \u2248 {_fmt_dur(_secs)}

    **{_fmt_size(_up)}** up \u00b7 **{_fmt_size(_down)}** back, at {baud.value} baud.
    Sending the picture is almost all of it.

    *Every inference pays this.*
        """
    )

    # --- the loader: a one-off, and only elf/tcl pay it.
    _static = loader_static_bytes()
    _vol = _fmt_size(_static) if _static else "the whole model"
    if loader_dd.value == "sd":
        _loader = mo.md(
            f"""
    #### Loading the model &nbsp; \u00b7 &nbsp; `sd`

    The model sits on the SD card and the app reads it at start-up
    (about 90 s). Flashing stays quick.

    *Paid once, when the application loads.*
            """
        )
    else:
        _loader = mo.md(
            f"""
    #### Loading the model &nbsp; \u00b7 &nbsp; \u26a0\ufe0f `{loader_dd.value}`

    **{_vol}** has to cross the JTAG cable before the app can start -
    expect **minutes, not seconds**. `sd` avoids it entirely.

    *Paid once, when the application loads - not per inference.*
            """
        )

    mo.hstack([_uart, _loader], justify="start", gap=3, widths=[1, 1])
    return


@app.cell
def board_flash(MILL, baud, board_dd, config_dd, loader_dd, mo, spec):
    build_btn = mo.ui.run_button(label=f"Build + flash {board_dd.value}")
    _build_cmd = (
        f"pixi run {MILL} -Dvta.board.name={board_dd.value} "
        f"-Dvta.uart.baud={baud.value} "
        f"\'examples.onnx[{spec.name},{config_dd.value}].buildVitisApp\' "
        f"--runner run_nn_uart --dataLoader {loader_dd.value}"
    )
    _flash_cmd = (
        f"pixi run {MILL} -Dvta.board.name={board_dd.value} "
        f"-Dvta.uart.baud={baud.value} "
        f"\'examples.onnx[{spec.name},{config_dd.value}].flashBoard\' "
        f"--runner run_nn_uart --dataLoader {loader_dd.value}"
    )
    mo.vstack([
        mo.md(
            f"""
    ### 5a - (optional) put the application on the board

    Builds the application with Vitis and flashes it. Only needed when the board
    is empty, or when you have changed the model, the config or the baud rate.

    \u26a0\ufe0f **The first run for a given config is very long** - with no XSA
    available it launches Vivado to build one.

    {build_btn}
            """
        ),
        mo.accordion({
            "Commands": mo.md(
                f"""
    ```sh
    {_build_cmd}
    {_flash_cmd}
    ```
                """
            ),
            "If you use the `sd` loader": mo.md(
                f"""
    The application expects its model data already on a FAT32 SD card, under
    `1:/{spec.name}/`. `./mill ...sdCard` stages those files for you, but copying
    them onto the card is still a manual step.
                """
            ),
        }),
    ])
    return (build_btn,)


@app.cell
def board_flash_run(
    MILL,
    REPO_ROOT,
    baud,
    board_dd,
    build_btn,
    config_dd,
    loader_dd,
    mo,
    spec,
    subprocess,
):
    mo.stop(not build_btn.value, mo.md("*idle — press the button above to build + flash*"))
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
def board_button(mo):
    board_btn = mo.ui.run_button(label="\u25b6 Send the photo")
    mo.vstack([
        mo.md(
            f"""
    ### 5b - run it

    Sends the photo down the cable, waits for the board to finish, and reads the
    answer back.

    {board_btn}
            """
        ),
        mo.accordion({
            "Two things that look like failures": mo.md(
                """
    **The first run after flashing takes about 90 s longer**, because the
    application is still copying the model off the SD card.

    **`runUart` reports an error even when it worked.** It compares the result
    against a golden file belonging to its own random test input, so a real
    photograph always "mismatches". The notebook trusts the returned data, not
    the exit code.
                """
            ),
        }),
    ])
    return (board_btn,)


@app.cell(hide_code=True)
def board_run(
    MILL,
    REPO_ROOT,
    SCRATCH_DIR,
    baud,
    board_btn,
    board_dd,
    cached_result,
    config_dd,
    decode_board,
    leg_out_path,
    mo,
    payload,
    port,
    spec,
    subprocess,
    time,
):
    if not board_btn.value:
        probs_board, info_board = cached_result("board", decode_board)
    else:
        probs_board = None
        info_board = None
        _t0 = time.time()
        _out_bin = leg_out_path("board")
        _stamp = _out_bin.stat().st_mtime if _out_bin.exists() else None
        _in = SCRATCH_DIR / "input.bin"
        _in.write_bytes(payload)
        _cmd = [
            "pixi", "run", str(MILL), f"-Dvta.board.name={board_dd.value}",
            f"-Dvta.uart.baud={baud.value}",
            f"examples.onnx[{spec.name},{config_dd.value}].runUart",
            "--port", port.value,
            "--input", str(_in),
            "--output", str(_out_bin),
            "--banner-timeout", "240",
            "--ready-timeout", "180",
        ]
        with mo.status.spinner(
            title=f"mill runUart on {board_dd.value} "
            "(first run after flashing \u2248 90 s for the SD load)\u2026"
        ):
            _cp = subprocess.run(
                _cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=420
            )
        # runUart checks against the random input's golden, so it exits 1 on a
        # real photo; the output file is what counts.
        _fresh = _out_bin.exists() and _out_bin.stat().st_mtime != _stamp
        if not _out_bin.exists() or not _out_bin.stat().st_size:
            info_board = (
                f"\u274c **mill runUart** produced no output (exit {_cp.returncode}).\n\n"
                f"```\n{(_cp.stdout + _cp.stderr)[-3000:]}\n```"
            )
        else:
            _raw = _out_bin.read_bytes()
            probs_board = decode_board(_raw)
            info_board = (
                f"mill runUart ({board_dd.value}, {config_dd.value}) \u00b7 "
                f"{len(_raw)} B \u00b7 {time.time() - _t0:.1f} s"
                + ("" if _fresh else " \u00b7 \u26a0\ufe0f output file not rewritten")
            )
    return info_board, probs_board


@app.cell
def board_results(info_board, leg_panel, probs_board):
    leg_panel(probs_board, info_board, "board")
    return


@app.cell
def comparison_header(mo):
    mo.md("""
    ## 6 - Side by side

    Everything that ran, on one colour scale, with the differences worked out.

    They should be identical. The table below subtracts each result from the
    earliest step that ran, so the first row with a real difference in it is the
    one worth investigating.
    """)
    return


@app.cell
def comparison(
    leg_detections,
    leg_heatmap,
    leg_rows,
    mio,
    mo,
    np,
    plt,
    probs_board,
    probs_fsim,
    probs_local,
    probs_vsim,
    spec,
):
    # 6 - the payoff: every leg that ran, on one colour scale.
    comparison = [
        (_n, _p)
        for _n, _p in [
            ("onnxruntime", probs_local),
            ("fsim", probs_fsim),
            ("vsim", probs_vsim),
            ("board", probs_board),
        ]
        if _p is not None
    ]

    def _comparison_view():
        if not comparison:
            return mo.md(
                "*Nothing has run yet - press \u25b6 in section 3, 4 or 5 and the "
                "results land here side by side.*"
            )
        # Shared vmax so the panels are comparable.
        vmax = max(0.15, max(float(p.max()) for _, p in comparison))
        fig, axes = plt.subplots(
            1, len(comparison), figsize=(5.2 * len(comparison), 5.0), squeeze=False
        )
        for ax, (name, probs) in zip(axes[0], comparison):
            leg_heatmap(ax, probs, name, vmax=vmax)
        fig.tight_layout()

        # Difference against the earliest stage that ran.
        base_name, base = comparison[0]
        top1 = lambda p: mio.topk_classes(p, spec.class_names, k=1)[0][1]
        deltas = [
            {
                "leg": name,
                "vs": base_name,
                "max |\u0394 prob|": round(float(np.abs(probs - base).max()), 4),
                "mean |\u0394 prob|": round(float(np.abs(probs - base).mean()), 5),
                "top-1": top1(probs),
                "top-1 agrees": "\u2014" if name == base_name
                else ("\u2705" if top1(probs) == top1(base) else "\u274c"),
            }
            for name, probs in comparison
        ]
        rows = []
        for name, probs in comparison:
            rows += leg_rows(leg_detections(probs), name)
        return mo.vstack(
            [
                fig,
                mo.md(
                    f"**Difference from `{base_name}`** \u2014 a jump in "
                    "`max |\u0394 prob|` names the step that broke."
                ),
                mo.ui.table(deltas, selection=None),
                mo.md("**All cell-boxes, every leg**"),
                mo.ui.table(rows, selection=None),
            ]
        )

    _comparison_view()
    return


if __name__ == "__main__":
    app.run()
