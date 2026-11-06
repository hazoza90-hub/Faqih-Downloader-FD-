"""
ArcSpinnerCanvas: Circular glowing arc spinner widget for parsing / pending cards in Smart Download (SD).
"""
from __future__ import annotations

import math
from typing import Optional, Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore


class ArcSpinnerCanvas:
    """Renders a smooth circular arc spinner with animated rotation or static ring."""

    COLOR_ACTIVE = "#19f3ee"     # Neon Cyan
    COLOR_DIM = "#253040"        # Muted Slate
    COLOR_TRACK = "#1a2230"      # Track ring

    def __init__(
        self,
        parent: Any,
        size: int = 36,
        bg: str = "#1c1f29",
        mode: str = "active",
        line_width: int = 3
    ):
        self.parent = parent
        self.size = size
        self.bg = bg
        self.mode = mode
        self.line_width = line_width
        self._angle = 0
        self._anim_job: Optional[Any] = None
        self._is_running = False

        if tk is not None:
            self.canvas = tk.Canvas(
                parent,
                width=self.size,
                height=self.size,
                bg=self.bg,
                bd=0,
                highlightthickness=0,
                relief="flat"
            )
            self.redraw()
            if self.mode == "active":
                self.start()
        else:
            self.canvas = None  # type: ignore

    def pack(self, **kwargs):
        if self.canvas:
            self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        if self.canvas:
            self.canvas.grid(**kwargs)

    def set_mode(self, mode: str):
        """Switches between 'active' (spinning neon arc) and 'dim' (static ring)."""
        self.mode = mode
        if mode == "active":
            self.start()
        else:
            self.stop()
            self.redraw()

    def start(self):
        """Starts smooth arc rotation."""
        if self._is_running:
            return
        self._is_running = True
        self._animate()

    def stop(self):
        """Stops arc animation."""
        self._is_running = False
        if self._anim_job and self.canvas:
            try:
                self.canvas.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    def _animate(self):
        if not self._is_running or not self.canvas or not self.canvas.winfo_exists():
            self._is_running = False
            return
        self._angle = (self._angle + 16) % 360
        self.redraw()
        try:
            self._anim_job = self.canvas.after(45, self._animate)
        except Exception:
            self._is_running = False

    def redraw(self):
        if not self.canvas or not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")

        pad = self.line_width + 2
        x0 = pad
        y0 = pad
        x1 = self.size - pad
        y1 = self.size - pad

        if self.mode == "active":
            # Track ring
            self.canvas.create_oval(
                x0, y0, x1, y1,
                outline=self.COLOR_TRACK,
                width=self.line_width
            )
            # Glowing spinning arc (100 degrees span)
            self.canvas.create_arc(
                x0, y0, x1, y1,
                start=self._angle,
                extent=100,
                style=tk.ARC,
                outline=self.COLOR_ACTIVE,
                width=self.line_width
            )
        else:
            # Dim static ring
            self.canvas.create_oval(
                x0, y0, x1, y1,
                outline=self.COLOR_DIM,
                width=self.line_width
            )


__all__ = ["ArcSpinnerCanvas"]
