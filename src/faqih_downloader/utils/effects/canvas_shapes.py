"""
Smooth rounded rectangle and glowing border Canvas drawing helpers for Faqih Downloader.
"""
from __future__ import annotations

import sys
from typing import Any, Optional


def _get_draw_rounded_rect():
    mod = sys.modules.get("faqih_downloader.utils.window_effects")
    if mod and hasattr(mod, "draw_rounded_rect"):
        return getattr(mod, "draw_rounded_rect")
    return draw_rounded_rect


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

    _draw_rr = _get_draw_rounded_rect()

    # Outer soft glow layer
    for i in range(glow_layers, 0, -1):
        pad = float(i)
        _draw_rr(
            canvas,
            x1 - pad, y1 - pad, x2 + pad, y2 + pad,
            radius=radius + pad,
            outline=glow_color,
            fill="",
            width=1,
            tags=tags
        )

    # Primary inner rounded box
    _draw_rr(
        canvas,
        x1, y1, x2, y2,
        radius=radius,
        outline=glow_color,
        fill=inner_fill,
        width=2,
        tags=tags
    )
