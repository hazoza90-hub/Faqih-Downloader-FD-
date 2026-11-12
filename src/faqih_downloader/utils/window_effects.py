"""
Window effects and rounded glass Canvas styling for Smart Download (SD).
Provides:
1. Native Windows 10/11 Acrylic and Mica backdrop effects via DWM and Win32 APIs.
2. Smooth rounded rectangle drawing helpers for dark glass Canvas cards and buttons.
"""
from __future__ import annotations

import os
import sys
import ctypes
from typing import Any, Optional, Tuple, Sequence

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.services.startup_service import IS_WINDOWS


# ──────────────────────────────────────────────────────────────────────────────
# Windows Acrylic / Mica Win32 DWM Backdrop Integration
# ──────────────────────────────────────────────────────────────────────────────
def apply_acrylic_or_mica_effect(root: Any, alpha: float = 1.0) -> bool:
    """
    Enables Windows 11 / Windows 10 Dark Mode and rounded corners behind
    the frameless window. Eliminates ACCENT_ENABLE_ACRYLICBLURBEHIND for 60fps smooth resize.
    """
    if not root:
        return False

    clamped_alpha = max(0.60, min(1.0, float(alpha)))
    try:
        root.attributes("-alpha", clamped_alpha)
    except Exception:
        pass

    if not IS_WINDOWS:
        return True

    # Never apply DWM composition or Win32 backdrop effects to child Toplevels or modals
    if tk is not None and not isinstance(root, tk.Tk):
        return True

    # Apply Win32 DWM Backdrop Attributes on root window only
    try:
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.GetParent.restype = ctypes.c_void_p
        raw_id = root.winfo_id()
        hwnd = user32.GetParent(raw_id) or raw_id
        if not hwnd:
            return False

        # DWMWA_USE_IMMERSIVE_DARK_MODE (20 on Win11/Win10 20H1+, 19 on older builds)
        dark_mode = ctypes.c_int(1)
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
                )
            except Exception:
                pass

        # DWMWA_WINDOW_CORNER_PREFERENCE (33): 2 = DWMWCP_ROUND (Rounded window corners)
        corner_pref = ctypes.c_int(2)
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(corner_pref), ctypes.sizeof(corner_pref)
            )
        except Exception:
            pass

        return True
    except Exception:
        return False


def apply_window_opacity(root: Any, alpha: float = 1.0) -> bool:
    """Sets window opacity cleanly on root window."""
    if not root:
        return False
    try:
        root.attributes("-alpha", max(0.60, min(1.0, float(alpha))))
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Smooth Rounded Rectangle Canvas Drawing Helpers
# ──────────────────────────────────────────────────────────────────────────────
def draw_rounded_rect(
    canvas: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float = 10,
    **kwargs
) -> Optional[int]:
    """
    Draws a true rounded rectangle on a Tkinter Canvas using 4 corner arcs and 2 rectangles.
    """
    if not canvas or not getattr(canvas, "winfo_exists", lambda: False)():
        return None

    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return None

    r = max(1.0, min(float(radius), w / 2.0, h / 2.0))
    d = 2 * r

    fill = kwargs.get("fill")
    outline = kwargs.get("outline")
    border_width = int(kwargs.get("width", 1) or 1)
    tags = kwargs.get("tags", ())
    if isinstance(tags, str) and tags:
        tags = (tags,)
    elif not tags:
        tags = ()

    created_ids = []

    # 1. Fill interior
    if fill and fill != "" and str(fill).lower() != "none":
        tl_pie = canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90, style="pieslice", fill=fill, outline=fill, tags=tags)
        tr_pie = canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90, style="pieslice", fill=fill, outline=fill, tags=tags)
        br_pie = canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90, style="pieslice", fill=fill, outline=fill, tags=tags)
        bl_pie = canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90, style="pieslice", fill=fill, outline=fill, tags=tags)

        r_horiz = canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill, tags=tags)
        r_vert = canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill, tags=tags)
        created_ids.extend([tl_pie, tr_pie, br_pie, bl_pie, r_horiz, r_vert])

    # 2. Outline border
    if outline and outline != "" and str(outline).lower() != "none":
        tl_arc = canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90, style="arc", outline=outline, width=border_width, tags=tags)
        tr_arc = canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90, style="arc", outline=outline, width=border_width, tags=tags)
        br_arc = canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90, style="arc", outline=outline, width=border_width, tags=tags)
        bl_arc = canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90, style="arc", outline=outline, width=border_width, tags=tags)

        l_top = canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=border_width, tags=tags)
        l_right = canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=border_width, tags=tags)
        l_bottom = canvas.create_line(x2 - r, y2, x1 + r, y2, fill=outline, width=border_width, tags=tags)
        l_left = canvas.create_line(x1, y2 - r, x1, y1 + r, fill=outline, width=border_width, tags=tags)
        created_ids.extend([tl_arc, tr_arc, br_arc, bl_arc, l_top, l_right, l_bottom, l_left])

    return created_ids[0] if created_ids else None


def draw_glow_border(
    canvas: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float = 10,
    glow_color: str = "#19f3ee",
    glow_layers: int = 2,
    inner_fill: str = "#10151f",
    tags: str = "glow_frame"
):
    """
    Draws a multi-layered neon glow border with rounded corners.
    """
    if not canvas or not getattr(canvas, "winfo_exists", lambda: False)():
        return

    # Outer soft glow layer
    for i in range(glow_layers, 0, -1):
        pad = float(i)
        draw_rounded_rect(
            canvas,
            x1 - pad, y1 - pad, x2 + pad, y2 + pad,
            radius=radius + pad,
            outline=glow_color,
            fill="",
            width=1,
            tags=tags
        )

    # Primary inner rounded box
    draw_rounded_rect(
        canvas,
        x1, y1, x2, y2,
        radius=radius,
        outline=glow_color,
        fill=inner_fill,
        width=2,
        tags=tags
    )


# ──────────────────────────────────────────────────────────────────────────────
# Rounded Frosted Glass Canvas Container
# ──────────────────────────────────────────────────────────────────────────────
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
        try: top = self.winfo_toplevel()
        except Exception: pass
        if top and getattr(top, "_is_resizing_window", False):
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
            draw_glow_border(
                self, pad + 1, pad + 1, w - pad - 1, h - pad - 1,
                radius=self.radius, glow_color=self.glow_color, glow_layers=self.glow_layers,
                inner_fill=self.card_bg, tags="card_bg"
            )
        else:
            b_col = state_sig[2]
            draw_rounded_rect(
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
        self._last_size = (w, h)
        b_curr = "#38bdf8" if (self._is_hovered and not self._orig_glow_color) else self.border_color
        state_sig = (w, h, b_curr, self.glow_color, self.card_bg)
        if state_sig == getattr(self, "_last_drawn_state", None):
            return
        self._draw_card_bg(w, h, state_sig)


__all__ = [
    "apply_acrylic_or_mica_effect",
    "apply_window_opacity",
    "draw_rounded_rect",
    "draw_glow_border",
    "RoundedGlassCard",
]

