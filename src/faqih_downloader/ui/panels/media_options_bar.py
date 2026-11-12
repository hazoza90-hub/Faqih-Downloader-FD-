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

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting, get_base_downloads_dir, parse_safe_int
from faqih_downloader.utils.file_ops import apply_media_filename_tags, generate_unique_destination_path
from faqih_downloader.services.youtube_service import VideoFormatOption, YouTubeResolver, format_filesize, sanitize_filename, is_media_url
from faqih_downloader.services.youtube_tracks import extract_audio_tracks, extract_subtitle_tracks
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
        self.btn_main_advanced = self.btn_reopen_quality

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

        is_ar = (getattr(self, "current_language", "en") == "ar") or (get_setting("language", "ar") == "ar")
        lbl_threads = tr("lbl_main_threads", "⚡ المسارات:" if is_ar else "⚡ Threads:")
        self.lbl_main_sub_pos = tk.Label(row2, text=lbl_threads, font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_bright, width=9, anchor="w")
        self._main_conn_values = ["1", "2", "4", "8", "16", "32"]
        self._main_sub_pos_codes = ["bottom", "middle", "top"]
        self.cb_main_sub_pos = ttk.Combobox(row2, values=self._main_conn_values, state="readonly", font=("Segoe UI", 8), width=8)
        init_conn = str(get_setting("max_connections", 8))
        self.cb_main_sub_pos.set(init_conn if init_conn in self._main_conn_values else "8")
        self.cb_main_conn = self.cb_main_sub_pos
        self.lbl_main_sub_pos.pack(side=tk.LEFT); self.cb_main_sub_pos.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_main_sub_pos.bind("<<ComboboxSelected>>", self._on_main_sub_pos_changed)

    def _on_staged_probe_ready(self, ctx: Dict[str, Any]):
        """Callback invoked immediately when link probe finishes (manual paste or clipboard capture)."""
        if not ctx:
            return
        self._pending_media_context = dict(ctx)
        self.populate_main_media_bar(ctx)
        if hasattr(self, "update_idletasks"):
            try:
                self.update_idletasks()
            except Exception:
                pass

    def populate_main_media_bar(
        self, info: Optional[Dict[str, Any]] = None, options: Optional[List[VideoFormatOption]] = None,
        audio_tracks: Optional[List[Dict[str, Any]]] = None, subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
        selected_option: Optional[VideoFormatOption] = None, url: Optional[str] = None, dest: Optional[str] = None,
        selected_opt: Optional[VideoFormatOption] = None, resolver: Optional[Any] = None, **kwargs
    ):
        """Displays and populates the Main Window Media Settings Bar with resolved formats."""
        if not hasattr(self, "media_options_frame"):
            return

        if isinstance(info, dict) and ("options" in info or "selected_opt" in info or "selected_option" in info):
            ctx_dict = info
            info = ctx_dict.get("info") or ctx_dict.get("stream_info") or {}
            options = options or ctx_dict.get("options") or []
            audio_tracks = audio_tracks or ctx_dict.get("audio_tracks") or []
            subtitle_tracks = subtitle_tracks or ctx_dict.get("subtitle_tracks") or []
            selected_option = selected_option or ctx_dict.get("selected_option") or ctx_dict.get("selected_opt")
            url = url or ctx_dict.get("url")
            dest = dest or ctx_dict.get("final_dest") or ctx_dict.get("dest")
            resolver = resolver or ctx_dict.get("resolver")

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
            "selected_opt": sel_opt,
            "resolver": resolver,
            "final_dest": final_dest
        }
        self._last_media_context = dict(self._pending_media_context)
        self._cache_media_context(media_url, self._pending_media_context)
        self._main_bar_url = media_url

        # Show host frame and options frame directly under top header
        fill_x = tk.X if tk else "x"
        if hasattr(self, "media_bar_host") and self.media_bar_host:
            if hasattr(self, "kanban_container") and self.kanban_container:
                self.media_bar_host.pack(fill=fill_x, before=self.kanban_container, padx=10, pady=2)
            else:
                self.media_bar_host.pack(fill=fill_x, padx=10, pady=2)
        if hasattr(self, "media_options_frame") and self.media_options_frame:
            self.media_options_frame.pack(fill=fill_x, pady=(4, 2))

        # 1. Populate Quality Combobox
        q_vals = []
        info_dur = float((info.get("duration") if isinstance(info, dict) else getattr(info, "duration", 0)) or 0.0)
        from faqih_downloader.services.media_clipper_engine import estimate_clip_total_bytes
        for opt in self._main_media_options:
            if info_dur > 0 and not getattr(opt, "duration", 0): setattr(opt, "duration", info_dur)
            fs = getattr(opt, "filesize_approx", 0) or getattr(opt, "filesize", 0) or 0
            if fs: fs = estimate_clip_total_bytes(opt, int(fs))
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
        sel_at = getattr(sel_opt, "selected_audio_track", None)
        if sel_at and sel_at in self._main_audio_tracks:
            a_idx = self._main_audio_tracks.index(sel_at)
        elif sel_at and isinstance(sel_at, dict):
            for i, t in enumerate(self._main_audio_tracks):
                if t.get("track_id") == sel_at.get("track_id") or (t.get("language") and t.get("language") == sel_at.get("language")):
                    a_idx = i
                    break
        elif pref_a and pref_a != "original":
            for i, t in enumerate(self._main_audio_tracks):
                if str(t.get("language", "")).lower().startswith(pref_a.lower()):
                    a_idx = i; break
        if a_vals:
            self.cb_main_audio.current(a_idx)

        # 3. Populate Subtitles Combobox
        s_vals = [s.get("label", "") for s in self._main_subtitle_tracks]
        self.cb_main_sub.configure(values=s_vals)
        sub_idx, pref_s = 0, get_setting("preferred_subtitle_lang", "none")
        sel_st = getattr(sel_opt, "selected_subtitle_track", None)
        if sel_st and sel_st in self._main_subtitle_tracks:
            sub_idx = self._main_subtitle_tracks.index(sel_st)
        elif sel_st and isinstance(sel_st, dict):
            for i, s in enumerate(self._main_subtitle_tracks):
                if s.get("sub_id") == sel_st.get("sub_id") or (s.get("language") and s.get("language") == sel_st.get("language")):
                    sub_idx = i
                    break
        elif pref_s and pref_s != "none":
            for i, s in enumerate(self._main_subtitle_tracks):
                if i > 0 and str(s.get("language", "")).lower().startswith(pref_s.lower()):
                    sub_idx = i; break
        if s_vals:
            self.cb_main_sub.current(sub_idx)

        # 4. Mode Selection
        mode = getattr(sel_opt, "subtitle_embed_mode", None) or get_setting("subtitle_embed_mode", "soft_embed")
        self.cb_main_sub_mode.current(self._main_sub_mode_codes.index(mode) if mode in self._main_sub_mode_codes else 0)

        # 5. Connections / Threads Selection
        cur_conn = str(parse_safe_int(getattr(sel_opt, "max_connections", None))
                       or (parse_safe_int(self.conn_var.get()) if hasattr(self, "conn_var") else None)
                       or parse_safe_int(get_setting("max_connections", 8)) or 8)
        if hasattr(self, "cb_main_sub_pos") and self.cb_main_sub_pos:
            self.cb_main_sub_pos.set(cur_conn if cur_conn in getattr(self, "_main_conn_values", ["1", "2", "4", "8", "16", "32"]) else "8")
            self.cb_main_sub_pos.configure(state="readonly")

        mode_st = "readonly" if len(self._main_subtitle_tracks) > 1 else "disabled"
        if hasattr(self, "cb_main_sub_mode") and self.cb_main_sub_mode: self.cb_main_sub_mode.configure(state=mode_st)

        # Synchronize context and column 1 card immediately
        self._sync_media_bar_state()

    def hide_main_media_bar(self):
        """Hides the Media Settings Bar frame when switching to non-media URLs."""
        self._main_bar_url = None
        if hasattr(self, "media_options_frame"):
            try: self.media_options_frame.pack_forget()
            except Exception: pass
        if hasattr(self, "media_bar_host") and self.media_bar_host:
            try: self.media_bar_host.pack_forget()
            except Exception: pass

    def _sync_media_bar_state(self, event=None):
        """Synchronizes dropdown selections with _pending_media_context and the Column 1 Kanban card."""
        ctx = getattr(self, "_pending_media_context", None)
        if not isinstance(ctx, dict):
            return

        # Guard: prevent cross-video state corruption if media bar currently belongs to another URL or options mismatch
        bar_url = getattr(self, "_main_bar_url", None)
        if bar_url and ctx.get("url") and bar_url != ctx.get("url"):
            return
        bar_opts = getattr(self, "_main_media_options", []) or []
        ctx_opts = ctx.get("options") or []
        if bar_opts and ctx_opts and bar_opts != ctx_opts:
            return

        opts = ctx_opts or bar_opts
        q_idx = self.cb_main_quality.current() if hasattr(self, "cb_main_quality") else -1
        prev_opt = ctx.get("selected_option") or ctx.get("selected_opt")
        opt = opts[q_idx] if (0 <= q_idx < len(opts)) else prev_opt
        if prev_opt and opt and prev_opt != opt:
            for attr in ("clip_start_sec", "clip_end_sec", "selected_chapter_title", "audio_boost_enabled", "dual_subtitle_enabled", "subtitle_custom_edits", "duration"):
                if hasattr(prev_opt, attr): setattr(opt, attr, getattr(prev_opt, attr))

        # Audio track
        audios = getattr(self, "_main_audio_tracks", []) or ctx.get("audio_tracks") or []
        a_idx = self.cb_main_audio.current() if hasattr(self, "cb_main_audio") else -1
        if opt and 0 <= a_idx < len(audios):
            opt.selected_audio_track = audios[a_idx]
            ctx["selected_audio_track"] = audios[a_idx]

        # Subtitle track
        subs = getattr(self, "_main_subtitle_tracks", []) or ctx.get("subtitle_tracks") or []
        s_idx = self.cb_main_sub.current() if hasattr(self, "cb_main_sub") else -1
        if opt:
            if 0 < s_idx < len(subs):
                opt.selected_subtitle_track = subs[s_idx]
                ctx["selected_subtitle_track"] = subs[s_idx]
            else:
                opt.selected_subtitle_track = None
                ctx["selected_subtitle_track"] = None

        # Subtitle mode
        m_idx = self.cb_main_sub_mode.current() if hasattr(self, "cb_main_sub_mode") else 0
        sub_mode = self._main_sub_mode_codes[m_idx] if (hasattr(self, "_main_sub_mode_codes") and 0 <= m_idx < len(self._main_sub_mode_codes)) else "soft_embed"
        if opt:
            opt.subtitle_embed_mode = sub_mode
            ctx["subtitle_embed_mode"] = sub_mode

        # Connections / Threads and Subtitle position
        cb_pos = getattr(self, "cb_main_sub_pos", None)
        conn_v = str(cb_pos.get() if (cb_pos and hasattr(cb_pos, "get")) else "").strip()
        if conn_v.isdigit() and int(conn_v) in (1, 2, 4, 8, 16, 24, 32):
            conn_int = int(conn_v)
            if opt: opt.max_connections = conn_int
            ctx["max_connections"] = conn_int
            sub_pos = getattr(opt, "subtitle_position", "bottom") or "bottom"
        else:
            p_idx = cb_pos.current() if (cb_pos and hasattr(cb_pos, "current")) else 0
            sub_pos = self._main_sub_pos_codes[p_idx] if (hasattr(self, "_main_sub_pos_codes") and 0 <= p_idx < len(self._main_sub_pos_codes)) else "bottom"
        if opt:
            opt.subtitle_position = sub_pos
            ctx["subtitle_position"] = sub_pos

        ctx["selected_option"] = opt
        ctx["selected_opt"] = opt
        if opts and hasattr(self, "cb_main_quality"):
            from faqih_downloader.services.media_clipper_engine import estimate_clip_total_bytes
            q_vals = []
            for o in opts:
                fs = getattr(o, "filesize_approx", 0) or getattr(o, "filesize", 0) or 0
                if fs: fs = estimate_clip_total_bytes(o, int(fs))
                sz = format_filesize(fs) if fs else "~"
                res_lbl = getattr(o, "resolution_label", "") or getattr(o, "resolution_name", "Video")
                ext = getattr(o, "ext", "mp4").upper()
                q_vals.append(f"{res_lbl} ({ext}) — {sz}")
            self.cb_main_quality.configure(values=q_vals)
            if 0 <= q_idx < len(q_vals): self.cb_main_quality.current(q_idx)

        # Update destination path filename tags
        cur_dest = self.entry_dest.get().strip() if hasattr(self, "entry_dest") else ""
        if cur_dest and opt:
            is_sub_burned = (sub_mode == "hard_burn") and bool(getattr(opt, "selected_subtitle_track", None))
            updated_dest = apply_media_filename_tags(cur_dest, quality_label=opt.resolution_label, is_sub_burned=is_sub_burned, ext=opt.ext)
            if hasattr(self, "entry_dest") and updated_dest != cur_dest:
                end_val = tk.END if tk else "end"
                self.entry_dest.delete(0, end_val)
                self.entry_dest.insert(0, updated_dest)
            ctx["final_dest"] = updated_dest

        # Reflect updated options into Column 1 staged card
        u = ctx.get("url")
        staged = getattr(self, "_staged_links", [])
        for it in staged:
            if it.get("url") == u:
                it["selected_opt"] = opt
                it["final_dest"] = ctx.get("final_dest", "") or cur_dest
                if isinstance(it.get("media_context"), dict):
                    it["media_context"]["selected_option"] = opt
                    it["media_context"]["selected_opt"] = opt
                    it["media_context"]["selected_audio_track"] = getattr(opt, "selected_audio_track", None)
                    it["media_context"]["selected_subtitle_track"] = getattr(opt, "selected_subtitle_track", None)
                    it["media_context"]["subtitle_embed_mode"] = sub_mode
        try:
            from faqih_downloader.ui.panels.kanban_staged_prober import stage_media_option_in_col1
            raw_title = ctx.get("raw_title") or (ctx.get("info", {}).get("title") if isinstance(ctx.get("info"), dict) else "")
            dur = ctx.get("duration") or (ctx.get("info", {}).get("duration") if isinstance(ctx.get("info"), dict) else 0) or 0
            stage_media_option_in_col1(self, u, raw_title, opt, ctx.get("final_dest", "") or cur_dest, dur)
        except Exception:
            pass
        if hasattr(self, "refresh_kanban_col1"):
            try: self.refresh_kanban_col1()
            except Exception: pass
        if hasattr(self, "update_idletasks"):
            try: self.update_idletasks()
            except Exception: pass

    def _on_main_quality_changed(self, event=None):
        """Dynamically updates destination filename extension and quality tag when user picks a different quality."""
        if getattr(self, "_main_media_options", None) and hasattr(self, "cb_main_quality"):
            idx = self.cb_main_quality.current()
            if 0 <= idx < len(self._main_media_options) and event is not None:
                h = getattr(self._main_media_options[idx], "height", 0) or 0
                if h > 0:
                    try: set_setting("preferred_video_height", h)
                    except Exception: pass
        self._sync_media_bar_state(event)

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
        self._sync_media_bar_state(event)

    def _on_main_sub_changed(self, event=None):
        """Enables or disables subtitle mode combobox based on selected subtitle."""
        idx = self.cb_main_sub.current()
        has_s = len(getattr(self, "_main_subtitle_tracks", [])) > 1
        if hasattr(self, "cb_main_sub_mode"):
            self.cb_main_sub_mode.configure(state="readonly" if has_s else "disabled")
        if hasattr(self, "cb_main_sub_pos"):
            self.cb_main_sub_pos.configure(state="readonly")
        if event is not None and getattr(self, "_main_subtitle_tracks", None):
            lang = self._main_subtitle_tracks[idx].get("language") if (0 < idx < len(self._main_subtitle_tracks)) else "none"
            try: set_setting("preferred_subtitle_lang", lang or "none")
            except Exception: pass
        self._sync_media_bar_state(event)

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
        self._sync_media_bar_state(event)

    def _on_main_sub_pos_changed(self, event=None):
        """Persists selected thread/connection count or fallback subtitle position."""
        val = str(self.cb_main_sub_pos.get() if hasattr(self.cb_main_sub_pos, "get") else "").strip()
        if val.isdigit() and int(val) in (1, 2, 4, 8, 16, 24, 32):
            try:
                set_setting("max_connections", int(val))
                if hasattr(self, "conn_var"): self.conn_var.set(val)
            except Exception: pass
        else:
            cur_idx = self.cb_main_sub_pos.current() if hasattr(self.cb_main_sub_pos, "current") else -1
            if 0 <= cur_idx < len(getattr(self, "_main_sub_pos_codes", [])):
                pos = self._main_sub_pos_codes[cur_idx]
                if event is not None:
                    try: set_setting("subtitle_position", pos)
                    except Exception: pass
        self._sync_media_bar_state(event)


__all__ = ["MediaOptionsBarMixin", "MediaOptionsActionsMixin"]

