"""
QualityModalLayoutMixin: Builds the visual layout and widget hierarchy for QualitySelectionModal.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from faqih_downloader.config import get_setting
from faqih_downloader.locales.i18n import tr
from faqih_downloader.utils.file_ops import apply_media_filename_tags
from faqih_downloader.services.youtube_service import VideoFormatOption, format_filesize
from faqih_downloader.ui.modals.quality_modal_helpers import (
    build_preview_header_banner,
    build_quality_title_bar,
    sync_modal_selection_to_staged,
)


class QualityModalLayoutMixin:
    """Provides _build_ui constructing header, banner, format treeview, audio/sub selectors, and action buttons."""

    def _build_ui(self):
        c_bg, c_panel = self.theme["c_bg"], self.theme["c_panel"]
        c_panel_light, c_border = self.theme["c_panel_light"], self.theme["c_border"]
        c_accent, c_accent_dark = self.theme["c_accent"], self.theme["c_accent_dark"]
        c_success, c_text_bright = self.theme["c_success"], self.theme["c_text_bright"]
        c_text_muted, c_input_bg = self.theme["c_text_muted"], self.theme["c_input_bg"]

        outer = tk.Frame(self, bg=c_border, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self.title_bar = build_quality_title_bar(self, outer, self.theme, self.title(), self._on_close)

        body = tk.Frame(outer, bg=c_bg, padx=16, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        lbl_head = tk.Label(body, text=tr("modal_quality_header", "❖ SELECT VIDEO RESOLUTION & QUALITY"), font=("Segoe UI", 11, "bold"), bg=c_bg, fg=c_accent)
        lbl_head.pack(anchor="w", pady=(0, 6))

        # Compact embedded Preview Header Banner
        self.card_info, self.btn_banner_preview = build_preview_header_banner(
            parent_frame=body,
            theme=self.theme,
            video_title=self.video_title,
            duration=self.duration,
            options_count=len(self.options),
            video_url=self.video_url,
            on_preview_cmd=self._on_preview_video
        )

        table_frame = tk.Frame(body, bg=c_panel, highlightbackground=c_border, highlightthickness=1)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("res", "ext", "size", "fps", "mode")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8, selectmode="browse", style="Custom.Treeview")

        for col, txt, anc, w in (
            ("res", tr("modal_col_res", "Resolution / Quality"), "w", 170),
            ("ext", tr("modal_col_ext", "Format"), "center", 70),
            ("size", tr("modal_col_size", "Est. Size"), "e", 100),
            ("fps", tr("modal_col_fps", "FPS"), "center", 95),
            ("mode", tr("modal_col_type", "Stream Details"), "w", 210),
        ):
            self.tree.heading(col, text=txt, anchor=anc)
            self.tree.column(col, width=w, anchor=anc)

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._row_to_opt: Dict[str, VideoFormatOption] = {}
        for idx, opt in enumerate(self.options):
            iid = f"opt_{idx}"
            self._row_to_opt[iid] = opt
            fps_str = str(opt.fps) if opt.fps > 0 else "—"
            size_str = format_filesize(opt.filesize_approx)
            vals = (opt.resolution_label, opt.ext.upper(), size_str, fps_str, opt.note)
            self.tree.insert("", tk.END, iid=iid, values=vals)

        first_iid = "opt_0"
        if self.options:
            init_idx = self._resolve_initial_index()
            first_iid = f"opt_{init_idx}"
            self.tree.selection_set(first_iid)
            self.tree.focus(first_iid)
            self.tree.see(first_iid)
            self.after_idle(lambda: self.tree.see(first_iid) if self.winfo_exists() else None)
            if first_iid in self._row_to_opt:
                self.selected_option = self._row_to_opt[first_iid]

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        init_ext = self._resolve_initial_ext_subs()
        for o in (self.options or []):
            if init_ext and not getattr(o, "external_subtitle_tracks", None):
                try: o.external_subtitle_tracks = [dict(t) for t in init_ext]
                except Exception: pass

        # Audio & Subtitle selection row
        if self.audio_tracks or self.subtitle_tracks:
            from faqih_downloader.services.youtube_tracks import build_audio_subtitle_row
            self.cb_audio, self.cb_sub = build_audio_subtitle_row(
                body, self.theme, self.audio_tracks, self.subtitle_tracks
            )
            if self.cb_audio:
                self.cb_audio.bind("<<ComboboxSelected>>", lambda e: sync_modal_selection_to_staged(self), add="+")
            if self.cb_sub:
                if init_ext and hasattr(self.cb_sub, "set_external_subtitle_tracks"):
                    self.cb_sub.set_external_subtitle_tracks(init_ext, notify=False)
                self.cb_sub._on_ext_srt_changed = lambda _: sync_modal_selection_to_staged(self)
                self.cb_sub.bind("<<ComboboxSelected>>", lambda e: sync_modal_selection_to_staged(self), add="+")

        card_dest = tk.Frame(body, bg=c_panel, padx=12, pady=8, highlightbackground=c_border, highlightthickness=1)
        card_dest.pack(fill=tk.X, pady=(0, 12))

        lbl_dest = tk.Label(card_dest, text=tr("modal_save_to", "Save As:"), font=("Segoe UI", 9, "bold"), bg=c_panel, fg=c_text_bright)
        lbl_dest.pack(side=tk.LEFT)

        self.entry_dest = tk.Entry(card_dest, font=("Segoe UI", 9), bg=c_input_bg, fg=c_text_bright, insertbackground=c_accent, relief="flat")
        self.entry_dest.insert(0, self.dest_path)
        self.entry_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8), ipady=3)

        if self.cb_sub and hasattr(self.cb_sub, "_mode_var"):
            def _on_sub_mode_modal_changed(*_):
                if hasattr(self, "entry_dest") and self.selected_option:
                    sub_mode = getattr(self.cb_sub, "_selected_mode", "soft_embed")
                    if hasattr(self.cb_sub, "get_selected_mode"): sub_mode = self.cb_sub.get_selected_mode()
                    cur = self.entry_dest.get().strip()
                    has_sub = bool(getattr(self.selected_option, "selected_subtitle_track", None))
                    updated = apply_media_filename_tags(
                        cur, quality_label=self.selected_option.resolution_label,
                        is_sub_burned=(sub_mode == "hard_burn") and has_sub, ext=self.selected_option.ext
                    )
                    self.entry_dest.delete(0, tk.END)
                    self.entry_dest.insert(0, updated)
                    if self.dest_path: self.dest_path = updated
                    sync_modal_selection_to_staged(self)
            try: self.cb_sub._mode_var.trace_add("write", _on_sub_mode_modal_changed)
            except Exception:
                try: self.cb_sub._mode_var.trace("w", _on_sub_mode_modal_changed)
                except Exception: pass

        btn_browse = tk.Button(
            card_dest, text=tr("modal_btn_browse", "⋯ Browse..."), font=("Segoe UI", 8),
            bg=c_panel_light, fg=c_text_bright, relief="flat", activebackground=c_accent_dark,
            cursor="hand2", command=self._on_browse
        )
        btn_browse.pack(side=tk.RIGHT)
        if getattr(self, "options", None) and (first_iid != "opt_0" or (self.selected_option and f"[{self.selected_option.resolution_label}]" not in self.dest_path and "[" in self.dest_path)):
            self._on_tree_select(None)

        btn_row = tk.Frame(body, bg=c_bg)
        btn_row.pack(fill=tk.X)
        self.btn_download = tk.Button(
            btn_row, text=tr("modal_btn_start_quality", "⚡ Download Selected Quality"), font=("Segoe UI", 9, "bold"),
            bg=c_success, fg="white", relief="flat", activebackground="#059669", cursor="hand2",
            padx=12, pady=6, command=self._on_download
        )
        self.btn_download.pack(side=tk.LEFT)

        self.btn_download_mp3: Optional[tk.Button] = None
        if any(opt.is_audio_only for opt in self.options):
            self.btn_download_mp3 = tk.Button(
                btn_row, text=tr("modal_download_mp3", "♪ Download MP3"), font=("Segoe UI", 9, "bold"),
                bg=c_accent_dark, fg="white", relief="flat", activebackground=c_accent, cursor="hand2",
                padx=12, pady=6, command=self._on_download_mp3
            )
            self.btn_download_mp3.pack(side=tk.LEFT, padx=(6, 0))

        self.btn_preview_video = tk.Button(
            btn_row, text=tr("btn_preview_video", "▶ Preview Video"), font=("Segoe UI", 9, "bold"),
            bg=c_panel_light, fg=c_accent, relief="flat", activebackground=c_accent_dark, activeforeground="white",
            cursor="hand2", padx=12, pady=6, command=self._on_preview_video
        )
        self.btn_preview_video.pack(side=tk.LEFT, padx=(6, 0))

        self.btn_cancel = tk.Button(
            btn_row, text=tr("modal_btn_cancel", "✕ Cancel"), font=("Segoe UI", 9, "bold"),
            bg=c_panel_light, fg=c_text_muted, relief="flat", activebackground=c_border,
            cursor="hand2", padx=12, pady=6, command=self._on_close
        )
        self.btn_cancel.pack(side=tk.RIGHT)

        self.btn_open_app = tk.Button(
            btn_row, text=tr("modal_btn_open_in_main", "❐ Open in Main App"),
            font=("Segoe UI", 9), bg=c_panel_light, fg=c_text_bright, relief="flat",
            activebackground=c_border, cursor="hand2", padx=12, pady=6, command=self._on_open_in_main
        )
        self.btn_open_app.pack(side=tk.RIGHT, padx=(0, 6))
