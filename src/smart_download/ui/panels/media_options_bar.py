"""
MediaOptionsBarMixin: Main-window media format, dubbing audio, and subtitle options bar.
Provides dynamic Quality, Audio track, Subtitle track, and Subtitle mode selectors directly in the GUI.
"""
import os
import copy
import threading
from typing import Optional, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

from smart_download.i18n import tr
from smart_download.config import get_setting, set_setting, get_base_downloads_dir
from smart_download.utils.file_ops import apply_media_filename_tags, generate_unique_destination_path
from smart_download.services.youtube_service import VideoFormatOption, YouTubeResolver, format_filesize, sanitize_filename, is_media_url
from smart_download.services.youtube_tracks import extract_audio_tracks, extract_subtitle_tracks
from .media_options_actions import MediaOptionsActionsMixin
from ..modals.quality_modal import QualitySelectionModal
from ..modals.confirm_modal import DownloadConfirmationModal
from ..modals.quality_modal_helpers import resolve_preferred_option_index


class MediaOptionsBarMixin(MediaOptionsActionsMixin):
    """Mixin providing the Main Window Media Settings Bar for quality, dubbing, and subtitles."""

    def _build_media_options_bar(self, parent_card):
        """Constructs sleek themed frame for video quality, dubbing, and subtitle settings."""
        if tk is None or ttk is None:
            return

        self.media_options_frame = tk.Frame(parent_card, bg=self.c_panel)
        # Initially not packed; shown when media format options are populated
        self._main_media_options: List[VideoFormatOption] = []
        self._main_audio_tracks: List[Dict[str, Any]] = []
        self._main_subtitle_tracks: List[Dict[str, Any]] = []
        self._main_sub_mode_codes = ["soft_embed", "srt_only", "hard_burn"]
        self._pending_media_context: Optional[Dict[str, Any]] = None
        self._last_yt_info: Optional[Dict[str, Any]] = None

        # Row 1: Quality (Combobox), Audio/Dubbing (Combobox), Reopen Modal Button
        row1 = tk.Frame(self.media_options_frame, bg=self.c_panel)
        row1.pack(fill=tk.X, pady=(4, 2))
        self.lbl_main_quality = tk.Label(row1, text=tr("lbl_main_quality", "⚙ Quality:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=10, anchor="w")
        self.cb_main_quality = ttk.Combobox(row1, state="readonly", font=("Segoe UI", 8), width=22)
        self.lbl_main_quality.pack(side=tk.LEFT); self.cb_main_quality.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_main_quality.bind("<<ComboboxSelected>>", self._on_main_quality_changed)

        self.lbl_main_audio = tk.Label(row1, text=tr("lbl_main_audio", "♪ Audio:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=8, anchor="w")
        self.cb_main_audio = ttk.Combobox(row1, state="readonly", font=("Segoe UI", 8), width=20)
        self.lbl_main_audio.pack(side=tk.LEFT); self.cb_main_audio.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_audio.bind("<<ComboboxSelected>>", self._on_main_audio_changed)

        self.btn_main_preview = tk.Button(row1, text=tr("btn_preview_short", "▶ Preview"), font=("Segoe UI", 8, "bold"), bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark, activeforeground="white", cursor="hand2", padx=8, pady=2, command=self._open_main_media_preview)
        self.btn_main_preview.pack(side=tk.RIGHT, padx=(4, 0))
        self.btn_reopen_quality = tk.Button(row1, text=tr("btn_media_quality_options", "⚙ Options..."), font=("Segoe UI", 8, "bold"), bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark, activeforeground="white", cursor="hand2", padx=8, pady=2, command=self._reopen_media_quality_modal)
        self.btn_reopen_quality.pack(side=tk.RIGHT, padx=(0, 4))

        # Row 2: Subtitles (Combobox), Subtitle Delivery Mode (Combobox), Subtitle Position (Combobox)
        row2 = tk.Frame(self.media_options_frame, bg=self.c_panel)
        row2.pack(fill=tk.X, pady=(2, 2))
        self.lbl_main_sub = tk.Label(row2, text=tr("lbl_main_sub", "≡ Subtitles:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=10, anchor="w")
        self.cb_main_sub = ttk.Combobox(row2, state="readonly", font=("Segoe UI", 8), width=22)
        self.lbl_main_sub.pack(side=tk.LEFT); self.cb_main_sub.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_main_sub.bind("<<ComboboxSelected>>", self._on_main_sub_changed)

        self.lbl_main_sub_mode = tk.Label(row2, text=tr("lbl_main_sub_mode", "⚙️ Mode:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=7, anchor="w")
        sub_mode_labels = [tr("sub_mode_soft", "دمج ناعم"), tr("sub_mode_srt_only", "ملف ترجمة"), tr("sub_mode_burn", "حرق دائم (Burn-in)")]
        self.cb_main_sub_mode = ttk.Combobox(row2, values=sub_mode_labels, state="disabled", font=("Segoe UI", 8), width=18)
        self.cb_main_sub_mode.current(0)
        self.lbl_main_sub_mode.pack(side=tk.LEFT); self.cb_main_sub_mode.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub_mode.bind("<<ComboboxSelected>>", self._on_main_sub_mode_changed)

        self.lbl_main_sub_pos = tk.Label(row2, text=tr("lbl_main_sub_pos", "● Pos:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=6, anchor="w")
        self._main_sub_pos_codes = ["bottom", "middle", "top"]
        pos_labels = [tr("sub_pos_bottom", "أسفل (Bottom)"), tr("sub_pos_middle", "وسط (Middle)"), tr("sub_pos_top", "أعلى (Top)")]
        self.cb_main_sub_pos = ttk.Combobox(row2, values=pos_labels, state="readonly", font=("Segoe UI", 8), width=13)
        self.cb_main_sub_pos.current(0)
        self.lbl_main_sub_pos.pack(side=tk.LEFT); self.cb_main_sub_pos.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub_pos.bind("<<ComboboxSelected>>", self._on_main_sub_pos_changed)

    def populate_main_media_bar(
        self, info: Optional[Dict[str, Any]] = None, options: Optional[List[VideoFormatOption]] = None,
        audio_tracks: Optional[List[Dict[str, Any]]] = None, subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
        selected_option: Optional[VideoFormatOption] = None, url: Optional[str] = None, dest: Optional[str] = None,
        selected_opt: Optional[VideoFormatOption] = None, resolver: Optional[Any] = None, **kwargs
    ):
        """Displays and populates the Main Window Media Settings Bar with resolved formats."""
        if not hasattr(self, "media_options_frame"):
            return

        self._main_media_info = info or {}
        self._main_media_options = list(options or [])
        self._main_audio_tracks = list(audio_tracks or [])
        self._main_subtitle_tracks = list(subtitle_tracks or [])
        self._last_yt_info = info
        explicit_opt = selected_opt or selected_option
        if explicit_opt and explicit_opt in self._main_media_options:
            sel_idx = self._main_media_options.index(explicit_opt)
            sel_opt = explicit_opt
        else:
            sel_idx = resolve_preferred_option_index(self._main_media_options)
            sel_opt = self._main_media_options[sel_idx] if (self._main_media_options and 0 <= sel_idx < len(self._main_media_options)) else None

        media_url = url or (self.entry_url.get().strip() if hasattr(self, "entry_url") else "")
        final_dest = dest or (self.entry_dest.get().strip() if hasattr(self, "entry_dest") else "")
        self._pending_media_context = {
            "url": media_url,
            "info": info or {},
            "options": self._main_media_options,
            "audio_tracks": self._main_audio_tracks,
            "subtitle_tracks": self._main_subtitle_tracks,
            "selected_option": sel_opt,
            "resolver": resolver,
            "final_dest": final_dest
        }
        self._last_media_context = dict(self._pending_media_context)
        self._cache_media_context(media_url, self._pending_media_context)

        # Show frame in layout
        self.media_options_frame.pack(fill=tk.X, pady=(4, 2))

        # 1. Populate Quality Combobox
        q_vals = []
        for opt in self._main_media_options:
            fs = getattr(opt, "filesize_approx", 0) or getattr(opt, "filesize", 0)
            sz = format_filesize(fs) if fs else "~"
            res_lbl = getattr(opt, "resolution_label", "") or getattr(opt, "resolution_name", "Video")
            ext = getattr(opt, "ext", "mp4").upper()
            q_vals.append(f"{res_lbl} ({ext}) — {sz}")
        self.cb_main_quality.configure(values=q_vals)
        if q_vals and 0 <= sel_idx < len(q_vals):
            self.cb_main_quality.current(sel_idx)

        # 2. Populate Audio Combobox
        a_vals = [t.get("label", "") for t in self._main_audio_tracks]
        self.cb_main_audio.configure(values=a_vals)
        a_idx, pref_a = 0, get_setting("preferred_audio_lang", "original")
        if pref_a and pref_a != "original":
            for i, t in enumerate(self._main_audio_tracks):
                if str(t.get("language", "")).lower().startswith(pref_a.lower()):
                    a_idx = i; break
        if a_vals:
            self.cb_main_audio.current(a_idx)

        # 3. Populate Subtitles Combobox
        s_vals = [s.get("label", "") for s in self._main_subtitle_tracks]
        self.cb_main_sub.configure(values=s_vals)
        sub_idx, pref_s = 0, get_setting("preferred_subtitle_lang", "none")
        if sel_opt and getattr(sel_opt, "selected_subtitle_track", None) in self._main_subtitle_tracks:
            sub_idx = self._main_subtitle_tracks.index(sel_opt.selected_subtitle_track)
        elif pref_s and pref_s != "none":
            for i, s in enumerate(self._main_subtitle_tracks):
                if i > 0 and str(s.get("language", "")).lower().startswith(pref_s.lower()):
                    sub_idx = i; break
        if s_vals:
            self.cb_main_sub.current(sub_idx)

        # 4. Mode Selection
        mode = getattr(sel_opt, "subtitle_embed_mode", None) or get_setting("subtitle_embed_mode", "soft_embed")
        self.cb_main_sub_mode.current(self._main_sub_mode_codes.index(mode) if mode in self._main_sub_mode_codes else 0)

        # 5. Position Selection
        pos = getattr(sel_opt, "subtitle_position", None) or get_setting("subtitle_position", "bottom")
        if hasattr(self, "cb_main_sub_pos") and self.cb_main_sub_pos:
            self.cb_main_sub_pos.current(self._main_sub_pos_codes.index(pos) if pos in self._main_sub_pos_codes else 0)

        mode_st = "readonly" if len(self._main_subtitle_tracks) > 1 else "disabled"
        if hasattr(self, "cb_main_sub_mode") and self.cb_main_sub_mode: self.cb_main_sub_mode.configure(state=mode_st)
        pos_st = "readonly" if sub_idx > 0 else "disabled"
        if hasattr(self, "cb_main_sub_pos") and self.cb_main_sub_pos: self.cb_main_sub_pos.configure(state=pos_st)

    def hide_main_media_bar(self):
        """Hides the Media Settings Bar frame when switching to non-media URLs."""
        if hasattr(self, "media_options_frame"):
            try:
                self.media_options_frame.pack_forget()
            except Exception:
                pass

    def _on_main_quality_changed(self, event=None):
        """Dynamically updates destination filename extension and quality tag when user picks a different quality."""
        if not getattr(self, "_main_media_options", None):
            return
        idx = self.cb_main_quality.current()
        if 0 <= idx < len(self._main_media_options):
            opt = self._main_media_options[idx]
            if event is not None:
                h = getattr(opt, "height", 0) or 0
                if h > 0:
                    try: set_setting("preferred_video_height", h)
                    except Exception: pass
            cur = self.entry_dest.get().strip()
            updated = cur
            if cur:
                sub_mode = "soft_embed"
                if hasattr(self, "cb_main_sub_mode") and hasattr(self, "_main_sub_mode_codes"):
                    m_idx = self.cb_main_sub_mode.current()
                    if 0 <= m_idx < len(self._main_sub_mode_codes):
                        sub_mode = self._main_sub_mode_codes[m_idx]
                updated = apply_media_filename_tags(cur, quality_label=opt.resolution_label, is_sub_burned=(sub_mode == "hard_burn"), ext=opt.ext)
                self.entry_dest.delete(0, tk.END); self.entry_dest.insert(0, updated)

            pending = getattr(self, "_pending_media_context", None)
            if isinstance(pending, dict):
                pending["selected_option"], pending["selected_opt"] = opt, opt
                if updated: pending["final_dest"] = updated
                u = pending.get("url")
                staged = getattr(self, "_staged_links", [])
                if u and any(it.get("url") == u for it in staged):
                    try:
                        from smart_download.ui.panels.kanban_staged_helpers import stage_media_option_in_col1
                        raw_title = pending.get("raw_title") or (pending.get("info", {}).get("title") if isinstance(pending.get("info"), dict) else "")
                        dur = pending.get("duration") or (pending.get("info", {}).get("duration") if isinstance(pending.get("info"), dict) else 0) or 0
                        stage_media_option_in_col1(self, u, raw_title, opt, updated or pending.get("final_dest", ""), dur)
                    except Exception: pass

    def _on_main_audio_changed(self, event=None):
        """Persists preferred audio language when user selects a different audio track."""
        if event is not None and getattr(self, "_main_audio_tracks", None):
            idx = self.cb_main_audio.current()
            if 0 <= idx < len(self._main_audio_tracks):
                track = self._main_audio_tracks[idx]
                lang = track.get("language") or ("original" if idx == 0 else "")
                if lang:
                    try: set_setting("preferred_audio_lang", lang)
                    except Exception: pass

    def _on_main_sub_changed(self, event=None):
        """Enables or disables subtitle mode combobox based on selected subtitle."""
        idx = self.cb_main_sub.current()
        has_s = len(getattr(self, "_main_subtitle_tracks", [])) > 1
        self.cb_main_sub_mode.configure(state="readonly" if has_s else "disabled")
        self.cb_main_sub_pos.configure(state="readonly" if idx > 0 else "disabled")
        if event is not None:
            lang = self._main_subtitle_tracks[idx].get("language") if (0 < idx < len(self._main_subtitle_tracks)) else "none"
            try: set_setting("preferred_subtitle_lang", lang or "none")
            except Exception: pass

    def _on_main_sub_mode_changed(self, event=None):
        """Saves chosen mode, auto-selects Arabic/first subtitle track if None, and reflects [Sub] tag."""
        cur_idx = self.cb_main_sub_mode.current()
        chosen = "soft_embed"
        if 0 <= cur_idx < len(self._main_sub_mode_codes):
            chosen = self._main_sub_mode_codes[cur_idx]
            try: set_setting("subtitle_embed_mode", chosen)
            except Exception: pass
        if self.cb_main_sub.current() <= 0 and len(self._main_subtitle_tracks) > 1:
            ar_idx = next((i for i, s in enumerate(self._main_subtitle_tracks) if i > 0 and str(s.get("language", "")).lower().startswith("ar")), None)
            target_idx = ar_idx if ar_idx is not None else 1
            self.cb_main_sub.current(target_idx)
            self.cb_main_sub_mode.configure(state="readonly")
            self.cb_main_sub_pos.configure(state="readonly")
        cur = self.entry_dest.get().strip()
        if cur and getattr(self, "_main_media_options", None):
            q_idx = self.cb_main_quality.current() if hasattr(self, "cb_main_quality") else 0
            opt = self._main_media_options[q_idx] if (0 <= q_idx < len(self._main_media_options)) else None
            ql = opt.resolution_label if opt else None
            ext = opt.ext if opt else None
            updated = apply_media_filename_tags(cur, quality_label=ql, is_sub_burned=(chosen == "hard_burn"), ext=ext)
            self.entry_dest.delete(0, tk.END); self.entry_dest.insert(0, updated)

    def _on_main_sub_pos_changed(self, event=None):
        """Persists selected subtitle position."""
        cur_idx = self.cb_main_sub_pos.current()
        if 0 <= cur_idx < len(self._main_sub_pos_codes):
            pos = self._main_sub_pos_codes[cur_idx]
            if event is not None:
                try: set_setting("subtitle_position", pos)
                except Exception: pass


__all__ = ["MediaOptionsBarMixin", "MediaOptionsActionsMixin"]

