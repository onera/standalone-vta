#!/usr/bin/env python3
"""digit_canvas.py - a hand-drawable NxN pixel grid for the lenet5 notebook.

A minimal anywidget (https://anywidget.dev) wrapping a plain <canvas>: drag
with the mouse (or a touchscreen) to paint 0-255 grayscale pixels into an
``N x N`` grid (``grid_size``, default 32), right-drag (or hold shift while
dragging) to erase, "Clear" resets to all-black. The synced trait is a flat,
row-major list of ints - ``widget.pixels`` (or ``ui.value["pixels"]`` once
wrapped in ``mo.ui.anywidget``). ``tutorial4_lenet5_digit.py`` sizes it to
the model's actual input (``grid_size=spec.in_h``, 28 for lenet5.onnx), so
what's drawn is exactly what gets sent - no resize or crop needed.

No preprocessing beyond that happens here - this module only gets pixels out
of the browser and into Python; quantising them is the notebook's job, via
``model_io``.
"""
from __future__ import annotations

import anywidget
import traitlets

GRID = 32  # logical pixel grid; matches classic LeNet-5's 32x32 convention

_ESM = r"""
function render({ model, el }) {
  const N = model.get("grid_size") || 32;
  const scale = Math.floor(320 / N);
  const w = N * scale, h = N * scale;

  const wrap = document.createElement("div");
  wrap.style.display = "inline-block";
  wrap.style.fontFamily = "system-ui, sans-serif";

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.style.imageRendering = "pixelated";
  canvas.style.border = "1px solid #888";
  canvas.style.touchAction = "none";
  canvas.style.cursor = "crosshair";
  canvas.style.background = "black";
  const ctx = canvas.getContext("2d");

  let pixels = (model.get("pixels") || new Array(N * N).fill(0)).slice();

  function repaint() {
    ctx.fillStyle = "black";
    ctx.fillRect(0, 0, w, h);
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        const v = pixels[y * N + x] || 0;
        if (v > 0) {
          ctx.fillStyle = `rgb(${v},${v},${v})`;
          ctx.fillRect(x * scale, y * scale, scale, scale);
        }
      }
    }
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= N; i++) {
      ctx.beginPath();
      ctx.moveTo(i * scale + 0.5, 0);
      ctx.lineTo(i * scale + 0.5, h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * scale + 0.5);
      ctx.lineTo(w, i * scale + 0.5);
      ctx.stroke();
    }
  }

  // Full-strength centre, dimmer 4-neighbours: MNIST-like soft strokes.
  const BRUSH = [[0, 0, 255], [1, 0, 130], [-1, 0, 130], [0, 1, 130], [0, -1, 130]];

  function paintCell(cx, cy, erase) {
    for (const [dx, dy, val] of BRUSH) {
      const x = cx + dx, y = cy + dy;
      if (x < 0 || x >= N || y < 0 || y >= N) continue;
      const idx = y * N + x;
      pixels[idx] = erase ? 0 : Math.max(pixels[idx] || 0, val);
    }
  }

  function paintAt(clientX, clientY, erase) {
    const rect = canvas.getBoundingClientRect();
    const cx = Math.floor(((clientX - rect.left) / rect.width) * N);
    const cy = Math.floor(((clientY - rect.top) / rect.height) * N);
    paintCell(cx, cy, erase);
    repaint();
  }

  let drawing = false;
  canvas.addEventListener("pointerdown", (e) => {
    drawing = true;
    canvas.setPointerCapture(e.pointerId);
    paintAt(e.clientX, e.clientY, e.button === 2 || e.shiftKey);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drawing) return;
    paintAt(e.clientX, e.clientY, (e.buttons & 2) !== 0 || e.shiftKey);
  });
  function endStroke() {
    if (!drawing) return;
    drawing = false;
    model.set("pixels", pixels.slice());
    model.save_changes();
  }
  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointerleave", endStroke);
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  const controls = document.createElement("div");
  controls.style.marginTop = "6px";

  const clearBtn = document.createElement("button");
  clearBtn.textContent = "Clear";
  clearBtn.onclick = () => {
    pixels = new Array(N * N).fill(0);
    repaint();
    model.set("pixels", pixels.slice());
    model.save_changes();
  };
  controls.appendChild(clearBtn);

  const hint = document.createElement("span");
  hint.textContent = "  drag to draw · shift-drag / right-drag to erase";
  hint.style.fontSize = "12px";
  hint.style.opacity = "0.7";
  hint.style.marginLeft = "8px";
  controls.appendChild(hint);

  model.on("change:pixels", () => {
    pixels = (model.get("pixels") || new Array(N * N).fill(0)).slice();
    repaint();
  });

  wrap.appendChild(canvas);
  wrap.appendChild(controls);
  el.appendChild(wrap);
  repaint();
}
export default { render };
"""


class DigitCanvasWidget(anywidget.AnyWidget):
    """``GRID x GRID`` grayscale drawing canvas. ``pixels`` is a flat,
    row-major list of ``grid_size**2`` ints in ``[0, 255]``, 0 = black."""

    _esm = _ESM
    grid_size = traitlets.Int(GRID).tag(sync=True)
    pixels = traitlets.List(traitlets.Int(), default_value=[0] * (GRID * GRID)).tag(sync=True)

    def __init__(self, grid_size: int = GRID, **kwargs):
        super().__init__(
            grid_size=grid_size, pixels=[0] * (grid_size * grid_size), **kwargs
        )
