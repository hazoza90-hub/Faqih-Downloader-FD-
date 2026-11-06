"""
HiddenCompatPanelMixin: Preserves 100% of internal widgets and variables expected by tests and controllers.
Instantiates legacy notebook, treeviews, log console, speed limiter, and toggles in an accessible frame.
"""
from __future__ import annotations

import os
from typing import Optional, Any

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting, get_base_downloads_dir
from faqih_downloader.ui.components.tooltip import ToolTip


class _CompatButton(tk.Button if tk is not None else object):  # type: ignore
    """Button subclass that manages background / foreground on state shifts."""
    def __init__(self, master=None, active_bg=None, disabled_bg=None, active_fg="#ffffff", disabled_fg="#64748b", **kwargs):
        self._active_bg = active_bg
        self._disabled_bg = disabled_bg
        self._active_fg = active_fg
        self._disabled_fg = disabled_fg
        super().__init__(master, **kwargs)

    def configure(self, cnf=None, **kwargs):
        if cnf is not None and isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
            cnf = None
        if "state" in kwargs:
            st = kwargs["state"]
            if "bg" not in kwargs:
                if st == "disabled" and self._disabled_bg:
                    kwargs["bg"] = self._disabled_bg
                elif st == "normal" and self._active_bg:
                    kwargs["bg"] = self._active_bg
            if "fg" not in kwargs:
                if st == "disabled" and self._disabled_fg:
                    kwargs["fg"] = self._disabled_fg
                elif st == "normal" and self._active_fg:
                    kwargs["fg"] = self._active_fg
        return super().configure(cnf, **kwargs) if cnf else super().configure(**kwargs)

    config = configure


class HiddenCompatPanelMixin:
    """Instantiates and wires all legacy and controller-accessible widgets for 100% test compatibility."""

    def _build_compat_infrastructure(self, parent: Any):
        """Constructs background-accessible widgets in a zero-height container."""
        compat_frame = tk.Frame(parent, height=0, width=0, bg=getattr(self, "c_bg", "#0f172a"))
        compat_frame.pack(side=tk.BOTTOM, fill=tk.NONE)
        compat_frame.pack_propagate(False)
        self._compat_frame = compat_frame

        # Destination entry (self.entry_dest)
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.dest_var = tk.StringVar(value=default_dir)
        self.entry_dest = tk.Entry(compat_frame, textvariable=self.dest_var)
        self.lbl_dest = tk.Label(compat_frame, text=tr("lbl_dest", "Save Location:"), width=14)
        self.lbl_url = tk.Label(compat_frame, text=tr("lbl_url", "Download URL:"), width=14)
        self.btn_browse = tk.Button(compat_frame, text=tr("btn_browse", "⋯ Browse..."), command=self._browse_destination)
        self.btn_check_updates = tk.Button(
            compat_frame,
            text=tr("btn_check_updates", "↻ Check for Updates"),
            command=self._manual_check_updates if hasattr(self, "_manual_check_updates") else lambda: None
        )
        self.btn_update = self.btn_check_updates

        # Primary Transfer Controls (btn_pause, btn_cancel, btn_refresh_link, btn_quality_main)
        self.btn_pause = _CompatButton(
            compat_frame,
            text=tr("btn_pause", "|| Pause"),
            active_bg=getattr(self, "c_panel_light", "#1e293b"),
            disabled_bg="#182234",
            state="disabled",
            command=self._on_pause_resume
        )
        self.btn_cancel = _CompatButton(
            compat_frame,
            text=tr("btn_cancel", "✕ Cancel"),
            active_bg=getattr(self, "c_danger", "#ef4444"),
            disabled_bg="#182234",
            state="disabled",
            command=self._on_cancel_download
        )
        self.btn_refresh_link = tk.Button(
            compat_frame,
            text=tr("btn_refresh_url", "↻ Refresh Link"),
            command=self._open_refresh_link_dialog
        )
        self.btn_quality_main = tk.Button(
            compat_frame,
            text=tr("btn_quality_reopen", "⚙ Quality"),
            command=self._reopen_media_quality_modal if hasattr(self, "_reopen_media_quality_modal") else lambda: None
        )

        # Speed limiter & Connection widgets
        saved_conn = str(get_setting("max_connections", 8))
        self.conn_var = tk.StringVar(value=saved_conn)
        self.lbl_conn = tk.Label(compat_frame, text=tr("lbl_threads", "Threads:"))

        unlimited_val = tr("lbl_unlimited", "Unlimited")
        presets = [unlimited_val, "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "20 MB/s"]
        self.preset_options = [
            unlimited_val, "128 KB/s", "256 KB/s", "512 KB/s", "1 MB/s", "1.0 MB/s",
            "2 MB/s", "2.0 MB/s", "5 MB/s", "5.0 MB/s", "10 MB/s", "10.0 MB/s", "20 MB/s", "20.0 MB/s", "Custom"
        ]
        saved_preset = str(get_setting("speed_limit_preset", "Unlimited") or "Unlimited")
        if saved_preset in ("Unlimited", "بدون حد"):
            saved_preset = unlimited_val
        elif saved_preset not in self.preset_options:
            saved_preset = unlimited_val
        self.speed_preset_var = tk.StringVar(value=saved_preset)
        self.limit_preset_var = self.speed_preset_var
        self.combo_speed = ttk.Combobox(compat_frame, textvariable=self.speed_preset_var, values=presets, width=12, state="readonly")
        self.preset_combo = self.combo_speed
        self.combo_speed.bind("<<ComboboxSelected>>", self._on_speed_preset_change)

        self.lbl_limit = tk.Label(compat_frame, text=tr("lbl_speed_limiter", "Speed Limiter:"))
        self.lbl_custom = tk.Label(compat_frame, text=tr("lbl_custom_speed", "Custom:"))
        self.entry_custom_speed = tk.Entry(compat_frame, width=7)
        try:
            saved_kbps = int(get_setting("custom_speed_limit_kbps", 0) or 0)
        except Exception:
            saved_kbps = 0
        self.entry_custom_speed.insert(0, str(saved_kbps))
        self.btn_apply_speed = tk.Button(compat_frame, text=tr("btn_apply_limit", "Apply"), command=self._apply_speed_limit)
        self.lbl_active_limit = tk.Label(compat_frame, text=tr("lbl_current_unlimited", "● Current: Unlimited"))
        self.lbl_slider_val = tk.Label(compat_frame, text=f"{unlimited_val} (0 KB/s)")

        dpi_scale = getattr(self, "dpi_scale", 1.0)
        slider_len = max(20, int(22 * dpi_scale))
        slider_w = max(14, int(16 * dpi_scale))
        self.slider_speed = tk.Scale(
            compat_frame,
            from_=0,
            to=20480,
            orient=tk.HORIZONTAL,
            showvalue=False,
            command=self._on_slider_moved,
            highlightthickness=1,
            highlightbackground=getattr(self, "c_border", "#283548"),
            highlightcolor=getattr(self, "c_accent", "#38bdf8"),
            bd=0,
            relief="flat",
            sliderrelief="flat",
            bg=getattr(self, "c_panel", "#131c31"),
            troughcolor=getattr(self, "c_input_bg", "#090e1a"),
            sliderlength=slider_len,
            width=slider_w,
        )

        # Quick Toggles: Unmapped row_toggles frame housing child buttons
        self.row_toggles = tk.Frame(compat_frame)

        self.btn_clipboard_sniffer = tk.Button(
            self.row_toggles,
            text=tr("btn_sniffer_active", "● Sniffer: Active"),
            command=self.toggle_clipboard_sniffer
        )
        self.btn_clipboard_sniffer.pack(side=tk.LEFT)
        self.btn_sniffer = self.btn_clipboard_sniffer

        self.btn_auto_cat = tk.Button(
            self.row_toggles,
            text=tr("btn_auto_cat_on", "❖ Auto-Sort: ON") if getattr(self, "auto_categorize_folders", True) else tr("btn_auto_cat_off", "❖ Auto-Sort: OFF"),
            command=self.toggle_auto_categorize
        )
        self.btn_auto_cat.pack(side=tk.LEFT)

        self.btn_cookies = tk.Button(
            self.row_toggles,
            text=self._get_cookies_btn_text() if hasattr(self, "_get_cookies_btn_text") else "◆ Cookies: Auto",
            command=self.cycle_cookies_setting
        )
        self.btn_cookies.pack(side=tk.LEFT)

        st_enabled = bool(getattr(self, "_startup_enabled", False))
        self.btn_startup = tk.Button(
            self.row_toggles,
            text=tr("btn_startup_on") if st_enabled else tr("btn_startup_off"),
            command=self.toggle_startup_setting
        )
        self.btn_startup.pack(side=tk.LEFT)

        self.btn_browser = tk.Button(
            self.row_toggles,
            text=tr("btn_browser", "⚙ Browser Integration"),
            command=self.open_browser_integration_dialog if hasattr(self, "open_browser_integration_dialog") else (self._open_browser_integration_dialog if hasattr(self, "_open_browser_integration_dialog") else lambda: None)
        )
        self.btn_browser.pack(side=tk.LEFT)

        # Metrics Labels & Canvas Progress
        box_bg = "#0d1526"
        c_border = getattr(self, "c_border", "#283548")
        c_text_muted = getattr(self, "c_text_muted", "#94a3b8")
        c_text_bright = getattr(self, "c_text_bright", "#f8fafc")
        c_accent = getattr(self, "c_accent", "#38bdf8")

        def _make_compat_metric(col: int, title: str, initial_val: str):
            box = tk.Frame(compat_frame, bg=box_bg, padx=12, pady=8, highlightbackground=c_border, highlightthickness=1)
            lbl_t = tk.Label(box, text=title, font=("Segoe UI", 8, "bold"), bg=box_bg, fg=c_text_muted)
            lbl_t.pack(anchor="w")
            box.lbl_t = lbl_t
            val_fg = c_accent if col == 0 else c_text_bright
            lbl_v = tk.Label(box, text=initial_val, font=("Segoe UI", 12, "bold"), bg=box_bg, fg=val_fg)
            lbl_v.pack(anchor="w", pady=(2, 0))
            box.lbl_v = lbl_v
            return lbl_v

        prog_h = max(26, int(26 * dpi_scale))
        self.canvas_prog = tk.Canvas(compat_frame, height=prog_h, bg="#090e1a", highlightthickness=0)
        self.card_speed = _make_compat_metric(0, tr("metric_speed", "Speed"), "0.0 KB/s")
        self.lbl_t_speed = self.card_speed.master.lbl_t
        self.card_size = _make_compat_metric(1, tr("metric_total_size", "Size"), "0 B / 0 B (0%)")
        self.lbl_t_size = self.card_size.master.lbl_t
        self.card_eta = _make_compat_metric(2, tr("metric_eta", "ETA"), "--:--:--")
        self.lbl_t_eta = self.card_eta.master.lbl_t
        self.card_threads = _make_compat_metric(3, tr("metric_threads", "Threads"), f"0 / 0 {tr('lbl_threads_unit', 'Threads')}")
        self.lbl_t_threads = self.card_threads.master.lbl_t

        # Chunk Canvas
        chunks_h = max(34, int(34 * dpi_scale))
        self.canvas_chunks = tk.Canvas(compat_frame, height=chunks_h, bg="#090e1a", highlightthickness=0)
        self.chunk_canvas = self.canvas_chunks

        # Notebook with 3 Tabs: Chunk Segments, Activity Log, History
        self.notebook = ttk.Notebook(compat_frame, style="Custom.TNotebook")

        # Tab 0: Chunk Segments
        tab_bg = getattr(self, "c_panel", "#1e293b")
        tab0 = tk.Frame(self.notebook, bg=tab_bg, highlightthickness=1, highlightbackground=c_border, highlightcolor=c_border, bd=0)
        self.notebook.add(tab0, text=tr("tab_chunks", "  ▦ Chunk Segments  "))
        cols_chunks = ("id", "range", "size", "downloaded", "pct", "status")
        self.tree_chunks = ttk.Treeview(tab0, columns=cols_chunks, show="headings", style="Custom.Treeview")
        for col in cols_chunks:
            self.tree_chunks.heading(col, text=col)
        self.tree_chunks.column("id", width=max(50, int(60 * dpi_scale)), minwidth=40, anchor="center", stretch=True)
        self.tree_chunks.column("range", width=max(200, int(250 * dpi_scale)), minwidth=180, anchor="w", stretch=True)
        self.tree_chunks.column("size", width=max(90, int(110 * dpi_scale)), minwidth=80, anchor="e", stretch=True)
        self.tree_chunks.column("downloaded", width=max(90, int(110 * dpi_scale)), minwidth=80, anchor="e", stretch=True)
        self.tree_chunks.column("pct", width=max(80, int(90 * dpi_scale)), minwidth=70, anchor="center", stretch=True)
        self.tree_chunks.column("status", width=max(100, int(120 * dpi_scale)), minwidth=90, anchor="center", stretch=True)
        if hasattr(self, "_build_tree_context_menu") and callable(self._build_tree_context_menu):
            try:
                self._build_tree_context_menu()
            except Exception:
                pass
        if not hasattr(self, "tree_context_menu") or self.tree_context_menu is None:
            self.tree_context_menu = tk.Menu(self.tree_chunks, tearoff=0)

        # Tab 1: Live Activity Log
        tab1 = tk.Frame(self.notebook, bg=tab_bg, highlightthickness=1, highlightbackground=c_border, highlightcolor=c_border, bd=0)
        self.notebook.add(tab1, text=tr("tab_logs", "  ▤ Live Activity Log  "))
        self.txt_log = tk.Text(tab1, bg="#090e1a", fg="#f8fafc", font=("Consolas", 9), height=5)

        # Tab 2: Download History
        tab2 = tk.Frame(self.notebook, bg=tab_bg, highlightthickness=1, highlightbackground=c_border, highlightcolor=c_border, bd=0)
        self.notebook.add(tab2, text=tr("tab_history", "  ☰ Download History  "))

        hist_cats = [
            "All Categories", "Video", "Audio", "Programs", "Compressed", "Documents", "Images", "General"
        ]
        self.combo_history_filter = ttk.Combobox(tab2, values=hist_cats, state="readonly", width=15)
        self.combo_history_filter.set("All Categories")

        self.btn_hist_open = tk.Button(tab2, text=tr("btn_hist_open", "↗ Open File"), command=self._history_open_selected_file if hasattr(self, "_history_open_selected_file") else lambda: None)
        self.btn_hist_folder = tk.Button(tab2, text=tr("btn_hist_folder", "⋯ Open Folder"), command=self._history_open_selected_folder if hasattr(self, "_history_open_selected_folder") else lambda: None)
        self.btn_hist_redownload = tk.Button(tab2, text=tr("btn_hist_redownload", "↻ Resume / Retry"), command=self._history_redownload_selected if hasattr(self, "_history_redownload_selected") else lambda: None)
        self.btn_hist_quality = tk.Button(tab2, text=tr("ctx_redownload_quality", "⚙ Re-Download Quality"), command=self._history_redownload_with_quality if hasattr(self, "_history_redownload_with_quality") else lambda: None)
        self.btn_hist_remove = tk.Button(tab2, text=tr("btn_hist_remove", "✕ Remove"), command=self._history_remove_selected if hasattr(self, "_history_remove_selected") else lambda: None)
        self.btn_hist_clear = tk.Button(tab2, text=tr("btn_hist_clear", "⌫ Clear All"), command=self._history_clear_all if hasattr(self, "_history_clear_all") else lambda: None)

        cols_hist = ("category", "filename", "size", "status", "date", "path")
        self.tree_history = ttk.Treeview(tab2, columns=cols_hist, show="headings", style="Custom.Treeview")
        self.tree_history.heading("category", text=tr("col_hist_category", "Category"))
        self.tree_history.heading("filename", text=tr("col_hist_filename", "File Name"))
        self.tree_history.heading("size", text=tr("col_hist_size", "Size"))
        self.tree_history.heading("status", text=tr("col_hist_status", "Status"))
        self.tree_history.heading("date", text=tr("col_hist_date", "Date"))
        self.tree_history.heading("path", text=tr("col_hist_path", "Path"))
        if hasattr(self, "_build_history_context_menu") and callable(self._build_history_context_menu):
            try:
                self._build_history_context_menu()
            except Exception:
                pass


__all__ = ["HiddenCompatPanelMixin"]
