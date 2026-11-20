"""
MediaBarLayoutMixin: UI construction and localization for the Main Window Media Settings Bar.
"""
from typing import Optional, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

import sys
from ....i18n import tr
from ....config import get_setting as _cfg_get_setting
from ....services.youtube_service import VideoFormatOption


def _get_setting(key: str, default: Any = None) -> Any:
    mod = sys.modules.get("faqih_downloader.ui.panels.media_options_bar")
    if mod and hasattr(mod, "get_setting"):
        return getattr(mod, "get_setting")(key, default)
    return _cfg_get_setting(key, default)


class MediaBarLayoutMixin:
    """Provides layout construction, hiding, and locale refreshing for the media bar."""

    def _build_media_options_bar(self, parent_card):
        """Constructs sleek themed frame for video quality, dubbing, and subtitle settings."""
        if tk is None or ttk is None:
            return

        self.media_options_frame = tk.Frame(parent_card, bg=self.c_panel)
        # Initially not packed; shown when media format options are populated
        self._main_media_options: List[VideoFormatOption] = []
        self._main_audio_tracks: List[Dict[str, Any]] = []
        self._main_subtitle_tracks: List[Dict[str, Any]] = []
        self._main_external_subtitle_tracks: List[Dict[str, Any]] = []
        self._main_sub_mode_codes = ["soft_embed", "hard_burn"]
        self._pending_media_context: Optional[Dict[str, Any]] = None
        self._last_yt_info: Optional[Dict[str, Any]] = None

        # Row 1: Quality (Combobox), Audio/Dubbing (Combobox), Reopen Modal Button
        row1 = tk.Frame(self.media_options_frame, bg=self.c_panel)
        row1.pack(fill=tk.X, pady=(4, 2))
        self.lbl_main_quality = tk.Label(row1, text=tr("lbl_main_quality", "⚙ Quality:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=10, anchor="w")
        self.cb_main_quality = ttk.Combobox(row1, state="readonly", font=("Segoe UI", 8), width=25)
        self.lbl_main_quality.pack(side=tk.LEFT); self.cb_main_quality.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_main_quality.bind("<<ComboboxSelected>>", self._on_main_quality_changed)

        self.lbl_main_audio = tk.Label(row1, text=tr("lbl_main_audio", "♪ Audio:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=8, anchor="w")
        self.cb_main_audio = ttk.Combobox(row1, state="readonly", font=("Segoe UI", 8), width=20)
        self.lbl_main_audio.pack(side=tk.LEFT); self.cb_main_audio.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_audio.bind("<<ComboboxSelected>>", self._on_main_audio_changed)

        self.btn_main_preview = tk.Button(row1, text=tr("btn_preview_short", "▶ Preview"), font=("Segoe UI", 8, "bold"), bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark, activeforeground="white", cursor="hand2", padx=10, pady=4, command=self._open_main_media_preview)
        self.btn_main_preview.pack(side=tk.RIGHT, padx=(4, 0))
        self.btn_reopen_quality = tk.Button(row1, text=tr("btn_media_quality_options", "⚙ Options..."), font=("Segoe UI", 8, "bold"), bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark, activeforeground="white", cursor="hand2", padx=10, pady=4, command=self._reopen_media_quality_modal)
        self.btn_reopen_quality.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_main_advanced = self.btn_reopen_quality

        # Row 2: Subtitles (Combobox), Internal Delivery Mode (Combobox), External SRT Button, Threads
        row2 = tk.Frame(self.media_options_frame, bg=self.c_panel)
        row2.pack(fill=tk.X, pady=(2, 2))
        self.lbl_main_sub = tk.Label(row2, text=tr("lbl_main_sub", "≡ Subtitles:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=10, anchor="w")
        self.cb_main_sub = ttk.Combobox(row2, state="readonly", font=("Segoe UI", 8), width=20)
        self.lbl_main_sub.pack(side=tk.LEFT); self.cb_main_sub.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub.bind("<<ComboboxSelected>>", self._on_main_sub_changed)

        self.lbl_main_sub_mode = tk.Label(row2, text=tr("lbl_main_sub_mode", "⚙️ Mode:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=8, anchor="w")
        sub_mode_labels = [tr("sub_mode_soft", "دمج ناعم (Soft Embed)"), tr("sub_mode_burn", "حرق دائم (Burn-in)")]
        self.cb_main_sub_mode = ttk.Combobox(row2, values=sub_mode_labels, state="disabled", font=("Segoe UI", 8), width=20)
        self.cb_main_sub_mode.current(0)
        self.lbl_main_sub_mode.pack(side=tk.LEFT); self.cb_main_sub_mode.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub_mode.bind("<<ComboboxSelected>>", self._on_main_sub_mode_changed)

        from ...modals.quality_tracks_ui import format_ext_srt_button_text
        self.lbl_main_ext_srt = tk.Label(row2, text=tr("lbl_ext_srt", "❏ خارجي:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright)
        self.btn_main_ext_srt = tk.Button(
            row2, text=format_ext_srt_button_text([]), font=("Segoe UI", 8, "bold"),
            bg=getattr(self, "c_input_bg", self.c_panel_light), fg=self.c_text_bright,
            activebackground=self.c_accent, activeforeground="white", relief="flat", bd=1,
            padx=8, pady=2, cursor="hand2", command=self._open_main_ext_srt_menu,
        )
        self.lbl_main_ext_srt.pack(side=tk.LEFT); self.btn_main_ext_srt.pack(side=tk.LEFT, padx=(4, 8))

        is_ar = (getattr(self, "current_language", "en") == "ar") or (_get_setting("language", "ar") == "ar")
        lbl_threads = tr("lbl_main_threads", "⚡ المسارات:" if is_ar else "⚡ Threads:")
        self.lbl_main_sub_pos = tk.Label(row2, text=lbl_threads, font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=9, anchor="w")
        self._main_conn_values = ["1", "2", "4", "8", "16", "32"]
        self._main_sub_pos_codes = ["bottom", "middle", "top"]
        self.cb_main_sub_pos = ttk.Combobox(row2, values=self._main_conn_values, state="readonly", font=("Segoe UI", 8), width=6)
        init_conn = str(_get_setting("max_connections", 8))
        self.cb_main_sub_pos.set(init_conn if init_conn in self._main_conn_values else "8")
        self.cb_main_conn = self.cb_main_sub_pos
        self.lbl_main_sub_pos.pack(side=tk.LEFT); self.cb_main_sub_pos.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub_pos.bind("<<ComboboxSelected>>", self._on_main_sub_pos_changed)

    def hide_main_media_bar(self):
        """Hides the Media Settings Bar frame when switching to non-media URLs."""
        self._main_bar_url = None
        if hasattr(self, "media_options_frame"):
            try: self.media_options_frame.pack_forget()
            except Exception: pass
        if hasattr(self, "media_bar_host") and self.media_bar_host:
            try: self.media_bar_host.pack_forget()
            except Exception: pass

    def refresh_media_options_locale(self):
        """Refreshes all Media Options Bar labels, buttons, and comboboxes on language switch."""
        try:
            from ....i18n import LocalizationManager
            cur_lang = LocalizationManager.get_instance().get_language()
        except Exception:
            cur_lang = getattr(self, "current_language", "ar")
        is_ar = (cur_lang == "ar")
        if hasattr(self, "lbl_main_quality") and self.lbl_main_quality.winfo_exists():
            self.lbl_main_quality.configure(text=tr("lbl_main_quality", "⚙ Quality:"))
        if hasattr(self, "lbl_main_audio") and self.lbl_main_audio.winfo_exists():
            self.lbl_main_audio.configure(text=tr("lbl_main_audio", "♪ Audio:"))
        if hasattr(self, "lbl_main_sub") and self.lbl_main_sub.winfo_exists():
            self.lbl_main_sub.configure(text=tr("lbl_main_sub", "≡ Subtitles:"))
        if hasattr(self, "lbl_main_sub_mode") and self.lbl_main_sub_mode.winfo_exists():
            self.lbl_main_sub_mode.configure(text=tr("lbl_main_sub_mode", "⚙️ Mode:"))
        if hasattr(self, "lbl_main_ext_srt") and self.lbl_main_ext_srt.winfo_exists():
            self.lbl_main_ext_srt.configure(text=tr("lbl_ext_srt", "❏ خارجي:" if is_ar else "❏ Ext SRT:"))
        if hasattr(self, "btn_main_ext_srt") and self.btn_main_ext_srt.winfo_exists():
            from ...modals.quality_tracks_ui import format_ext_srt_button_text
            self.btn_main_ext_srt.configure(text=format_ext_srt_button_text(getattr(self, "_main_external_subtitle_tracks", [])))
        if hasattr(self, "lbl_main_sub_pos") and self.lbl_main_sub_pos.winfo_exists():
            self.lbl_main_sub_pos.configure(text=tr("lbl_main_threads", "⚡ المسارات:" if is_ar else "⚡ Threads:"))
        if hasattr(self, "btn_reopen_quality") and self.btn_reopen_quality.winfo_exists():
            self.btn_reopen_quality.configure(text=tr("btn_media_quality_options", "⚙ Options..."))
        if hasattr(self, "btn_main_preview") and self.btn_main_preview.winfo_exists():
            self.btn_main_preview.configure(text=tr("btn_preview_short", "▶ Preview"))
        if hasattr(self, "cb_main_sub_mode") and self.cb_main_sub_mode.winfo_exists():
            try:
                cur_idx = self.cb_main_sub_mode.current()
            except Exception:
                cur_idx = 0
            sub_mode_labels = [
                tr("sub_mode_soft", "دمج ناعم (Soft Embed)"),
                tr("sub_mode_burn", "حرق دائم (Burn-in)"),
            ]
            self.cb_main_sub_mode.configure(values=sub_mode_labels)
            if 0 <= cur_idx < len(sub_mode_labels):
                self.cb_main_sub_mode.current(cur_idx)
        if hasattr(self, "cb_main_sub") and self.cb_main_sub.winfo_exists():
            try:
                vals = list(self.cb_main_sub.cget("values") or [])
                if vals and vals[0] in ("بدون ترجمة (None)", "None (No Subtitle)", "No Subtitle", tr("sub_none", "بدون ترجمة (None)")):
                    cur_s = self.cb_main_sub.current()
                    vals[0] = tr("sub_none", "بدون ترجمة (None)")
                    self.cb_main_sub.configure(values=vals)
                    if 0 <= cur_s < len(vals):
                        self.cb_main_sub.current(cur_s)
            except Exception:
                pass

__all__ = ["MediaBarLayoutMixin"]
