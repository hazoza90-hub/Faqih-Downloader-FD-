"""
KanbanActiveColumnMixin: Column 2 (Active Turbo Streams) management for Smart Download (SD).
Handles real-time active card updates, LED equalizer driving, pause/resume menu, and idle states.
"""
from __future__ import annotations

import os
from typing import Optional, Any, List, Dict

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import is_test_environment
from faqih_downloader.utils.window_effects import RoundedGlassCard
from faqih_downloader.ui.panels.kanban_cards import (
    create_empty_state,
    draw_neon_progress_bar,
    build_active_card_shell,
)


class KanbanActiveColumnMixin:
    """Provides dynamic Column 2 (Active Turbo Streams) lifecycle and rendering."""

    def _build_col2_active(self, parent: Any):
        """Constructs the active stream column shell with glowing cyan border and breathing indicator."""
        cyan_border = RoundedGlassCard(
            parent,
            radius=14,
            bg="#0b0e14",
            card_bg="#0f1520",
            glow_color="#19f3ee",
            glow_layers=2,
            inner_padx=6,
            inner_pady=6,
        )
        cyan_border.grid(row=0, column=1, sticky="nsew", padx=6)
        self.active_column_border = cyan_border

        inner_col = tk.Frame(cyan_border.inner, bg="#0f1520", padx=8, pady=8)
        inner_col.pack(fill=tk.BOTH, expand=True)

        # Header Row: "Active Turbo Streams (N)" on left, "● 0.0 MB/s" on right
        hdr = tk.Frame(inner_col, bg="#0f1520")
        hdr.pack(fill=tk.X, pady=(0, 10))

        self.lbl_col2_title = tk.Label(
            hdr,
            text=f"{tr('pipeline_col_active', 'Active Turbo Streams')} (0)",
            font=("Segoe UI", 10, "bold"),
            bg="#0f1520",
            fg="#f8fafc"
        )
        self.lbl_col2_title.pack(side=tk.LEFT)

        speed_box = tk.Frame(hdr, bg="#0f1520")
        speed_box.pack(side=tk.RIGHT)

        lbl_dot = tk.Label(speed_box, text="●", font=("Segoe UI", 9), bg="#0f1520", fg="#19f3ee")
        lbl_dot.pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_col2_dot = lbl_dot

        # Calm breathing pulse animation for neon indicator dot
        self._pulse_colors = ["#19f3ee", "#38bdf8", "#0284c7", "#0369a1", "#0284c7", "#38bdf8"]
        self._pulse_idx = 0
        def _breathe_pulse():
            if not getattr(self, "_closing", False) and getattr(lbl_dot, "winfo_exists", lambda: False)():
                self._pulse_idx = (self._pulse_idx + 1) % len(self._pulse_colors)
                lbl_dot.configure(fg=self._pulse_colors[self._pulse_idx])
                if not is_test_environment():
                    lbl_dot.after(400, _breathe_pulse)
        if not is_test_environment():
            lbl_dot.after(400, _breathe_pulse)

        self.lbl_col2_total_speed = tk.Label(
            speed_box,
            text="0.0 MB/s",
            font=("Segoe UI", 9, "bold"),
            bg="#0f1520",
            fg="#19f3ee"
        )
        self.lbl_col2_total_speed.pack(side=tk.LEFT)

        # Dynamic container for Active Stream card or Engine Ready state
        self.active_stream_body = tk.Frame(inner_col, bg="#0f1520")
        self.active_stream_body.pack(fill=tk.BOTH, expand=True)

        # Build live engine card widget shell as RoundedGlassCard
        self.card_active_1 = RoundedGlassCard(
            self.active_stream_body,
            radius=12,
            bg="#0f1520",
            card_bg="#151a24",
            border_color="#243242",
            height=148,
            inner_padx=12,
            inner_pady=10,
        )
        self._build_active_card_shell(self.card_active_1.inner)

    def _build_active_card_shell(self, card: Any):
        w = build_active_card_shell(card, self)
        self.lbl_a1_filename = w["lbl_filename"]
        self.btn_a1_pause = w.get("btn_pause")
        self.btn_a1_menu = w["btn_menu"]
        self.lbl_a1_pct = w["lbl_pct"]
        self.canvas_a1_prog = w["canvas_prog"]
        self.lbl_a1_speed = w["lbl_speed"]
        self.lbl_a1_size = w.get("lbl_size")
        self.lbl_a1_eta = w.get("lbl_eta")
        self.matrix_a1 = w["matrix"]

    def reset_kanban_active_stream(self):
        """Puts Column 2 in quiet 'Engine Ready' idle state with 0.0 MB/s and LEDs off."""
        self._active_stream_live = False
        self._last_active_pct = 0.0
        self._last_active_downloaded = 0
        self._last_active_total = 0
        if hasattr(self, "btn_a1_pause") and self.btn_a1_pause and self.btn_a1_pause.winfo_exists():
            self.btn_a1_pause.configure(text="⏸")
        if hasattr(self, "lbl_col2_title") and self.lbl_col2_title.winfo_exists():
            self.lbl_col2_title.configure(text=f"{tr('pipeline_col_active', 'Active Turbo Streams')} (0)")
        if hasattr(self, "lbl_col2_total_speed") and self.lbl_col2_total_speed.winfo_exists():
            self.lbl_col2_total_speed.configure(text="0.0 MB/s")

        if hasattr(self, "card_active_1") and self.card_active_1.winfo_exists():
            self.card_active_1.pack_forget()

        if hasattr(self, "empty_active_canvas") and self.empty_active_canvas.winfo_exists():
            try:
                self.empty_active_canvas.destroy()
            except Exception:
                pass

        self.empty_active_canvas = create_empty_state(
            self.active_stream_body,
            icon="⚡",
            title=tr("pipeline_empty_active", "Engine Ready"),
            subtitle=tr("status_ready", "Ready"),
            bg="#0f1520",
            card_bg="#151a24",
            border_color="#233042",
            glow_color=None,
            height=140
        )

        if hasattr(self, "matrix_a1"):
            self.matrix_a1.set_levels([0.0] * 16)
        if hasattr(self, "lbl_a1_size") and self.lbl_a1_size and self.lbl_a1_size.winfo_exists():
            self.lbl_a1_size.configure(text="0.0 MB / 0.0 MB")
        if hasattr(self, "lbl_a1_eta") and self.lbl_a1_eta and self.lbl_a1_eta.winfo_exists():
            self.lbl_a1_eta.configure(text="")
        if hasattr(self, "lbl_a1_pct") and self.lbl_a1_pct and self.lbl_a1_pct.winfo_exists():
            self.lbl_a1_pct.configure(text="0%")
        if hasattr(self, "lbl_a1_speed") and self.lbl_a1_speed and self.lbl_a1_speed.winfo_exists():
            self.lbl_a1_speed.configure(text="0.0 MB/s")

    def update_kanban_active_stream(
        self,
        filename: str,
        pct: float,
        speed_str: str,
        chunks: List[Any],
        active_chunks: int,
        downloaded: int = 0,
        total: int = 0,
        eta: str = "",
    ):
        """Updates the active stream card in Column 2 in real-time."""
        eng = getattr(self, "engine", None)
        is_running = False
        if eng:
            r = getattr(eng, "is_running", False)
            is_running = bool(r() if callable(r) else r)

        eta_raw = str(eta or "").strip()
        stage_part, stage_timer = [x.strip() for x in eta_raw.split("|", 1)] if "|" in eta_raw else (eta_raw, "")
        has_at = False
        if "@" in stage_part:
            try:
                clean_stage, stage_pct_str = stage_part.split("@", 1)
                pct = max(0.0, min(100.0, float(stage_pct_str)))
                stage_part = clean_stage
                has_at = True
            except Exception:
                pass
        eta_lower = stage_part.lower()
        is_processing = any(k in eta_lower for k in ("merging", "burning", "embedding", "clipping", "boost", "transcoding"))
        raw_p = getattr(eng, "is_paused", False) if eng else False
        eng_paused = (raw_p() if callable(raw_p) else raw_p) is True
        desired_p = getattr(self, "_pause_desired_state", None) if (eng and getattr(self, "_pause_desired_engine", None) is eng) else None
        if desired_p is not None:
            eng_paused = bool(desired_p)
        is_paused_state = ("paused" in eta_lower and desired_p is not False) or (eng_paused and not is_processing)

        if not is_running and not is_processing and not is_paused_state and eta_lower != "downloading" and pct <= 0 and (not speed_str or speed_str in ("0 B/s", "0.0 MB/s")):
            self.reset_kanban_active_stream()
            return

        if is_paused_state:
            speed_str = "0.0 MB/s"
            if pct <= 0 and downloaded <= 0 and getattr(self, "_last_active_pct", 0.0) > 0:
                pct = float(self._last_active_pct)
                downloaded = int(getattr(self, "_last_active_downloaded", 0) or 0)
                total = total or int(getattr(self, "_last_active_total", 0) or 0)
        elif downloaded > 0 or total > 0 or pct > 0:
            self._last_active_pct = pct
            self._last_active_downloaded = downloaded
            self._last_active_total = total

        def _fmt_sz(b: float) -> str:
            b = max(0.0, float(b or 0))
            if b >= 1024**3:
                return f"{b / (1024**3):.2f} GB"
            if b >= 1024**2:
                return f"{b / (1024**2):.1f} MB"
            if b >= 1024:
                return f"{b / 1024:.1f} KB"
            return f"{int(b)} B"

        if total <= 0 and eng:
            try:
                raw_t = getattr(eng, "total_size", 0)
                total = int(raw_t() if callable(raw_t) else raw_t or 0)
            except Exception:
                total = 0

        if downloaded <= 0 and total > 0 and pct > 0:
            downloaded = int(total * (pct / 100.0))

        if not self._active_stream_live:
            self._active_stream_live = True
            if hasattr(self, "empty_active_canvas") and self.empty_active_canvas.winfo_exists():
                self.empty_active_canvas.pack_forget()
            if hasattr(self, "card_active_1"):
                self.card_active_1.pack(fill=tk.X, pady=(0, 10))

        if hasattr(self, "lbl_col2_title") and self.lbl_col2_title.winfo_exists():
            self.lbl_col2_title.configure(text=f"{tr('pipeline_col_active', 'Active Turbo Streams')} (1)")

        if hasattr(self, "lbl_a1_filename") and self.lbl_a1_filename.winfo_exists():
            clean_name = os.path.basename(filename) if filename else "Active Stream"
            self.lbl_a1_filename.configure(text=clean_name[:32] + ("..." if len(clean_name) > 32 else ""))

        if hasattr(self, "lbl_a1_pct") and self.lbl_a1_pct.winfo_exists():
            self.lbl_a1_pct.configure(text=f"{int(pct)}%")

        if hasattr(self, "lbl_a1_speed") and self.lbl_a1_speed.winfo_exists():
            self.lbl_a1_speed.configure(text=speed_str)

        if hasattr(self, "lbl_a1_size") and self.lbl_a1_size and self.lbl_a1_size.winfo_exists():
            if is_processing and total > 0:
                sz_txt = f"📦 {_fmt_sz(total)} / {_fmt_sz(total)} ✓"
            elif total > 0:
                sz_txt = f"📦 {_fmt_sz(downloaded)} / {_fmt_sz(total)}"
            elif downloaded > 0:
                sz_txt = f"📦 {_fmt_sz(downloaded)}"
            else:
                sz_txt = "📦 جاري الاتصال..."
            self.lbl_a1_size.configure(text=sz_txt)

        if hasattr(self, "lbl_a1_eta") and self.lbl_a1_eta and self.lbl_a1_eta.winfo_exists():
            stage_lower = stage_part.lower()
            if stage_timer and stage_timer not in ("--:--", "--:--:--"):
                timer_suffix = f" ({int(pct)}%) • ⏱ {stage_timer}"
            elif has_at or ("|" in eta_raw and stage_timer in ("--:--", "--:--:--")):
                timer_suffix = f" ({int(pct)}%)"
            elif stage_part.endswith("..."):
                timer_suffix = "..."
            else:
                timer_suffix = f" ({int(pct)}%)" if pct > 0 else ""

            if is_paused_state:
                eta_txt = "⏸ متوقف مؤقتاً"
            elif "merging" in stage_lower:
                eta_txt = f"⚙️ جاري دمج الصوت والفيديو{timer_suffix}"
            elif "burning" in stage_lower:
                eta_txt = f"🔥 جاري حرق الترجمة{timer_suffix}"
            elif "embedding" in stage_lower:
                eta_txt = f"📝 جاري دمج الترجمة{timer_suffix}"
            elif "clipping" in stage_lower:
                eta_txt = f"✂️ جاري قص المقطع{timer_suffix}"
            elif "boost" in stage_lower:
                eta_txt = f"🔊 جاري تحسين الصوت{timer_suffix}"
            elif "transcoding" in stage_lower:
                eta_txt = f"🎵 جاري تحويل الصوت{timer_suffix}"
            elif eta_raw and eta_raw not in ("--:--", ""):
                eta_txt = f"⏱ {eta_raw} • ⚡ {active_chunks}" if active_chunks > 0 else f"⏱ {eta_raw}"
            elif active_chunks > 0:
                eta_txt = f"⚡ {active_chunks} مسارات نشطة"
            else:
                eta_txt = ""
            self.lbl_a1_eta.configure(text=eta_txt)

        if hasattr(self, "btn_a1_pause") and self.btn_a1_pause and self.btn_a1_pause.winfo_exists():
            self.btn_a1_pause.configure(text="▶" if is_paused_state else "⏸")

        if hasattr(self, "lbl_col2_total_speed") and self.lbl_col2_total_speed.winfo_exists():
            self.lbl_col2_total_speed.configure(text=speed_str)

        if hasattr(self, "canvas_a1_prog") and self.canvas_a1_prog.winfo_exists():
            self._draw_neon_bar(self.canvas_a1_prog, pct / 100.0)

        if hasattr(self, "matrix_a1"):
            safe_lanes = 0
            if hasattr(self, "engine") and self.engine:
                raw_mc = getattr(self.engine, "max_connections", 0)
                if isinstance(raw_mc, (int, str)) and not isinstance(raw_mc, bool):
                    s = str(raw_mc).strip()
                    if s.isdigit(): safe_lanes = int(s)
            self.matrix_a1.update_from_chunks(chunks, active_count=(0 if is_paused_state else active_chunks), is_active=(not is_paused_state), max_lanes=safe_lanes)

    def refresh_kanban_col2(self):
        """Re-translates Column 2 texts."""
        count = 1 if getattr(self, "_active_stream_live", False) else 0
        if hasattr(self, "lbl_col2_title") and self.lbl_col2_title.winfo_exists():
            self.lbl_col2_title.configure(text=f"{tr('pipeline_col_active', 'Active Turbo Streams')} ({count})")
        if not getattr(self, "_active_stream_live", False):
            self.reset_kanban_active_stream()

    def _draw_neon_bar(self, canvas: tk.Canvas, ratio: float):
        draw_neon_progress_bar(canvas, ratio)

    def _show_active_card_menu(self, anchor_widget: Any):
        """Displays options menu for Pause, Cancel, Refresh, Copy."""
        menu = tk.Menu(anchor_widget, tearoff=0, bg="#151a24", fg="#f8fafc", activebackground="#0284c7", activeforeground="#ffffff")
        eng = getattr(self, "engine", None)
        desired_p = getattr(self, "_pause_desired_state", None) if (eng and getattr(self, "_pause_desired_engine", None) is eng) else None
        is_paused = bool(desired_p) if desired_p is not None else (getattr(eng, "is_paused", False) if eng else False)
        menu.add_command(label=tr("menu_resume", "▶ Resume") if is_paused else tr("menu_pause", "|| Pause"), command=self._on_pause_resume)
        menu.add_command(label=tr("menu_cancel", "✕ Cancel Download"), command=self._on_cancel_download)
        menu.add_separator()
        menu.add_command(label=tr("menu_refresh", "↻ Refresh Expired Link"), command=self._open_refresh_link_dialog)
        menu.add_command(label=tr("menu_copy_url", "⎘ Copy URL"), command=self._copy_active_url)
        try:
            menu.tk_popup(anchor_widget.winfo_rootx(), anchor_widget.winfo_rooty() + anchor_widget.winfo_height())
        finally:
            menu.grab_release()

    def _copy_active_url(self):
        u = getattr(self, "_active_download_url", "") or (self.entry_url.get() if hasattr(self, "entry_url") else "")
        if u and hasattr(self, "root"):
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(u)
            except Exception:
                pass


__all__ = ["KanbanActiveColumnMixin"]
