"""
LedEqualizerMatrix: 16-channel x 7-row LED Equalizer Spectrum Matrix widget for Smart Download (SD).
Visualizes multi-threaded download chunk activity in real-time.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore


class LedEqualizerMatrix:
    """
    Renders an 8-pair (16-channel) by 7-row LED matrix visualizer.
    Channels correspond to active download workers / chunk streams.
    """

    NUM_COLUMNS = 16
    NUM_ROWS = 7
    COLOR_LIT = "#19f3ee"       # Neon Cyan glow
    COLOR_LIT_TOP = "#5ffbf8"   # Slightly brighter top cap
    COLOR_UNLIT = "#16202c"     # Subtle dark slate
    COLOR_BORDER = "#1b2838"    # Block outline
    COLOR_BG = "#171f2a"        # Card background

    def __init__(self, parent: Any, height: int = 58, bg: str = COLOR_BG):
        self.parent = parent
        self.height = height
        self.bg = bg
        self._levels: List[float] = [0.0] * self.NUM_COLUMNS
        self._target_levels: List[float] = [0.0] * self.NUM_COLUMNS
        self._animating = False
        self._anim_job: Optional[Any] = None

        if tk is not None:
            self.canvas = tk.Canvas(
                parent,
                height=self.height,
                bg=self.bg,
                bd=0,
                highlightthickness=0,
                relief="flat"
            )
            self.canvas.bind("<Configure>", lambda e: self.redraw())
        else:
            self.canvas = None  # type: ignore

    def pack(self, **kwargs):
        if self.canvas:
            self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        if self.canvas:
            self.canvas.grid(**kwargs)

    def set_levels(self, levels: List[float]):
        """Sets the 16 channel levels (values from 0.0 to 1.0)."""
        new_levels = list(levels)
        if len(new_levels) < self.NUM_COLUMNS:
            new_levels.extend([0.0] * (self.NUM_COLUMNS - len(new_levels)))
        self._target_levels = [max(0.0, min(1.0, float(v))) for v in new_levels[:self.NUM_COLUMNS]]
        self._levels = list(self._target_levels)
        self.redraw()

    def update_from_chunks(self, chunks: List[Any], active_count: int = 0, is_active: bool = True):
        """Derives 16-channel levels from chunks snapshot."""
        if not is_active or not chunks:
            # Idle gentle baseline or zero
            self.set_levels([0.0] * self.NUM_COLUMNS)
            return

        levels = [0.0] * self.NUM_COLUMNS
        total_chunks = len(chunks)

        for i in range(self.NUM_COLUMNS):
            if i < total_chunks:
                chunk = chunks[i]
                try:
                    span = max(1, getattr(chunk, "end_byte", 1) - getattr(chunk, "start_byte", 0) + 1)
                    dl = getattr(chunk, "downloaded_bytes", 0)
                    pct = dl / span
                    status = getattr(chunk, "status", "")
                    if status == "completed":
                        levels[i] = 1.0
                    elif status == "downloading":
                        # Active stream: minimum height 2/7, plus progress + minor pulse
                        levels[i] = max(0.3, min(1.0, pct + random.uniform(0.05, 0.2)))
                    else:
                        levels[i] = min(0.9, pct)
                except Exception:
                    levels[i] = 0.2
            elif active_count > 0 and i < active_count:
                levels[i] = random.uniform(0.4, 0.9)
            else:
                levels[i] = 0.0

        self.set_levels(levels)

    def redraw(self):
        """Draws the 16 columns of 7 LEDs on the canvas."""
        if not self.canvas or not self.canvas.winfo_exists():
            return

        w = self.canvas.winfo_width()
        if w <= 10:
            w = 280
        h = self.canvas.winfo_height()
        if h <= 10:
            h = self.height

        self.canvas.delete("all")

        # 16 columns arranged as 8 pairs
        num_pairs = 8
        cols_per_pair = 2
        inter_pair_gap = 5.0
        intra_pair_gap = 2.0
        v_gap = 2.0
        top_margin = 3.0
        bottom_margin = 3.0

        available_h = h - (top_margin + bottom_margin)
        block_h = max(3.0, (available_h - (self.NUM_ROWS - 1) * v_gap) / self.NUM_ROWS)

        # Total horizontal gaps = 7 * inter_pair_gap + 8 * intra_pair_gap
        total_gap_w = (num_pairs - 1) * inter_pair_gap + num_pairs * intra_pair_gap
        block_w = max(4.0, (w - total_gap_w) / self.NUM_COLUMNS)
        start_x = max(0.0, (w - (self.NUM_COLUMNS * block_w + total_gap_w)) / 2.0)

        cur_x = start_x
        for pair_idx in range(num_pairs):
            for c_in_pair in range(cols_per_pair):
                col_idx = pair_idx * cols_per_pair + c_in_pair
                level = self._levels[col_idx] if col_idx < len(self._levels) else 0.0
                lit_count = int(round(level * self.NUM_ROWS))
                if level > 0.05 and lit_count == 0:
                    lit_count = 1

                for row_idx in range(self.NUM_ROWS):
                    # row 0 is top, row 6 is bottom. LEDs light up from bottom to top!
                    inv_row = (self.NUM_ROWS - 1) - row_idx
                    is_lit = inv_row < lit_count

                    y0 = top_margin + row_idx * (block_h + v_gap)
                    y1 = y0 + block_h
                    x0 = cur_x
                    x1 = cur_x + block_w

                    color = self.COLOR_LIT if is_lit else self.COLOR_UNLIT
                    if is_lit and inv_row == lit_count - 1 and lit_count > 1:
                        color = self.COLOR_LIT_TOP

                    self.canvas.create_rectangle(
                        x0, y0, x1, y1,
                        fill=color,
                        outline=self.COLOR_BORDER,
                        width=1
                    )

                if c_in_pair == 0:
                    cur_x += block_w + intra_pair_gap
                else:
                    cur_x += block_w
                    if pair_idx < num_pairs - 1:
                        cur_x += inter_pair_gap


__all__ = ["LedEqualizerMatrix"]
