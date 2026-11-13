"""
WindowResizeMixin: 8-edge & corner resizing grips and border drag handlers for frameless window.
"""
from __future__ import annotations

from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore


class WindowResizeMixin:
    """Provides 8-edge & corner resizing grips and drag-to-resize handlers for frameless windows."""

    def _setup_resizing(self):
        """Initializes 8 edge & corner resize grips on the frameless root window."""
        if not hasattr(self, "root") or not self.root or tk is None:
            return
        try:
            self._resize_grips = []
            grip_configs = [
                ("nw", "size_nw_se", {"x": 0, "y": 0, "width": 8, "height": 8}),
                ("ne", "size_ne_sw", {"relx": 1.0, "x": -8, "y": 0, "width": 8, "height": 8}),
                ("sw", "size_ne_sw", {"x": 0, "rely": 1.0, "y": -8, "width": 8, "height": 8}),
                ("se", "size_nw_se", {"relx": 1.0, "x": -10, "rely": 1.0, "y": -10, "width": 10, "height": 10}),
                ("n",  "size_ns",    {"x": 8, "y": 0, "relwidth": 1.0, "width": -16, "height": 5}),
                ("s",  "size_ns",    {"x": 8, "rely": 1.0, "y": -5, "relwidth": 1.0, "width": -16, "height": 5}),
                ("w",  "size_we",    {"x": 0, "y": 8, "width": 5, "relheight": 1.0, "height": -16}),
                ("e",  "size_we",    {"relx": 1.0, "x": -5, "y": 8, "width": 5, "relheight": 1.0, "height": -16}),
            ]
            border_color = getattr(self, "c_border", "#2a2d32")
            for mode, cursor_name, place_kwargs in grip_configs:
                grip = tk.Frame(self.root, bg=border_color, cursor=cursor_name)
                grip.bind("<ButtonPress-1>", lambda e, m=mode: self._on_resize_press(e, m))
                grip.bind("<B1-Motion>", self._on_resize_drag)
                grip.bind("<ButtonRelease-1>", self._on_resize_release)
                grip.place(**place_kwargs)
                grip.lift()
                self._resize_grips.append((grip, place_kwargs))
        except Exception:
            pass

    def _lift_resize_grips(self):
        """Ensures all 8 resize grips stay above all container frames."""
        for g, _ in getattr(self, "_resize_grips", []):
            try:
                g.lift()
            except Exception:
                pass

    def _hide_resize_grips(self):
        """Temporarily hides resize grips when maximized."""
        for g, _ in getattr(self, "_resize_grips", []):
            try:
                g.place_forget()
            except Exception:
                pass

    def _show_resize_grips(self):
        """Restores resize grips when unmaximized."""
        for g, pk in getattr(self, "_resize_grips", []):
            try:
                g.place(**pk)
                g.lift()
            except Exception:
                pass

    def _hide_offscreen_vault_cards(self):
        """Temporarily unpacks off-viewport vault cards (>6 visible) to cut Win32 TkChild HWND moves during drag."""
        self._resize_hidden_vault_cards = []
        self._resize_vault_pack_meta = []
        cont = getattr(self, "vault_cards_container", None)
        if not cont or not getattr(cont, "winfo_exists", lambda: False)():
            return
        try:
            children = list(cont.winfo_children())
            if len(children) <= 6:
                return
            cv = getattr(self, "vault_cards_canvas", None)
            visible_indices = []
            if cv and getattr(cv, "winfo_exists", lambda: False)() and cv.winfo_height() > 20:
                top_y = float(cv.canvasy(0))
                bot_y = float(cv.canvasy(cv.winfo_height()))
                for idx, ch in enumerate(children):
                    cy, ch_h = ch.winfo_y(), max(1, ch.winfo_height())
                    if (cy + ch_h) >= top_y and cy <= bot_y:
                        visible_indices.append(idx)
                        if len(visible_indices) >= 6:
                            break
            keep_set = set(visible_indices) if visible_indices else set(range(min(6, len(children))))
            for idx, ch in enumerate(children):
                if idx not in keep_set:
                    try:
                        info = ch.pack_info()
                        self._resize_vault_pack_meta.append((ch, {"fill": info.get("fill", tk.X), "pady": info.get("pady", (0, 8)), "padx": info.get("padx", 0)}, children[idx + 1] if idx + 1 < len(children) else None))
                        ch.pack_forget()
                        self._resize_hidden_vault_cards.append(ch)
                    except Exception:
                        pass
        except Exception:
            pass

    def _restore_offscreen_vault_cards(self) -> bool:
        """Restores temporarily hidden vault cards in exact original stacking order."""
        meta = getattr(self, "_resize_vault_pack_meta", None) or []
        hidden = getattr(self, "_resize_hidden_vault_cards", None) or []
        if not meta and not hidden:
            return False
        if meta:
            for ch, pk, nxt in reversed(meta):
                try:
                    if not ch.winfo_exists():
                        continue
                    if nxt is not None and nxt.winfo_exists() and nxt.winfo_manager() == "pack":
                        ch.pack(before=nxt, **pk)
                    else:
                        ch.pack(**pk)
                except Exception:
                    pass
        else:
            for ch in hidden:
                try:
                    if ch.winfo_exists():
                        ch.pack(fill=tk.X, pady=(0, 8))
                except Exception:
                    pass
        self._resize_hidden_vault_cards = []
        self._resize_vault_pack_meta = []
        return True

    def _apply_resize_geometry(self, w: int, h: int, x: int, y: int):
        if (w, h, x, y) == getattr(self, "_last_resize_geo", None):
            return
        if getattr(self, "_in_resize_update", False):
            self._pending_resize_geo = (w, h, x, y)
            return
        self._in_resize_update = True
        try:
            self._last_resize_geo = (w, h, x, y)
            geo = self._format_geometry(w, h, x, y)
            self.root.geometry(geo)
            try:
                self.root.update()
            except Exception:
                pass
            v_cv = getattr(self, "vault_cards_canvas", None)
            if v_cv is not None:
                try:
                    if v_cv.winfo_exists():
                        cv_w = v_cv.winfo_width()
                        win_id = getattr(v_cv, "_win_id", None)
                        if cv_w > 10 and win_id is not None:
                            v_cv.itemconfigure(win_id, width=cv_w)
                except Exception:
                    pass
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            self._normal_geometry = geo
            self.width, self.height = w, h
        finally:
            self._in_resize_update = False

    def _flush_pending_resize(self):
        self._resize_flush_job = None
        pending = getattr(self, "_pending_resize_geo", None)
        self._pending_resize_geo = None
        if not pending or getattr(self, "_is_maximized", False):
            return
        import time
        self._last_resize_ts = time.perf_counter()
        self._apply_resize_geometry(*pending)

    def _on_resize_press(self, event, mode: str):
        if getattr(self, "_is_maximized", False):
            return "break"
        try:
            if hasattr(self, "root") and self.root:
                self.root._is_resizing_window = True
        except Exception:
            pass
        self._hide_offscreen_vault_cards()
        try:
            win_w, win_h = self.root.winfo_width(), self.root.winfo_height()
            win_x, win_y = self.root.winfo_x(), self.root.winfo_y()
            if win_w <= 1 or win_h <= 1:
                norm_geo = getattr(self, "_normal_geometry", "")
                if norm_geo and "x" in norm_geo:
                    try:
                        w_p, rest = norm_geo.split("x", 1)
                        win_w = int(w_p)
                        pts = rest.replace("-", "+-").split("+")
                        win_h = int(pts[0])
                        if len(pts) >= 3:
                            win_x, win_y = int(pts[1]), int(pts[2])
                    except Exception:
                        win_w, win_h = getattr(self, "width", 850), getattr(self, "height", 650)
                else:
                    win_w, win_h = getattr(self, "width", 850), getattr(self, "height", 650)
            self._resize_state = {
                "mode": mode,
                "x_root": event.x_root,
                "y_root": event.y_root,
                "win_x": win_x,
                "win_y": win_y,
                "win_w": win_w,
                "win_h": win_h,
            }
        except Exception:
            pass
        return "break"

    def _on_resize_drag(self, event):
        if getattr(self, "_is_maximized", False):
            return "break"
        mode = getattr(self, "_resize_state", {}).get("mode")
        if not mode:
            return "break"

        import time
        now = time.perf_counter()
        try:
            dx = event.x_root - self._resize_state["x_root"]
            dy = event.y_root - self._resize_state["y_root"]
            w, h = self._resize_state["win_w"], self._resize_state["win_h"]
            x, y = self._resize_state["win_x"], self._resize_state["win_y"]
            min_w = getattr(self, "_min_width", 820)
            min_h = getattr(self, "_min_height", 620)

            if "e" in mode:
                w = max(min_w, w + dx)
            if "s" in mode:
                h = max(min_h, h + dy)
            if "w" in mode:
                new_w = max(min_w, w - dx)
                x, w = x + (w - new_w), new_w
            if "n" in mode:
                new_h = max(min_h, h - dy)
                y, h = y + (h - new_h), new_h

            if (w, h, x, y) == getattr(self, "_last_resize_geo", None):
                return "break"
            if getattr(self, "_in_resize_update", False):
                self._pending_resize_geo = (w, h, x, y)
                return "break"
            if now - getattr(self, "_last_resize_ts", 0.0) < 0.014:
                self._pending_resize_geo = (w, h, x, y)
                if getattr(self, "_resize_flush_job", None) is None and hasattr(self, "root") and self.root:
                    self._resize_flush_job = self.root.after(14, self._flush_pending_resize)
                return "break"
            job = getattr(self, "_resize_flush_job", None)
            if job is not None and hasattr(self, "root") and self.root:
                try: self.root.after_cancel(job)
                except Exception: pass
                self._resize_flush_job = None
            self._pending_resize_geo = None
            self._last_resize_ts = now
            self._apply_resize_geometry(w, h, x, y)
        except Exception:
            pass
        return "break"

    def _on_resize_release(self, event=None):
        job = getattr(self, "_resize_flush_job", None)
        if job is not None and hasattr(self, "root") and self.root:
            try: self.root.after_cancel(job)
            except Exception: pass
            self._resize_flush_job = None
        pending = getattr(self, "_pending_resize_geo", None)
        self._pending_resize_geo = None
        if pending and not getattr(self, "_is_maximized", False):
            try: self._apply_resize_geometry(*pending)
            except Exception: pass

        try:
            if hasattr(self, "root") and self.root:
                self.root._is_resizing_window = False
        except Exception:
            pass

        if self._restore_offscreen_vault_cards() and hasattr(self, "root") and self.root:
            try: self.root.update_idletasks()
            except Exception: pass

        try:
            if hasattr(self, "root") and self.root:
                from faqih_downloader.utils.window_effects import RoundedGlassCard
                from faqih_downloader.ui.panels.kanban_card_graphics import draw_neon_progress_bar
                stack = [self.root]
                while stack:
                    curr = stack.pop()
                    if isinstance(curr, RoundedGlassCard):
                        curr._fast_resize_rect = None
                        curr._last_drawn_state = None
                        try: curr._on_resize(None)
                        except Exception: pass
                    if callable(getattr(curr, "_rerender_empty_state", None)):
                        curr._fast_rect = None
                        curr._last_size = None
                        try: curr._rerender_empty_state()
                        except Exception: pass
                    if hasattr(curr, "_prog_ratio"):
                        try: draw_neon_progress_bar(curr, curr._prog_ratio)
                        except Exception: pass
                    owner = getattr(curr, "_visualizer_owner", None)
                    if owner is not None and hasattr(owner, "redraw"):
                        try: owner.redraw()
                        except Exception: pass
                    try:
                        children = curr.winfo_children()
                        if children: stack.extend(children)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            if hasattr(self, "vault_cards_canvas") and self.vault_cards_canvas and self.vault_cards_canvas.winfo_exists():
                self.vault_cards_canvas.configure(scrollregion=self.vault_cards_canvas.bbox("all"))
        except Exception:
            pass

        if hasattr(self, "_resize_state"):
            self._resize_state.clear()
        self._last_resize_geo = None
        self._last_resize_ts = 0.0
        return "break"

    def _detect_resize_edge(self, x: int, y: int, width: int, height: int, threshold: int = 6) -> str:
        """Determines the resize edge direction ('n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se') for coordinate (x, y)."""
        edge = ""
        if y <= threshold:
            edge += "n"
        elif y >= height - threshold:
            edge += "s"
        if x <= threshold:
            edge += "w"
        elif x >= width - threshold:
            edge += "e"
        return edge

    def _cursor_for_edge(self, edge: str) -> str:
        return {
            "nw": "size_nw_se",
            "se": "size_nw_se",
            "ne": "size_ne_sw",
            "sw": "size_ne_sw",
            "w": "size_we",
            "e": "size_we",
            "n": "size_ns",
            "s": "size_ns",
        }.get(edge, "")

    def _setup_border_resizing(self, widget):
        """Binds border motion and drag events to main_border for edge resizing."""
        if not widget:
            return
        widget.bind("<Motion>", self._on_border_motion)
        widget.bind("<ButtonPress-1>", self._on_border_press)
        widget.bind("<B1-Motion>", self._on_resize_drag)
        widget.bind("<ButtonRelease-1>", self._on_resize_release)

    def _on_border_motion(self, event):
        if getattr(self, "_is_maximized", False):
            return
        w, h = self.root.winfo_width(), self.root.winfo_height()
        edge = self._detect_resize_edge(event.x, event.y, w, h, 6)
        event.widget.configure(cursor=self._cursor_for_edge(edge))

    def _on_border_press(self, event):
        if getattr(self, "_is_maximized", False):
            return "break"
        w, h = self.root.winfo_width(), self.root.winfo_height()
        edge = self._detect_resize_edge(event.x, event.y, w, h, 6)
        return self._on_resize_press(event, edge) if edge else "break"


__all__ = ["WindowResizeMixin"]
