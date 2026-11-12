"""
LedEqualizerMatrix: Dynamic Turbo Stream Lanes visualizer widget for Smart Download (SD).
Visualizes multi-threaded download chunk activity and connection progress in real-time.
"""
from __future__ import annotations

from typing import List, Optional, Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore


class LedEqualizerMatrix:
    """
    Renders dynamic rectangular Turbo Stream Lanes matching download connection count (1..32).
    Lanes correspond to active download workers / chunk streams.
    """

    NUM_COLUMNS = 16
    NUM_ROWS = 7
    COLOR_LIT = "#19f3ee"       # Neon Cyan glow
    COLOR_LIT_TOP = "#5ffbf8"   # Glowing top cap
    COLOR_UNLIT = "#16202c"     # Subtle dark slate
    COLOR_BORDER = "#1b2838"    # Block outline
    COLOR_BG = "#171f2a"        # Card background

    def __init__(self, parent: Any, height: int = 58, bg: str = COLOR_BG):
        self.parent = parent
        self.height = height
        self.bg = bg
        self._lane_count: int = 8
        self._levels: List[float] = [0.0] * self.NUM_COLUMNS
        self._target_levels: List[float] = [0.0] * self.NUM_COLUMNS
        self._lane_statuses: List[str] = ["idle"] * self.NUM_COLUMNS
        self._animating = False
        self._anim_job: Optional[Any] = None
        self._last_canvas_size: Optional[Tuple[int, int]] = None
        self._resize_redraw_job: Optional[Any] = None

        if tk is not None:
            self.canvas = tk.Canvas(
                parent,
                height=self.height,
                bg=self.bg,
                bd=0,
                highlightthickness=0,
                relief="flat"
            )
            self.canvas.bind("<Configure>", self._on_canvas_configure)
        else:
            self.canvas = None  # type: ignore

    def _flush_canvas_redraw(self):
        self._resize_redraw_job = None
        if not self.canvas or not getattr(self.canvas, "winfo_exists", lambda: False)():
            return
        self.redraw()

    def _on_canvas_configure(self, event):
        if not self.canvas or not getattr(self.canvas, "winfo_exists", lambda: False)():
            return
        w = getattr(event, "width", 0)
        h = getattr(event, "height", 0)
        if (w, h) == getattr(self, "_last_canvas_size", None):
            return

        top = None
        try: top = self.canvas.winfo_toplevel()
        except Exception: pass
        if top and getattr(top, "_is_resizing_window", False):
            if getattr(self, "_resize_redraw_job", None) is None:
                self._resize_redraw_job = self.canvas.after(16, self._flush_canvas_redraw)
        else:
            if getattr(self, "_resize_redraw_job", None) is not None:
                try: self.canvas.after_cancel(self._resize_redraw_job)
                except Exception: pass
                self._resize_redraw_job = None
            self.redraw()

    def pack(self, **kwargs):
        if self.canvas:
            self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        if self.canvas:
            self.canvas.grid(**kwargs)

    def set_levels(self, levels: List[float]):
        """Sets channel levels (values from 0.0 to 1.0)."""
        self._levels = [max(0.0, min(1.0, float(v))) for v in levels]
        self._target_levels = list(self._levels)
        self._lane_count = max(1, len(self._levels))
        self._lane_statuses = ["active" if v > 0 else "idle" for v in self._levels]
        self.redraw()

    def update_from_chunks(self, chunks: List[Any], active_count: int = 0, is_active: bool = True, max_lanes: int = 0):
        """Derives dynamic rectangular Turbo Stream Lanes from chunks snapshot."""
        safe_ml = 0
        if isinstance(max_lanes, (int, str)) and not isinstance(max_lanes, bool):
            s = str(max_lanes).strip()
            if s.isdigit(): safe_ml = int(s)

        if not is_active or (not chunks and active_count <= 0):
            if safe_ml > 0:
                self._lane_count = max(1, min(32, safe_ml))
            else:
                self._lane_count = max(1, min(32, len(chunks) if chunks else (active_count if active_count > 0 else self._lane_count)))
            self._levels = [0.0] * self._lane_count
            self._target_levels = [0.0] * self._lane_count
            self._lane_statuses = ["idle"] * self._lane_count
            self.redraw()
            return

        if safe_ml > 0:
            n_lanes = max(1, min(32, safe_ml))
        elif chunks:
            n_lanes = max(1, min(32, len(chunks)))
        else:
            n_lanes = max(1, min(32, active_count if active_count > 0 else self._lane_count))

        if chunks:
            if len(chunks) <= n_lanes:
                if len(chunks) < n_lanes:
                    n_lanes = len(chunks)
                levels = [0.0] * n_lanes
                statuses = ["pending"] * n_lanes
                for i in range(n_lanes):
                    chunk = chunks[i]
                    span = max(1, getattr(chunk, "end_byte", 1) - getattr(chunk, "start_byte", 0) + 1)
                    dl = max(0, getattr(chunk, "downloaded_bytes", 0))
                    pct = max(0.0, min(1.0, dl / span))
                    st = str(getattr(chunk, "status", "")).lower()
                    if st == "completed" or pct >= 0.999:
                        levels[i] = 1.0
                        statuses[i] = "completed"
                    elif st in ("active", "downloading"):
                        levels[i] = max(0.08, min(1.0, pct))
                        statuses[i] = "active"
                    else:
                        levels[i] = pct
                        statuses[i] = st or "pending"
            else:
                # len(chunks) > n_lanes: aggregate into n_lanes buckets
                levels = [0.0] * n_lanes
                statuses = ["pending"] * n_lanes
                b_dl = [0.0] * n_lanes
                b_span = [0.0] * n_lanes
                b_has_active = [False] * n_lanes
                b_all_completed = [True] * n_lanes
                for i, chunk in enumerate(chunks):
                    b_idx = min(n_lanes - 1, (i * n_lanes) // len(chunks))
                    span = max(1, getattr(chunk, "end_byte", 1) - getattr(chunk, "start_byte", 0) + 1)
                    dl = max(0, getattr(chunk, "downloaded_bytes", 0))
                    b_dl[b_idx] += dl
                    b_span[b_idx] += span
                    st = str(getattr(chunk, "status", "")).lower()
                    if st in ("active", "downloading"):
                        b_has_active[b_idx] = True
                    if st != "completed" and dl < span:
                        b_all_completed[b_idx] = False

                for b in range(n_lanes):
                    span_val = max(1.0, b_span[b])
                    pct = max(0.0, min(1.0, b_dl[b] / span_val))
                    if b_all_completed[b] or pct >= 0.999:
                        levels[b] = 1.0
                        statuses[b] = "completed"
                    elif b_has_active[b]:
                        levels[b] = max(0.08, min(1.0, pct))
                        statuses[b] = "active"
                    else:
                        levels[b] = pct
                        statuses[b] = "pending"
        else:
            levels = [0.5 if i < active_count else 0.0 for i in range(n_lanes)]
            statuses = ["active" if i < active_count else "pending" for i in range(n_lanes)]

        self._lane_count = n_lanes
        self._levels = levels
        self._target_levels = list(levels)
        self._lane_statuses = statuses
        self.redraw()

    def redraw(self):
        """Draws dynamic rectangular Turbo Stream Lanes distributed across the canvas."""
        if not self.canvas or not self.canvas.winfo_exists():
            return

        w = self.canvas.winfo_width()
        if w <= 10:
            w = 280
        h = self.canvas.winfo_height()
        if h <= 10:
            h = self.height
        self._last_canvas_size = (w, h)

        self.canvas.delete("all")

        n = max(1, len(self._levels))
        gap = 6.0 if n <= 4 else (4.0 if n <= 8 else (2.5 if n <= 16 else 1.5))
        top_margin, bottom_margin = 4.0, 4.0
        left_margin, right_margin = 6.0, 6.0

        avail_w = max(10.0, w - left_margin - right_margin - (n - 1) * gap)
        lane_w = max(3.0, avail_w / n)
        lane_h = max(10.0, h - top_margin - bottom_margin)

        for i in range(n):
            x0 = left_margin + i * (lane_w + gap)
            x1 = x0 + lane_w
            y0 = top_margin
            y1 = y0 + lane_h

            status = self._lane_statuses[i] if i < len(self._lane_statuses) else "pending"
            level = self._levels[i] if i < len(self._levels) else 0.0

            if status == "active":
                bd_color = "#19f3ee"
            elif status == "completed":
                bd_color = "#10b981"
            else:
                bd_color = "#1e293b"

            # Outer lane rectangle with dark cyber-slate background
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                fill="#111822",
                outline=bd_color,
                width=1
            )

            # Inside lane, fill from bottom to top
            pad = 2.0
            inner_h = max(0.0, lane_h - 2 * pad)
            inner_w = max(0.0, lane_w - 2 * pad)
            fill_h = max(0.0, min(inner_h, level * inner_h))

            if fill_h > 0 and inner_w > 0:
                fy1 = y1 - pad
                fy0 = fy1 - fill_h
                fx0 = x0 + pad
                fx1 = x1 - pad

                body_color = "#10b981" if status == "completed" else "#0284c7"
                self.canvas.create_rectangle(
                    fx0, fy0, fx1, fy1,
                    fill=body_color,
                    outline="",
                    width=0
                )

                # Glowing top cap (3px) when active or completed
                if fill_h >= 3.0:
                    cap_color = "#10b981" if status == "completed" else "#19f3ee"
                    self.canvas.create_rectangle(
                        fx0, fy0, fx1, min(fy1, fy0 + 3.0),
                        fill=cap_color,
                        outline="",
                        width=0
                    )

            # Overlay subtle horizontal grid lines every 7px across lane
            grid_y = y0 + pad + 7.0
            while grid_y < y1 - pad:
                self.canvas.create_line(
                    x0 + pad, grid_y, x1 - pad, grid_y,
                    fill="#151a24",
                    width=1
                )
                grid_y += 7.0

            # Lane percentage text when n <= 8 and lane_w >= 26
            if n <= 8 and lane_w >= 26:
                txt = f"{int(round(level * 100))}%" if level > 0 else f"#{i+1}"
                self.canvas.create_text(
                    (x0 + x1) / 2.0,
                    (y0 + y1) / 2.0,
                    text=txt,
                    fill="#e2e8f0",
                    font=("Segoe UI", 7, "bold")
                )


__all__ = ["LedEqualizerMatrix"]
