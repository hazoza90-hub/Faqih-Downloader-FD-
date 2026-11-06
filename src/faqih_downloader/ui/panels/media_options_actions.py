"""
MediaOptionsActionsMixin: Actions, modal triggers, preview handlers, and download starters
for the Media Options Bar in Smart Download (SD).
"""
import os
import copy
from typing import Optional, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_base_downloads_dir
from faqih_downloader.utils.file_ops import apply_media_filename_tags, generate_unique_destination_path
from faqih_downloader.services.youtube_service import VideoFormatOption, YouTubeResolver, sanitize_filename
from ..modals.quality_modal import QualitySelectionModal
from ..modals.confirm_modal import DownloadConfirmationModal
from ..modals.quality_modal_helpers import resolve_preferred_option_index


class MediaOptionsActionsMixin:
    """Mixin handling actions, modal reopening, preview launches, and download executions."""

    def _get_cached_media_context(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached media options context by full URL or extracted video ID for 0ms reopen."""
        if not url:
            return None
        cache = getattr(self, "_media_context_cache", None)
        if cache and isinstance(cache, dict):
            if url in cache:
                return cache[url]
            clean_url = url.split("&")[0].strip() if "?" in url else url.strip()
            if clean_url in cache:
                return cache[clean_url]
            for k, ctx in cache.items():
                info = ctx.get("info") or {}
                vid = info.get("id") or info.get("display_id")
                if vid and (str(vid) in url or str(vid) == url):
                    return ctx
        for ctx_attr in ("_pending_media_context", "_last_media_context"):
            ctx = getattr(self, ctx_attr, None)
            if ctx and isinstance(ctx, dict):
                ctx_url = ctx.get("url") or ""
                info = ctx.get("info") or {}
                vid = info.get("id") or info.get("display_id")
                if (ctx_url and (ctx_url == url or ctx_url.split("&")[0] == url.split("&")[0])) or (vid and (str(vid) in url or str(vid) == url)):
                    return ctx
        return None

    def _cache_media_context(self, url: str, ctx: Dict[str, Any]):
        """Caches media format context by full URL and extracted video ID for 0ms reopen."""
        if not hasattr(self, "_media_context_cache") or self._media_context_cache is None:
            self._media_context_cache = {}
        if url:
            self._media_context_cache[url] = ctx
            clean = url.split("&")[0].strip() if "?" in url else url.strip()
            self._media_context_cache[clean] = ctx
        info = ctx.get("info") or {}
        vid = info.get("id") or info.get("display_id")
        if vid:
            for v in (str(vid), f"https://www.youtube.com/watch?v={vid}", f"https://youtu.be/{vid}"):
                self._media_context_cache[v] = ctx

    def _reopen_media_quality_modal(self):
        """Opens or re-opens QualitySelectionModal so user can reconfigure quality and subtitles."""
        url = self.entry_url.get().strip() if hasattr(self, "entry_url") else ""
        dest = self.entry_dest.get().strip() if hasattr(self, "entry_dest") else ""
        if not url:
            msg = tr("err_empty_url", "Please enter a valid URL first!")
            if hasattr(self, "show_toast"):
                self.show_toast(msg, icon="⚠️")
            elif hasattr(self, "log"):
                self.log(msg)
            return

        ctx = self._get_cached_media_context(url)
        if not ctx:
            ctx = getattr(self, "_pending_media_context", None) or getattr(self, "_last_media_context", None)
            if ctx and ctx.get("url") != url:
                ctx = None
        if ctx and ctx.get("options"):
            self._show_cached_quality_modal(ctx)
            return

        if hasattr(self, "_start_youtube_download"):
            self._start_youtube_download(url, dest)

    def _show_cached_quality_modal(self, ctx: Dict[str, Any], preferred_dest: Optional[str] = None):
        """Displays QualitySelectionModal instantaneously from cached metadata context."""
        info, options = ctx["info"], [copy.copy(o) for o in ctx.get("options", [])]
        raw_title, duration = info.get("title") or "Video", int(info.get("duration") or 0)
        theme_dict = self._theme_dict() if hasattr(self, "_theme_dict") else {}
        clean_title = sanitize_filename(raw_title)
        cached_opt = ctx.get("selected_option")
        first_opt = cached_opt if (cached_opt and cached_opt in options) else (options[resolve_preferred_option_index(options)] if options else None)
        first_ext = first_opt.ext if first_opt else "mp4"
        first_lbl = first_opt.resolution_label if first_opt else ""

        base_dl = self._get_base_downloads_dir() if hasattr(self, "_get_base_downloads_dir") else get_base_downloads_dir()
        target_dest = preferred_dest if (preferred_dest and clean_title.lower() in os.path.basename(preferred_dest).lower()) else (ctx.get("final_dest") or preferred_dest or os.path.join(base_dl, f"{clean_title}.{first_ext}"))
        initial_dest = apply_media_filename_tags(target_dest, quality_label=first_lbl, is_sub_burned=False, ext=first_ext)
        reserved = self.history_manager.get_active_or_queued_paths() if getattr(self, "history_manager", None) else None
        dest = generate_unique_destination_path(initial_dest, reserved_paths=reserved)
        resolver = ctx.get("resolver") or (YouTubeResolver(on_log=self.log, cookies_from_browser=getattr(self, "cookies_browser", "auto"), cookies_file=getattr(self, "cookies_file", "")) if hasattr(self, "log") else None)

        def _on_confirm(selected_opt: VideoFormatOption, final_dest: str):
            self._quality_modal = None
            if hasattr(self, "clear_last_clipboard_url"):
                self.clear_last_clipboard_url()
            stream_info = resolver.build_stream_info(info, selected_opt) if (resolver and selected_opt) else None
            try:
                max_conn = int(self.conn_var.get())
            except Exception:
                max_conn = 8
            try:
                kb_lim = float(self.entry_custom_speed.get().strip())
            except Exception:
                kb_lim = 0.0
            yt_modal = DownloadConfirmationModal(parent=self.root, url=ctx.get("url", ""), default_dest_path=final_dest, theme=self._theme_dict(), parent_app=self, show_progress_immediately=True) if getattr(self, "is_window_hidden_or_minimized", lambda: False)() else None
            if stream_info and hasattr(self, "_launch_stream_coordinator"):
                self._launch_stream_coordinator(stream_info, final_dest, max_conn, kb_lim * 1024.0, yt_modal=yt_modal)

        def _on_open_in_main(selected_opt: VideoFormatOption, final_dest: str):
            self._quality_modal = None
            if hasattr(self, "clear_last_clipboard_url"):
                self.clear_last_clipboard_url()
            if hasattr(self, "restore_window"):
                self.restore_window()
            try:
                self.entry_url.delete(0, tk.END)
                self.entry_url.insert(0, ctx["url"])
                self.entry_dest.delete(0, tk.END)
                self.entry_dest.insert(0, final_dest)
            except Exception:
                pass
            ctx["selected_option"], ctx["final_dest"] = selected_opt, final_dest
            self.populate_main_media_bar(info, options, ctx.get("audio_tracks", []), ctx.get("subtitle_tracks", []), selected_option=selected_opt)
            try:
                from faqih_downloader.ui.panels.kanban_staged_helpers import stage_media_option_in_col1
                dur = info.get("duration", 0) if isinstance(info, dict) else 0
                stage_media_option_in_col1(self, ctx.get("url", ""), raw_title, selected_opt, final_dest, dur)
            except Exception:
                pass
            try:
                self.btn_start.configure(state="normal")
                self.btn_pause.configure(state="disabled")
                self.btn_cancel.configure(state="disabled")
                self.card_size.configure(text=tr("status_ready", "Ready"))
            except Exception:
                pass

        if hasattr(self, "_quality_modal") and self._quality_modal:
            try:
                if self._quality_modal.winfo_exists():
                    self._quality_modal.destroy()
            except Exception:
                pass
            self._quality_modal = None

        self._quality_modal = QualitySelectionModal(
            parent=self.root, video_title=raw_title, duration=duration, options=options, default_dest_path=dest,
            theme=theme_dict, on_confirm=_on_confirm, on_cancel=lambda: setattr(self, "_quality_modal", None),
            on_open_in_main=_on_open_in_main, parent_app=self, audio_tracks=ctx.get("audio_tracks", []),
            subtitle_tracks=ctx.get("subtitle_tracks", []), video_url=ctx.get("url", ""), raw_info=info
        )

    def _open_main_media_preview(self):
        """Launches in-app VidMate-style preview directly from the Main Window Media Bar."""
        ctx = getattr(self, "_pending_media_context", None) or {}
        url = ctx.get("url") or (self.entry_url.get().strip() if hasattr(self, "entry_url") else "")
        info = ctx.get("info") or getattr(self, "_last_yt_info", {}) or {}
        raw_title = info.get("title") or ctx.get("title") or "Video Preview"
        opts = getattr(self, "_main_media_options", ctx.get("options", []))
        auds = getattr(self, "_main_audio_tracks", ctx.get("audio_tracks", []))
        subs = getattr(self, "_main_subtitle_tracks", ctx.get("subtitle_tracks", []))
        if hasattr(self, "cb_main_quality") and opts and 0 <= self.cb_main_quality.current() < len(opts):
            q_idx = self.cb_main_quality.current()
        elif ctx.get("selected_option") and ctx.get("selected_option") in opts:
            q_idx = opts.index(ctx["selected_option"])
        else:
            q_idx = resolve_preferred_option_index(opts)
        sel_opt = opts[q_idx] if (opts and 0 <= q_idx < len(opts)) else None
        sel_aud = auds[self.cb_main_audio.current()] if hasattr(self, "cb_main_audio") and auds and 0 <= self.cb_main_audio.current() < len(auds) else None
        sel_sub = subs[self.cb_main_sub.current()] if hasattr(self, "cb_main_sub") and subs and 0 <= self.cb_main_sub.current() < len(subs) else None
        theme_d = getattr(self, "_theme_dict", None) or ({"c_bg": self.c_bg, "c_panel": self.c_panel, "c_panel_light": self.c_panel_light, "c_border": self.c_border, "c_accent": self.c_accent, "c_accent_dark": self.c_accent_dark, "c_success": self.c_success, "c_text_bright": self.c_text_bright, "c_text_muted": self.c_text_muted, "c_input_bg": self.c_input_bg} if hasattr(self, "c_bg") else {})
        dest_p = (self.entry_dest.get().strip() if hasattr(self, "entry_dest") else "") or (self.dest_input.get().strip() if hasattr(self, "dest_input") else "")
        sel_mode = self._main_sub_mode_codes[self.cb_main_sub_mode.current()] if (hasattr(self, "cb_main_sub_mode") and hasattr(self, "_main_sub_mode_codes") and 0 <= self.cb_main_sub_mode.current() < len(self._main_sub_mode_codes)) else "hard_burn"
        sel_pos = self._main_sub_pos_codes[self.cb_main_sub_pos.current()] if (hasattr(self, "cb_main_sub_pos") and hasattr(self, "_main_sub_pos_codes") and 0 <= self.cb_main_sub_pos.current() < len(self._main_sub_pos_codes)) else "bottom"

        def _sync_ui(opt, dst, stage_col1: bool = True):
            if opt and opts and hasattr(self, "cb_main_quality"):
                for i, o in enumerate(opts):
                    if o == opt or getattr(o, "format_id", None) == getattr(opt, "format_id", None):
                        self.cb_main_quality.current(i)
                        break
            sel_a = getattr(opt, "selected_audio_track", None)
            if auds and sel_a and hasattr(self, "cb_main_audio"):
                for i, a in enumerate(auds):
                    if a == sel_a or a.get("track_id") == sel_a.get("track_id"):
                        self.cb_main_audio.current(i)
                        break
            sel_s = getattr(opt, "selected_subtitle_track", None)
            if subs and hasattr(self, "cb_main_sub"):
                for i, s in enumerate(subs):
                    if (sel_s and (s == sel_s or s.get("sub_id") == sel_s.get("sub_id"))) or (not sel_s and i == 0):
                        self.cb_main_sub.current(i)
                        if hasattr(self, "cb_main_sub_mode"):
                            self.cb_main_sub_mode.configure(state="readonly" if len(subs) > 1 else "disabled")
                        if hasattr(self, "cb_main_sub_pos"):
                            self.cb_main_sub_pos.configure(state="readonly" if i > 0 else "disabled")
                        break
            sm = getattr(opt, "subtitle_embed_mode", None)
            if sm and hasattr(self, "cb_main_sub_mode") and hasattr(self, "_main_sub_mode_codes") and sm in self._main_sub_mode_codes:
                self.cb_main_sub_mode.current(self._main_sub_mode_codes.index(sm))
            sp = getattr(opt, "subtitle_position", None)
            if sp and hasattr(self, "cb_main_sub_pos") and hasattr(self, "_main_sub_pos_codes") and sp in self._main_sub_pos_codes:
                self.cb_main_sub_pos.current(self._main_sub_pos_codes.index(sp))
            if dst and hasattr(self, "entry_dest") and self.entry_dest and tk:
                self.entry_dest.delete(0, tk.END)
                self.entry_dest.insert(0, dst)
            ctx["selected_option"] = opt
            if dst:
                ctx["final_dest"] = dst
            self._pending_media_context = dict(ctx)
            if stage_col1:
                target_gui = getattr(self, "gui", self)
                try:
                    from faqih_downloader.ui.panels.kanban_staged_helpers import stage_media_option_in_col1
                    dur = info.get("duration", 0) if isinstance(info, dict) else 0
                    stage_media_option_in_col1(target_gui, url, raw_title, opt, dst or ctx.get("final_dest", ""), dur)
                except Exception:
                    pass

        def _on_preview_confirm(selected_opt, final_dest):
            _sync_ui(selected_opt, final_dest, stage_col1=False)
            try:
                max_conn = int(self.conn_var.get())
            except Exception:
                max_conn = 8
            try:
                bytes_limit = max(0.0, float(self.entry_custom_speed.get().strip())) * 1024.0
            except Exception:
                bytes_limit = 0.0
            resolver = ctx.get("resolver") or (YouTubeResolver(on_log=self.log, cookies_from_browser=getattr(self, "cookies_browser", "auto"), cookies_file=getattr(self, "cookies_file", "")) if hasattr(self, "log") else None)
            stream_info = resolver.build_stream_info(info, selected_opt) if (resolver and selected_opt) else None
            self._last_media_context = {**dict(ctx), "selected_option": selected_opt, "final_dest": final_dest}
            self._pending_media_context = None
            if stream_info and hasattr(self, "_launch_stream_coordinator"):
                self._launch_stream_coordinator(stream_info, final_dest, max_conn, bytes_limit)

        try:
            from ..modals.video_preview_modal import open_video_preview
            open_video_preview(
                parent=self.root if hasattr(self, "root") else None, url=url, video_title=raw_title,
                stream_info=sel_opt, info_dict=info, selected_sub_track=sel_sub, theme=theme_d,
                selected_audio_track=sel_aud, options=opts, audio_tracks=auds, subtitle_tracks=subs,
                default_dest_path=dest_p, on_confirm=_on_preview_confirm,
                on_open_in_main=lambda opt, dst: _sync_ui(opt, dst),
                parent_app=self, on_log=self.log if hasattr(self, "log") else print,
                subtitle_embed_mode=sel_mode, selected_q_idx=q_idx, subtitle_position=sel_pos,
            )
        except Exception as e:
            if hasattr(self, "log"):
                self.log(f"[PREVIEW ERROR] {e}")

    def _start_pending_media_download(self):
        """Starts media download directly using the selections made in the Main Window Media Bar."""
        if hasattr(self, "_sync_media_bar_state"):
            try: self._sync_media_bar_state()
            except Exception: pass
        ctx = getattr(self, "_pending_media_context", None)
        if not ctx:
            return
        if hasattr(self, "remove_staged_link"):
            self.remove_staged_link(ctx.get("url", ""))

        ctx_opts = ctx.get("options") or []
        bar_opts = getattr(self, "_main_media_options", None) or []
        options = ctx_opts if ctx_opts else bar_opts
        audio_tracks = (ctx.get("audio_tracks") or getattr(self, "_main_audio_tracks", None) or [])
        subtitle_tracks = (ctx.get("subtitle_tracks") or getattr(self, "_main_subtitle_tracks", None) or [])
        info, resolver = ctx.get("info", {}), ctx.get("resolver")

        selected_opt = ctx.get("selected_option") or ctx.get("selected_opt")
        if hasattr(self, "cb_main_quality") and options and bar_opts == options:
            q_idx = self.cb_main_quality.current()
            if 0 <= q_idx < len(options):
                selected_opt = options[q_idx]
        if selected_opt is None and options:
            pref_i = resolve_preferred_option_index(options)
            selected_opt = options[pref_i] if 0 <= pref_i < len(options) else options[0]

        if selected_opt:
            if hasattr(self, "cb_main_audio") and audio_tracks and 0 <= self.cb_main_audio.current() < len(audio_tracks):
                selected_opt.selected_audio_track = audio_tracks[self.cb_main_audio.current()]
            sub_mode = self._main_sub_mode_codes[self.cb_main_sub_mode.current()] if (hasattr(self, "cb_main_sub_mode") and 0 <= self.cb_main_sub_mode.current() < len(self._main_sub_mode_codes)) else "soft_embed"
            selected_opt.subtitle_embed_mode = sub_mode
            sub_pos = self._main_sub_pos_codes[self.cb_main_sub_pos.current()] if (hasattr(self, "cb_main_sub_pos") and hasattr(self, "_main_sub_pos_codes") and 0 <= self.cb_main_sub_pos.current() < len(self._main_sub_pos_codes)) else "bottom"
            selected_opt.subtitle_position = sub_pos

            if hasattr(self, "cb_main_sub") and subtitle_tracks:
                s_idx = self.cb_main_sub.current()
                if 0 < s_idx < len(subtitle_tracks):
                    selected_opt.selected_subtitle_track = subtitle_tracks[s_idx]
                else:
                    selected_opt.selected_subtitle_track = None

        final_dest = (self.entry_dest.get().strip() if hasattr(self, "entry_dest") else "") or ctx.get("final_dest", "")
        if selected_opt:
            is_sub = (getattr(selected_opt, "subtitle_embed_mode", "") == "hard_burn")
            final_dest = apply_media_filename_tags(final_dest, quality_label=selected_opt.resolution_label, is_sub_burned=is_sub, ext=selected_opt.ext)
        reserved = self.history_manager.get_active_or_queued_paths() if (hasattr(self, "history_manager") and self.history_manager) else None
        final_dest = generate_unique_destination_path(final_dest, reserved_paths=reserved)

        try:
            max_conn = int(self.conn_var.get())
        except Exception:
            max_conn = 8
        try:
            bytes_limit = max(0.0, float(self.entry_custom_speed.get().strip())) * 1024.0
        except Exception:
            bytes_limit = 0.0

        if not resolver and hasattr(self, "log"):
            resolver = YouTubeResolver(on_log=self.log, cookies_from_browser=getattr(self, "cookies_browser", "auto"), cookies_file=getattr(self, "cookies_file", ""))
        stream_info = resolver.build_stream_info(info, selected_opt) if (resolver and selected_opt) else None
        self._last_media_context = {**dict(ctx), "selected_option": selected_opt, "final_dest": final_dest}
        self._pending_media_context = None

        if stream_info and hasattr(self, "_launch_stream_coordinator"):
            self._launch_stream_coordinator(stream_info, final_dest, max_conn, bytes_limit)


__all__ = ["MediaOptionsActionsMixin"]
