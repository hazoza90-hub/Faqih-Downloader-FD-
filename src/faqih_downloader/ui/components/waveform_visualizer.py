"""
WaveformVisualizerCanvas: Symmetrical audio waveform visualizer for completed audio cards in Smart Download (SD).
"""
from __future__ import annotations

import math
from typing import Optional, Any, List

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore


class WaveformVisualizerCanvas:
    """Renders a sleek, organic audio waveform bars visualizer on a Tkinter Canvas."""

    COLOR_BARS = "#22c55e"       # Vibrant green
    COLOR_BARS_DIM = "#15803d"   # Dim green base
    COLOR_BG = "#1c1f29"         # Vault card background

    def __init__(
        self,
        parent: Any,
        height: int = 34,
        bg: str = COLOR_BG,
        num_bars: int = 42
    ):
        self.parent = parent
        self.height = height
        self.bg = bg
        self.num_bars = num_bars
        self._pattern: List[float] = self._generate_default_pattern(num_bars)

        if tk is not None:
            self.canvas = tk.Canvas(
                parent,
                height=self.height,
                bg=self.bg,
                bd=0,
                highlightthickness=0,
                relief="flat"
            )
            self.canvas.bind("<Configure>", lambda e: (e.width, e.height) != getattr(self, "_last_canvas_size", None) and self.redraw())
        else:
            self.canvas = None  # type: ignore

    def pack(self, **kwargs):
        if self.canvas:
            self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        if self.canvas:
            self.canvas.grid(**kwargs)

    @staticmethod
    def _generate_default_pattern(count: int) -> List[float]:
        """Generates realistic audio frequency peaks pattern."""
        vals = []
        for i in range(count):
            t = i / float(count)
            # Combine sine frequencies for authentic audio profile
            v = 0.25 + 0.5 * math.sin(t * math.pi) * (0.6 + 0.4 * math.sin(t * 14.0) * math.cos(t * 7.0))
            v = max(0.12, min(0.95, v))
            vals.append(v)
        return vals

    def redraw(self):
        if not self.canvas or not self.canvas.winfo_exists():
            return
        w = self.canvas.winfo_width()
        if w <= 10:
            w = 240
        h = self.canvas.winfo_height()
        if h <= 6:
            h = self.height
        self._last_canvas_size = (w, h)

        self.canvas.delete("all")

        bar_spacing = w / float(self.num_bars)
        bar_w = max(2.0, bar_spacing - 2.0)
        center_y = h / 2.0

        for i, norm_h in enumerate(self._pattern):
            bar_height = max(3.0, (h - 6.0) * norm_h)
            x0 = i * bar_spacing + 1.0
            x1 = x0 + bar_w
            y0 = center_y - (bar_height / 2.0)
            y1 = center_y + (bar_height / 2.0)

            # Round edges by creating small smoothed bar
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                fill=self.COLOR_BARS,
                outline="",
                width=0
            )


__all__ = ["WaveformVisualizerCanvas"]
