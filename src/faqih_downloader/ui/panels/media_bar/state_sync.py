"""
MediaBarStateSyncMixin: Synchronization of media selections, staged card contexts, and Kanban models.
"""
import os
import sys
from typing import Optional, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

from ....config import parse_safe_int, get_setting as _cfg_get_setting
from ....utils.file_ops import apply_media_filename_tags
from ....services.youtube_service import VideoFormatOption, format_filesize
from ...modals.quality_modal_helpers import resolve_preferred_option_index


def _get_setting(key: str, default: Any = None) -> Any:
    mod = sys.modules.get("faqih_downloader.ui.panels.media_options_bar")
    if mod and hasattr(mod, "get_setting"):
        return getattr(mod, "get_setting")(key, default)
    return _cfg_get_setting(key, default)


class MediaBarStateSyncMixin:
    """Provides state synchronization between combobox selections and media context."""

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

        ctx_dict = {}
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
        old_ctx = getattr(self, "_pending_media_context", None)
        ext_src = kwargs.get("external_subtitle_tracks")
        if ext_src is None:
            ext_src = ctx_dict.get("external_subtitle_tracks") or getattr(sel_opt, "external_subtitle_tracks", None)
        if not ext_src:
            ext_src = next((getattr(o, "external_subtitle_tracks", None) for o in (self._main_media_options or []) if getattr(o, "external_subtitle_tracks", None)), None)
        if not ext_src and isinstance(old_ctx, dict) and (not media_url or old_ctx.get("url") == media_url):
            ext_src = old_ctx.get("external_subtitle_tracks") or getattr(self, "_main_external_subtitle_tracks", None)
        prev_ext = [dict(t) for t in (ext_src or []) if isinstance(t, dict)]
        for o in ((self._main_media_options or []) + ([sel_opt] if sel_opt is not None else [])):
            try: o.external_subtitle_tracks = [dict(t) for t in prev_ext]
            except Exception: pass
        self._pending_media_context = {
            "url": media_url,
            "info": info or {},
            "options": self._main_media_options,
            "audio_tracks": self._main_audio_tracks,
            "subtitle_tracks": self._main_subtitle_tracks,
            "selected_option": sel_opt,
            "selected_opt": sel_opt,
            "external_subtitle_tracks": prev_ext,
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
        from ....services.media_clipper_engine import estimate_clip_total_bytes
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
        a_idx, pref_a = 0, _get_setting("preferred_audio_lang", "original")
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
        sub_idx, pref_s = 0, _get_setting("preferred_subtitle_lang", "none")
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
        mode = getattr(sel_opt, "subtitle_embed_mode", None) or _get_setting("subtitle_embed_mode", "soft_embed")
        self.cb_main_sub_mode.current(self._main_sub_mode_codes.index(mode) if mode in self._main_sub_mode_codes else 0)

        # 5. Connections / Threads Selection
        cur_conn = str(parse_safe_int(getattr(sel_opt, "max_connections", None))
                       or (parse_safe_int(self.conn_var.get()) if hasattr(self, "conn_var") else None)
                       or parse_safe_int(_get_setting("max_connections", 8)) or 8)
        if hasattr(self, "cb_main_sub_pos") and self.cb_main_sub_pos:
            self.cb_main_sub_pos.set(cur_conn if cur_conn in getattr(self, "_main_conn_values", ["1", "2", "4", "8", "16", "32"]) else "8")
            self.cb_main_sub_pos.configure(state="readonly")

        mode_st = "readonly" if (len(self._main_subtitle_tracks) > 1 and sub_idx > 0) else "disabled"
        if hasattr(self, "cb_main_sub_mode") and self.cb_main_sub_mode: self.cb_main_sub_mode.configure(state=mode_st)

        ext_sel = getattr(sel_opt, "external_subtitle_tracks", None) or (getattr(self, "_pending_media_context", None) or {}).get("external_subtitle_tracks") or []
        if hasattr(self, "set_main_external_subtitles"):
            self.set_main_external_subtitles(ext_sel, sync_state=False)

        # Synchronize context and column 1 card immediately
        self._sync_media_bar_state()

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
            for attr in ("clip_start_sec", "clip_end_sec", "selected_chapter_title", "audio_boost_enabled", "dual_subtitle_enabled", "subtitle_custom_edits", "external_subtitle_tracks", "duration"):
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
        ext_sel = [dict(t) for t in (getattr(self, "_main_external_subtitle_tracks", []) or []) if isinstance(t, dict)]
        for o in (list(ctx.get("options") or []) + list(getattr(self, "_main_media_options", []) or []) + ([opt] if opt else [])):
            try: o.external_subtitle_tracks = [dict(t) for t in ext_sel]
            except Exception: pass
        ctx["external_subtitle_tracks"] = ext_sel
        if opts and hasattr(self, "cb_main_quality"):
            from ....services.media_clipper_engine import estimate_clip_total_bytes
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

        # Update destination path filename tags (only when entry_dest is non-empty; never corrupt a directory into folder.mp4)
        cur_dest = self.entry_dest.get().strip() if hasattr(self, "entry_dest") else ""
        ctx_dest = ctx.get("final_dest", "") or ""
        _is_file = lambda p: bool(p and not os.path.isdir(p) and os.path.splitext(p)[1])
        tag_target = (cur_dest if _is_file(cur_dest) else (ctx_dest if _is_file(ctx_dest) else "")) if cur_dest else ""
        if tag_target and opt:
            is_sub_burned = (sub_mode == "hard_burn") and bool(getattr(opt, "selected_subtitle_track", None))
            updated_dest = apply_media_filename_tags(tag_target, quality_label=opt.resolution_label, is_sub_burned=is_sub_burned, ext=opt.ext)
            if _is_file(cur_dest) and hasattr(self, "entry_dest") and updated_dest != cur_dest:
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
                it["external_subtitle_tracks"] = [dict(t) for t in ext_sel]
                it["final_dest"] = ctx.get("final_dest", "") or cur_dest
                if isinstance(it.get("media_context"), dict):
                    it["media_context"]["selected_option"] = opt
                    it["media_context"]["selected_opt"] = opt
                    it["media_context"]["selected_audio_track"] = getattr(opt, "selected_audio_track", None)
                    it["media_context"]["selected_subtitle_track"] = getattr(opt, "selected_subtitle_track", None)
                    it["media_context"]["subtitle_embed_mode"] = sub_mode
                    it["media_context"]["external_subtitle_tracks"] = [dict(t) for t in ext_sel]
                    for mo in (it["media_context"].get("options") or []):
                        try: mo.external_subtitle_tracks = [dict(t) for t in ext_sel]
                        except Exception: pass
        try:
            from ..kanban_staged_prober import stage_media_option_in_col1
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

__all__ = ["MediaBarStateSyncMixin"]
