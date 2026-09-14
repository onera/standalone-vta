#!/usr/bin/env python3
"""
model_io.py - image <-> tensor helpers for the UART inference notebooks.

Shapes, quantisation and class names are read from the selected ``.onnx``
(and the block size from the VTA config) by :func:`load_model_spec`; the
module-level constants are defaults for ``examples/onnx/qyolo.onnx``.

  * preprocessing : image -> letterboxed INT8 HWC bytes (board, fsim/vsim) or
                    NCHW tensor (onnxruntime)
  * decode        : board (block-tiled), simulator or onnxruntime output ->
                    (C,H,W) probabilities
  * grid -> boxes : merge adjacent same-class cells into coarse boxes
  * reference     : full yolo_nas_s.onnx detections (NMS included)

``python model_io.py`` runs self-tests on qyolo.onnx and lenet5.onnx.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from uart_nn import detile  # noqa: E402

# --------------------------------------------------------------------------- #
# Defaults for qyolo.onnx
# --------------------------------------------------------------------------- #

INPUT_SIZE = 640
GRID = 20
NUM_CLASSES = 80
BLOCK = 16
PAD_VALUE = 114                     # YOLO-NAS letterbox pad

INPUT_SCALE = 1.0
INPUT_ZP = -128

OUTPUT_SCALE = 0.062482379376888275
OUTPUT_ZP = 58

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]
assert len(COCO_NAMES) == NUM_CLASSES


DIGIT_NAMES = [str(i) for i in range(10)]


def class_names_for(num_classes: int) -> list[str]:
    """COCO-80 names when the class count matches, digit names ("0".."9") for
    a 10-way classifier (e.g. lenet5.onnx), else generic 'class<i>'."""
    if num_classes == NUM_CLASSES:
        return list(COCO_NAMES)
    if num_classes == len(DIGIT_NAMES):
        return list(DIGIT_NAMES)
    return [f"class{i}" for i in range(num_classes)]


# --------------------------------------------------------------------------- #
# ONNX introspection: figure out a model's shapes and quantisation generically
# --------------------------------------------------------------------------- #


def read_tensor_quant(onnx_path: str | Path, tensor_name: str
                      ) -> tuple[float, int] | None:
    """(scale, zero_point) of a QOperator-quantised tensor, from its
    ``<base>_scale`` / ``<base>_zero_point`` initializers; None if absent."""
    import onnx
    from onnx import numpy_helper

    base = tensor_name[:-len("_quantized")] if tensor_name.endswith("_quantized") \
        else tensor_name
    init = {t.name: t for t in onnx.load(str(onnx_path)).graph.initializer}
    s_name, z_name = base + "_scale", base + "_zero_point"
    if s_name not in init or z_name not in init:
        return None
    s = numpy_helper.to_array(init[s_name]).reshape(-1)[0]
    z = numpy_helper.to_array(init[z_name]).reshape(-1)[0]
    return float(s), int(z)


def read_output_quant(onnx_path: str | Path) -> tuple[float, int]:
    """(scale, zero_point) of the graph output, or the qyolo defaults."""
    try:
        import onnx

        out_name = onnx.load(str(onnx_path)).graph.output[0].name
        got = read_tensor_quant(onnx_path, out_name)
        return got if got is not None else (OUTPUT_SCALE, OUTPUT_ZP)
    except Exception:
        return OUTPUT_SCALE, OUTPUT_ZP


def read_input_quant(onnx_path: str | Path) -> tuple[float, int]:
    """(scale, zero_point) of the graph input, or the qyolo defaults."""
    try:
        import onnx

        in_name = onnx.load(str(onnx_path)).graph.input[0].name
        got = read_tensor_quant(onnx_path, in_name)
        return got if got is not None else (INPUT_SCALE, INPUT_ZP)
    except Exception:
        return INPUT_SCALE, INPUT_ZP


def model_io_dims(onnx_path: str | Path) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """((in_c,in_h,in_w), (out_c,out_h,out_w)) from the graph's NCHW shapes;
    a ``[N,C]`` output is a 1x1 grid."""
    import onnx

    g = onnx.load(str(onnx_path)).graph

    def dims(vi, label):
        d = [x.dim_value for x in vi.type.tensor_type.shape.dim]
        if len(d) == 4:
            _, c, h, w = d
        elif len(d) == 2:
            _, c = d
            h = w = 1
        else:
            raise ValueError(f"{label} '{vi.name}' has rank {len(d)}, expected 2 or 4")
        if c <= 0 or h <= 0 or w <= 0:
            raise ValueError(f"{label} '{vi.name}' has a dynamic dimension: {d}")
        return c, h, w

    return dims(g.input[0], "input"), dims(g.output[0], "output")


def config_block_size(config_path: str | Path | None) -> int:
    """``1 << LOG_BLOCK`` from a VTA config json, or the default."""
    if config_path is None:
        return BLOCK
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        return 1 << int(cfg["LOG_BLOCK"])
    except Exception:
        return BLOCK


@dataclass(frozen=True)
class ModelSpec:
    """Pre/post-processing parameters of one model on one VTA config."""

    path: Path
    name: str                 # onnx filename stem, also the mill model key
    in_c: int
    in_h: int
    in_w: int
    out_c: int
    out_h: int
    out_w: int
    input_scale: float
    input_zp: int
    output_scale: float
    output_zp: int
    block: int
    class_names: list[str] = field(default_factory=list)

    @property
    def is_rgb_image_input(self) -> bool:
        return self.in_c == 3 and self.in_h == self.in_w

    @property
    def is_grayscale_image_input(self) -> bool:
        return self.in_c == 1 and self.in_h == self.in_w

    @property
    def stride(self) -> int:
        """Input pixels per output cell."""
        if self.out_h <= 1:
            return self.in_h
        return self.in_h // self.out_h


def load_model_spec(onnx_path: str | Path, config_path: str | Path | None = None
                    ) -> ModelSpec:
    """Build a :class:`ModelSpec` from an ONNX model and a VTA config."""
    onnx_path = Path(onnx_path)
    (in_c, in_h, in_w), (out_c, out_h, out_w) = model_io_dims(onnx_path)
    in_scale, in_zp = read_input_quant(onnx_path)
    out_scale, out_zp = read_output_quant(onnx_path)
    return ModelSpec(
        path=onnx_path, name=onnx_path.stem,
        in_c=in_c, in_h=in_h, in_w=in_w,
        out_c=out_c, out_h=out_h, out_w=out_w,
        input_scale=in_scale, input_zp=in_zp,
        output_scale=out_scale, output_zp=out_zp,
        block=config_block_size(config_path),
        class_names=class_names_for(out_c),
    )


# --------------------------------------------------------------------------- #
# Letterbox / preprocessing
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Letterbox:
    """Maps original-image pixels <-> the size x size letterboxed frame."""

    scale: float      # original -> letterbox multiplier
    pad_x: int        # left padding in the letterboxed frame
    pad_y: int        # top padding in the letterboxed frame
    orig_w: int
    orig_h: int

    def to_orig(self, box_xyxy: np.ndarray) -> np.ndarray:
        """De-letterbox xyxy boxes (in letterboxed-frame space) back to
        original pixels."""
        b = np.asarray(box_xyxy, dtype=np.float64).reshape(-1, 4).copy()
        b[:, [0, 2]] = (b[:, [0, 2]] - self.pad_x) / self.scale
        b[:, [1, 3]] = (b[:, [1, 3]] - self.pad_y) / self.scale
        b[:, [0, 2]] = b[:, [0, 2]].clip(0, self.orig_w)
        b[:, [1, 3]] = b[:, [1, 3]].clip(0, self.orig_h)
        return b


def letterbox_image(img_rgb: np.ndarray, size: int = INPUT_SIZE,
                    pad_value: int = PAD_VALUE) -> tuple[np.ndarray, Letterbox]:
    """Resize an RGB uint8 image to ``size`` x ``size`` keeping its aspect
    ratio, centre-padded with ``pad_value``. The result stays RGB."""
    from PIL import Image

    h, w = img_rgb.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = np.asarray(
        Image.fromarray(img_rgb).resize((new_w, new_h), Image.BILINEAR)
    )
    canvas = np.full((size, size, 3), pad_value, dtype=np.uint8)
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, Letterbox(scale, pad_x, pad_y, w, h)


def _to_channels(img_uint8: np.ndarray, size: int, in_c: int) -> np.ndarray:
    """size x size (x{1,3}) uint8 -> size x size x in_c (RGB reduced to luma
    when ``in_c == 1``)."""
    if img_uint8.shape[:2] != (size, size):
        raise ValueError(f"expected {size}x{size} spatial dims, got {img_uint8.shape}")
    img = img_uint8[..., None] if img_uint8.ndim == 2 else img_uint8

    if in_c == 3:
        if img.shape[2] != 3:
            raise ValueError(f"in_c=3 needs an RGB source, got shape {img_uint8.shape}")
        return img
    if in_c == 1:
        if img.shape[2] == 1:
            return img
        if img.shape[2] == 3:
            gray = np.dot(img.astype(np.float32), [0.299, 0.587, 0.114])
            return gray.round().astype(np.uint8)[..., None]
        raise ValueError(f"don't know how to reduce shape {img_uint8.shape} to 1 channel")
    raise ValueError(f"unsupported in_c={in_c} (only 1 or 3 are supported)")


def to_input_int8(img_uint8: np.ndarray, size: int = INPUT_SIZE,
                  input_zp: int = INPUT_ZP, in_c: int = 3) -> np.ndarray:
    """size x size uint8 image -> int8 HWC, q = pixel + input_zp."""
    arr = _to_channels(img_uint8, size, in_c)
    return (arr.astype(np.int16) + input_zp).astype(np.int8)


def board_input_bytes(img_uint8: np.ndarray, size: int = INPUT_SIZE,
                      input_zp: int = INPUT_ZP, in_c: int = 3) -> bytes:
    """run_nn_uart payload: flat int8 HWC."""
    return to_input_int8(img_uint8, size, input_zp, in_c).tobytes()


def onnx_input_nchw(img_uint8: np.ndarray, size: int = INPUT_SIZE,
                    input_zp: int = INPUT_ZP, in_c: int = 3) -> np.ndarray:
    """int8 NCHW [1,in_c,size,size] for onnxruntime."""
    return to_input_int8(img_uint8, size, input_zp, in_c).transpose(2, 0, 1)[None]


# --------------------------------------------------------------------------- #
# Board output -> probabilities
# --------------------------------------------------------------------------- #


def detile_output(raw: bytes, num_classes: int = NUM_CLASSES, grid_h: int = GRID,
                  grid_w: int = GRID, block: int = BLOCK,
                  scale: float = OUTPUT_SCALE, zp: int = OUTPUT_ZP) -> np.ndarray:
    """Block-tiled board output -> (C,H,W) probabilities."""
    flat = np.frombuffer(
        detile(raw, num_classes, grid_h, grid_w, block), dtype=np.int8
    )
    logits = (flat.astype(np.float32).reshape(num_classes, grid_h, grid_w) - zp) * scale
    return _sigmoid(logits)


def probs_from_sim_output(raw: bytes, num_classes: int = NUM_CLASSES,
                          grid_h: int = GRID, grid_w: int = GRID,
                          scale: float = OUTPUT_SCALE, zp: int = OUTPUT_ZP
                          ) -> np.ndarray:
    """fsim/vsim output (flat NCHW int8) -> (C,H,W) probabilities."""
    return probs_from_onnx_output(
        np.frombuffer(raw, dtype=np.int8), num_classes, grid_h, grid_w, scale, zp
    )


def probs_from_onnx_output(out_i8: np.ndarray, num_classes: int = NUM_CLASSES,
                           grid_h: int = GRID, grid_w: int = GRID,
                           scale: float = OUTPUT_SCALE, zp: int = OUTPUT_ZP
                          ) -> np.ndarray:
    """onnxruntime int8 [1,C,H,W] (or [1,C]) -> (C,H,W) probabilities."""
    logits = (np.asarray(out_i8, dtype=np.float32).reshape(num_classes, grid_h, grid_w)
              - zp) * scale
    return _sigmoid(logits)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


# --------------------------------------------------------------------------- #
# Grid -> coarse boxes + classification
# --------------------------------------------------------------------------- #


@dataclass
class Detection:
    cls: int
    name: str
    score: float
    box_xyxy: np.ndarray   # original-image pixels
    n_cells: int = 1       # merged grid cells


def grid_detections(probs: np.ndarray, lb: Letterbox, class_names: list[str],
                    stride: int, conf: float = 0.30, merge: bool = True
                   ) -> list[Detection]:
    """Boxes (original-image pixels) of the cells scoring >= ``conf``; with
    ``merge``, 4-connected cells of the same class form one box."""
    grid_h, grid_w = probs.shape[1:]
    cls_grid = probs.argmax(0)           # (H,W)
    p_grid = probs.max(0)               # (H,W)
    fire = p_grid >= conf
    dets: list[Detection] = []
    if not fire.any():
        return dets

    if not merge:
        for gy, gx in zip(*np.where(fire)):
            dets.append(_cell_det(int(cls_grid[gy, gx]), float(p_grid[gy, gx]),
                                  gx, gy, gx, gy, lb, stride, class_names, 1))
        return dets

    seen = np.zeros_like(fire)
    for gy in range(grid_h):
        for gx in range(grid_w):
            if not fire[gy, gx] or seen[gy, gx]:
                continue
            c = cls_grid[gy, gx]
            stack = [(gy, gx)]
            seen[gy, gx] = True
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < grid_h and 0 <= nx < grid_w and not seen[ny, nx]
                            and fire[ny, nx] and cls_grid[ny, nx] == c):
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [y for y, _ in cells]
            xs = [x for _, x in cells]
            score = float(max(p_grid[y, x] for y, x in cells))
            dets.append(_cell_det(int(c), score, min(xs), min(ys),
                                  max(xs), max(ys), lb, stride, class_names,
                                  len(cells)))
    dets.sort(key=lambda d: d.score, reverse=True)
    return dets


def _cell_det(cls: int, score: float, gx0: int, gy0: int, gx1: int, gy1: int,
              lb: Letterbox, stride: int, class_names: list[str],
              n_cells: int) -> Detection:
    box_lb = np.array([gx0 * stride, gy0 * stride,
                       (gx1 + 1) * stride, (gy1 + 1) * stride], dtype=np.float64)
    return Detection(cls, class_names[cls], score,
                     lb.to_orig(box_lb)[0], n_cells)


def global_class_scores(probs: np.ndarray) -> np.ndarray:
    """Per-class maximum over the grid, shape (C,)."""
    return probs.reshape(probs.shape[0], -1).max(1)


def topk_classes(probs: np.ndarray, class_names: list[str], k: int = 5
                 ) -> list[tuple[int, str, float]]:
    s = global_class_scores(probs)
    idx = np.argsort(s)[::-1][:k]
    return [(int(i), class_names[int(i)], float(s[i])) for i in idx]


# --------------------------------------------------------------------------- #
# Reference: the full model with NMS baked in
# --------------------------------------------------------------------------- #


def reference_detections(session, lb_rgb_uint8: np.ndarray, lb: Letterbox,
                         class_names: list[str] = COCO_NAMES,
                         conf: float = 0.30) -> list[Detection]:
    """Detections of the full yolo_nas_s.onnx ``session``, in original-image
    pixels."""
    feed = lb_rgb_uint8.transpose(2, 0, 1)[None].astype(np.uint8)
    name = session.get_inputs()[0].name
    n_pred, boxes, scores, classes = session.run(None, {name: feed})
    n = int(np.asarray(n_pred).reshape(-1)[0])
    boxes = np.asarray(boxes).reshape(-1, 4)[:n]
    scores = np.asarray(scores).reshape(-1)[:n]
    classes = np.asarray(classes).reshape(-1)[:n].astype(int)
    keep = scores >= conf
    out = []
    for b, s, c in zip(lb.to_orig(boxes[keep]), scores[keep], classes[keep]):
        name = class_names[c] if c < len(class_names) else f"class{c}"
        out.append(Detection(int(c), name, float(s), b, 0))
    out.sort(key=lambda d: d.score, reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Self-tests
# --------------------------------------------------------------------------- #


def _selftest() -> int:
    import onnxruntime as ort

    root = _HERE.parents[3]
    qyolo = root / "examples/onnx/qyolo.onnx"
    if not qyolo.exists():
        print(f"SKIP: {qyolo} not found")
        return 0

    spec = load_model_spec(qyolo, root / "config/vta_w8b.json")
    print(f"spec: in={spec.in_c}x{spec.in_h}x{spec.in_w} "
          f"out={spec.out_c}x{spec.out_h}x{spec.out_w} block={spec.block} "
          f"in_quant=({spec.input_scale},{spec.input_zp}) "
          f"out_quant=({spec.output_scale},{spec.output_zp})")
    assert (spec.in_c, spec.in_h, spec.in_w) == (3, 640, 640)
    assert (spec.out_c, spec.out_h, spec.out_w) == (80, 20, 20)
    assert spec.block == 16
    assert spec.is_rgb_image_input
    assert spec.stride == 32

    rng = np.random.default_rng(0)
    img = (rng.random((480, 640, 3)) * 40 + 90).astype(np.uint8)
    img[120:360, 200:470] = (200, 70, 55)

    lb_img, lb = letterbox_image(img, size=spec.in_h)
    assert lb_img.shape == (640, 640, 3)

    payload = board_input_bytes(lb_img, size=spec.in_h, input_zp=spec.input_zp)
    assert len(payload) == 3 * 640 * 640, len(payload)

    sess = ort.InferenceSession(str(qyolo), providers=["CPUExecutionProvider"])
    out = sess.run(None, {sess.get_inputs()[0].name:
                          onnx_input_nchw(lb_img, size=spec.in_h, input_zp=spec.input_zp)})[0]
    assert out.shape == (1, 80, 20, 20) and out.dtype == np.int8, (out.shape, out.dtype)

    probs = probs_from_onnx_output(out, spec.out_c, spec.out_h, spec.out_w,
                                   spec.output_scale, spec.output_zp)
    assert probs.shape == (80, 20, 20)
    assert 0.0 <= probs.min() <= probs.max() <= 1.0

    tiled = _fake_tile(out[0], spec.block)
    probs_b = detile_output(tiled, spec.out_c, spec.out_h, spec.out_w, spec.block,
                            spec.output_scale, spec.output_zp)
    assert np.array_equal(probs_b, probs), np.abs(probs_b - probs).max()

    probs_s = probs_from_sim_output(out.tobytes(), spec.out_c, spec.out_h, spec.out_w,
                                    spec.output_scale, spec.output_zp)
    assert np.array_equal(probs_s, probs), np.abs(probs_s - probs).max()

    dets = grid_detections(probs, lb, spec.class_names, spec.stride,
                           conf=float(probs.max()) - 1e-6, merge=True)
    print(f"top-5 classes: {[(n, round(s, 3)) for _, n, s in topk_classes(probs, spec.class_names)]}")
    print(f"grid_detections at conf~max -> {len(dets)} box(es)")
    for d in dets[:3]:
        print(f"  {d.name:12s} p={d.score:.3f} cells={d.n_cells} "
              f"box={np.round(d.box_xyxy, 1).tolist()}")
    print("SELFTEST OK")
    return 0


def _selftest_lenet5() -> int:
    import onnxruntime as ort

    root = _HERE.parents[3]
    lenet = root / "examples/onnx/lenet5.onnx"
    if not lenet.exists():
        print(f"SKIP: {lenet} not found")
        return 0

    spec = load_model_spec(lenet, root / "config/vta_w8b.json")
    print(f"spec: in={spec.in_c}x{spec.in_h}x{spec.in_w} "
          f"out={spec.out_c}x{spec.out_h}x{spec.out_w} block={spec.block} "
          f"in_quant=({spec.input_scale},{spec.input_zp}) "
          f"out_quant=({spec.output_scale},{spec.output_zp})")
    assert spec.in_c == 1 and spec.in_h == spec.in_w == 28
    assert spec.out_c == 10
    assert spec.is_grayscale_image_input and not spec.is_rgb_image_input
    assert spec.stride == spec.in_h
    assert spec.class_names == DIGIT_NAMES

    img = np.zeros((64, 48, 3), dtype=np.uint8)
    img[10:54, 14:34] = 255

    lb_img, lb = letterbox_image(img, size=spec.in_h, pad_value=0)
    assert lb_img.shape == (28, 28, 3)

    payload = board_input_bytes(lb_img, size=spec.in_h, input_zp=spec.input_zp, in_c=spec.in_c)
    assert len(payload) == 1 * 28 * 28, len(payload)

    sess = ort.InferenceSession(str(lenet), providers=["CPUExecutionProvider"])
    out = sess.run(
        None,
        {sess.get_inputs()[0].name:
         onnx_input_nchw(lb_img, size=spec.in_h, input_zp=spec.input_zp, in_c=spec.in_c)},
    )[0]
    assert out.dtype == np.int8 and out.reshape(-1).shape == (10,), (out.shape, out.dtype)

    probs = probs_from_onnx_output(out, spec.out_c, spec.out_h, spec.out_w,
                                   spec.output_scale, spec.output_zp)
    assert probs.shape == (10, 1, 1)
    assert 0.0 <= probs.min() <= probs.max() <= 1.0

    tiled = _fake_tile(out.reshape(10, 1, 1), spec.block)
    probs_b = detile_output(tiled, spec.out_c, spec.out_h, spec.out_w, spec.block,
                            spec.output_scale, spec.output_zp)
    assert np.array_equal(probs_b, probs), np.abs(probs_b - probs).max()

    probs_s = probs_from_sim_output(out.tobytes(), spec.out_c, spec.out_h, spec.out_w,
                                    spec.output_scale, spec.output_zp)
    assert np.array_equal(probs_s, probs), np.abs(probs_s - probs).max()

    top = topk_classes(probs, spec.class_names, k=3)
    print(f"top-3 digits: {[(n, round(s, 3)) for _, n, s in top]}")
    print("LENET5 SELFTEST OK")
    return 0


def _fake_tile(nchw_i8: np.ndarray, block: int = BLOCK) -> bytes:
    """Inverse of uart_nn.detile."""
    c, h, w = nchw_i8.shape
    n = h * w
    cb, nb = (c + block - 1) // block, (n + block - 1) // block
    buf = np.zeros((nb, cb, block, block), dtype=np.int8)
    flat = nchw_i8.reshape(c, n)
    for row in range(n):
        rb, rr = divmod(row, block)
        for col in range(c):
            cbi, cc = divmod(col, block)
            buf[rb, cbi, rr, cc] = flat[col, row]
    return buf.tobytes()


if __name__ == "__main__":
    raise SystemExit(_selftest() or _selftest_lenet5())
