"""
Rounded Frosted Glass Canvas Container for Faqih Downloader.
"""
from __future__ import annotations

import sys
from typing import Any, Optional, Tuple

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from .canvas_shapes import draw_rounded_rect as _local_draw_rounded_rect, draw_glow_border as _local_draw_glow_border


def _get_draw_rounded_rect():
    mod = sys.modules.get("faqih_downloader.utils.window_effects")
    if mod and hasattr(mod, "draw_rounded_rect"):
        return getattr(mod, "draw_rounded_rect")
    return _local_draw_rounded_rect


def _get_draw_glow_border():
    mod = sys.modules.get("faqih_downloader.utils.window_effects")
    if mod and hasattr(mod, "draw_glow_border"):
        return getattr(mod, "draw_glow_border")
    return _local_draw_glow_border


_BaseCanvas = tk.Canvas if tk is not None else object


class RoundedGlassCard(_BaseCanvas):
    """
    A Tkinter Canvas container that renders a rounded frosted glass background
    (with optional multi-layer neon glowing border and hover glow) and embeds
    an inner Tkinter Frame to hold children cleanly.
    """

    def __init__(
        self,
        parent: Any,
        radius: float = 12,
        bg: str = "#0b0e14",
        card_bg: str = "#151a24",
        border_color: str = "#252b3b",
        glow_color: Optional[str] = None,
        glow_layers: int = 2,
        height: int = 100,
        inner_padx: int = 12,
        inner_pady: int = 10,
        width: Optional[int] = None,
        **kwargs
    ):
        if tk is not None:
            self.radius = radius
            self.card_bg = card_bg
            self.border_color = border_color
            self.glow_color = glow_color
            self.glow_layers = glow_layers
            self.inner_padx = inner_padx
            self.inner_pady = inner_pady
            self._explicit_width = width
            self._is_hovered = False
            self._orig_border_color = border_color
            self._orig_glow_color = glow_color
            self._last_size = None
            self._last_drawn_state = None

            # Avoid default 378px canvas width when width is not explicitly specified
            init_w = width if width is not None else 10
            super().__init__(parent, bg=bg, width=init_w, height=height, bd=0, highlightthickness=0, **kwargs)
            self.pack_propagate(False)
            self.grid_propagate(False)

            pad_x = max(inner_padx, 3)
            pad_y = max(inner_pady, 3)
            self.inner = tk.Frame(self, bg=card_bg)
            self.inner.pack(fill=tk.BOTH, expand=True, padx=pad_x, pady=pad_y)
            self.bind("<Configure>", self._on_resize)
            self.bind("<Enter>", self._on_card_enter, add="+")
            self.bind("<Leave>", self._on_card_leave, add="+")
            self.inner.bind("<Enter>", self._on_card_enter, add="+")
            self.inner.bind("<Leave>", self._on_card_leave, add="+")
            if width is None:
                self.inner.bind("<Configure>", self._on_inner_resize)
                req_w = self.inner.winfo_reqwidth() + pad_x * 2
                if req_w > 10:
                    self.configure(width=req_w)
        else:
            self.inner = None  # type: ignore

    def _is_pointer_inside(self, x_root: int, y_root: int) -> bool:
        try:
            target = self.winfo_containing(x_root, y_root)
            curr = target
            while curr is not None:
                if curr == self:
                    return True
                curr = getattr(curr, "master", None)
        except Exception:
            pass
        return False

    def _on_card_enter(self, event=None):
        if not self._is_hovered:
            self._is_hovered = True
            if not self._orig_glow_color:
                self.border_color = "#38bdf8"
                self._on_resize()

    def _on_card_leave(self, event=None):
        if event is not None and getattr(event, "x_root", None) is not None:
            if self._is_pointer_inside(event.x_root, event.y_root):
                return
        self._is_hovered = False
        if not self._orig_glow_color:
            self.border_color = self._orig_border_color
            self._on_resize()

    def _on_inner_resize(self, event=None):
        if self._explicit_width is None and getattr(self, "winfo_exists", lambda: False)():
            if self.winfo_width() <= 20:
                pad_x = max(self.inner_padx, 3)
                req_w = self.inner.winfo_reqwidth() + pad_x * 2
                if req_w > 10 and int(self.cget("width") or 0) != int(req_w):
                    self.configure(width=req_w)
            else:
                try:
                    self.inner.unbind("<Configure>")
                except Exception:
                    pass

    def _draw_card_bg(self, w: int, h: int, state_sig: Optional[Tuple] = None):
        if not getattr(self, "winfo_exists", lambda: False)():
            return
        if state_sig is None:
            b_curr = "#38bdf8" if (self._is_hovered and not self._orig_glow_color) else self.border_color
            state_sig = (w, h, b_curr, self.glow_color, self.card_bg)
        pad = 2
        top = None
        try:
            top = self.winfo_toplevel()
        except Exception:
            pass
        if top and getattr(top, "_is_resizing_window", False) and self._explicit_width is None:
            outline_col = self.glow_color or state_sig[2]
            w_line = 2 if self.glow_color else 1
            fast_rect = getattr(self, "_fast_resize_rect", None)
            if fast_rect is not None:
                try:
                    self.coords(fast_rect, pad, pad, w - pad, h - pad)
                    self._last_drawn_state = None
                    return
                except Exception:
                    self._fast_resize_rect = None
            self.delete("card_bg")
            self._fast_resize_rect = self.create_rectangle(
                pad, pad, w - pad, h - pad,
                fill=self.card_bg, outline=outline_col, width=w_line, tags="card_bg"
            )
            try:
                self.tag_lower(self._fast_resize_rect)
            except Exception:
                pass
            self._last_drawn_state = None
            return

        self._fast_resize_rect = None
        self.delete("card_bg")

        if self.glow_color:
            _draw_gb = _get_draw_glow_border()
            _draw_gb(
                self, pad + 1, pad + 1, w - pad - 1, h - pad - 1,
                radius=self.radius, glow_color=self.glow_color, glow_layers=self.glow_layers,
                inner_fill=self.card_bg, tags="card_bg"
            )
        else:
            b_col = state_sig[2]
            _draw_rr = _get_draw_rounded_rect()
            _draw_rr(
                self, pad, pad, w - pad, h - pad,
                radius=self.radius, fill=self.card_bg, outline=b_col, width=1, tags="card_bg"
            )
        self.tag_lower("card_bg")
        self._last_drawn_state = state_sig

    def _on_resize(self, event=None):
        if not getattr(self, "winfo_exists", lambda: False)():
            return
        w = event.width if (event is not None and getattr(event, "width", 0) > 1) else self.winfo_width()
        h = event.height if (event is not None and getattr(event, "height", 0) > 1) else self.winfo_height()
        if w < 10 or h < 10:
            return
        b_curr = "#38bdf8" if (self._is_hovered and not self._orig_glow_color) else self.border_color
        last_state = getattr(self, "_last_drawn_state", None)
        if (w, h) == getattr(self, "_last_size", None) and last_state is not None and len(last_state) >= 3 and b_curr == last_state[2]:
            return
        self._last_size = (w, h)
        state_sig = (w, h, b_curr, self.glow_color, self.card_bg)
        if state_sig == last_state:
            return
        self._draw_card_bg(w, h, state_sig)
