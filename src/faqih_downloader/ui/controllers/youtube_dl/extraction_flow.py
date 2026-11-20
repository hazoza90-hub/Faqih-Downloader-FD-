"""
YouTubeExtractionFlowMixin: Format probing, quality analysis, and quality selection dialog flow.
"""
import os
import sys
import threading
from typing import Dict, Any, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ....i18n import tr
from ....config import get_base_downloads_dir, get_setting, parse_safe_int
from ....utils.file_ops import (
    resolve_categorized_path,
    generate_unique_destination_path,
    apply_media_filename_tags,
)
from ....services.youtube_service import (
    YouTubeResolver,
    VideoFormatOption,
    extract_media_platform,
    sanitize_filename,
)
from ....services.youtube_tracks import extract_audio_tracks, extract_subtitle_tracks
from ...modals.quality_modal import QualitySelectionModal
from ...modals.confirm_modal import DownloadConfirmationModal
from ...modals.quality_modal_helpers import resolve_preferred_option_index


def _get_thread_cls():
    mod = sys.modules.get("faqih_downloader.ui.controllers.youtube_download_controller")
    if mod and hasattr(mod, "threading") and hasattr(getattr(mod, "threading"), "Thread"):
        return getattr(getattr(mod, "threading"), "Thread")
    return threading.Thread


def _get_quality_modal_cls():
    mod = sys.modules.get("faqih_downloader.ui.controllers.youtube_download_controller")
    if mod and hasattr(mod, "QualitySelectionModal"):
        return getattr(mod, "QualitySelectionModal")
    return QualitySelectionModal


class YouTubeExtractionFlowMixin:
    """Handles YouTube & social media stream format analysis and quality dialogs."""

    def _start_youtube_download(
        self,
        url: str,
        dest: str,
        max_conn: Optional[int] = None,
        bytes_limit: float = 0.0,
        modal: Optional[Any] = None
    ):
        conn_arg = parse_safe_int(max_conn)
        if conn_arg is None:
            max_conn = (parse_safe_int(self.conn_var.get()) if hasattr(self, "conn_var") else None) or parse_safe_int(get_setting("max_connections", 8)) or 8
        else:
            max_conn = conn_arg
        # Instant 0ms cached reopen if metadata context is already available
        cached_ctx = self._get_cached_media_context(url) if hasattr(self, "_get_cached_media_context") else None
        if cached_ctx and cached_ctx.get("options") and hasattr(self, "_show_cached_quality_modal"):
            self._show_cached_quality_modal(cached_ctx, preferred_dest=dest)
            return

        is_busy = bool(self.engine and getattr(self.engine, "is_running", False))

        if hasattr(self, "_yt_cancel_event") and self._yt_cancel_event and not is_busy:
            try:
                self._yt_cancel_event.set()
            except Exception:
                pass
        self._yt_cancel_event = threading.Event()

        if hasattr(self, "_confirm_modal") and self._confirm_modal:
            try:
                if self._confirm_modal.winfo_exists() and not getattr(self._confirm_modal, "is_in_progress_view", False):
                    self._confirm_modal.destroy()
                    self._confirm_modal = None
            except Exception:
                pass

        if hasattr(self, "_candidates_modal") and self._candidates_modal:
            try:
                if self._candidates_modal.winfo_exists():
                    self._candidates_modal.destroy()
                    self._candidates_modal = None
            except Exception:
                pass
        if not is_busy:
            try:
                self.btn_start.configure(state="disabled")
                self.btn_pause.configure(state="disabled")
                self.btn_cancel.configure(state="normal")
                if hasattr(self, "btn_refresh_link"):
                    self.btn_refresh_link.configure(state="normal", bg=self.c_panel_light, fg=self.c_accent)
                self.txt_log.delete("1.0", tk.END)

                for item in self.tree_chunks.get_children():
                    self.tree_chunks.delete(item)
                self._draw_main_progress(0.0)
                self._draw_chunk_segments([])
                self.card_size.configure(text="Fetching available formats...")
            except Exception:
                pass

        plat = extract_media_platform(url)
        tag = plat.upper().replace(" / X", "")
        self.log(f"[{tag}] Detected {plat} stream URL: {url}")
        self.log(f"[{tag}] Querying available video resolutions and formats via yt-dlp...")

        # Always display sleek frameless fetching indicator toast with cancel handler
        try:
            self._show_fetching_toast(url, on_cancel=lambda: self._yt_cancel_event.set())
        except Exception:
            pass

        def _resolve_and_prompt():
            if self._yt_cancel_event.is_set():
                if hasattr(self, "_close_fetching_toast"):
                    self._close_fetching_toast()
                return
            try:
                resolver = YouTubeResolver(
                    on_log=self.log,
                    cookies_from_browser=getattr(self, "cookies_browser", "auto"),
                    cookies_file=getattr(self, "cookies_file", "")
                )
                info, options = resolver.extract_format_options(url)
                audio_tracks = extract_audio_tracks(info)
                subtitle_tracks = extract_subtitle_tracks(info)

                if self._yt_cancel_event.is_set():
                    if hasattr(self, "_close_fetching_toast"):
                        self._close_fetching_toast()
                    self.log(f"[{tag}] Quality analysis cancelled.")
                    return

                if not options:
                    raise RuntimeError(f"No downloadable media formats found for this {plat} video.")

                raw_title = info.get("title") or f"{plat}_Video"
                clean_title = sanitize_filename(raw_title)
                duration = int(info.get("duration") or 0)

                downloads_dir = self._get_base_downloads_dir() if hasattr(self, "_get_base_downloads_dir") else get_base_downloads_dir()
                dest_dir = dest if (dest and (os.path.isdir(dest) or not os.path.splitext(dest)[1])) else (os.path.dirname(dest) if dest else downloads_dir)
                if not dest_dir:
                    dest_dir = downloads_dir
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception:
                    pass

                init_idx = resolve_preferred_option_index(options)
                init_opt = options[init_idx] if (options and 0 <= init_idx < len(options)) else (options[0] if options else None)
                initial_ext = getattr(init_opt, "ext", "mp4") if init_opt else "mp4"
                initial_lbl = getattr(init_opt, "resolution_label", "") if init_opt else ""
                initial_fn = f"{clean_title}.{initial_ext}"
                if getattr(self, "auto_categorize_folders", True) and hasattr(self, "_is_downloads_or_category_subfolder") and self._is_downloads_or_category_subfolder(dest_dir, downloads_dir):
                    initial_dest = resolve_categorized_path(downloads_dir, initial_fn, auto_categorize=True)
                else:
                    initial_dest = os.path.join(dest_dir, initial_fn)
                initial_dest = apply_media_filename_tags(initial_dest, quality_label=initial_lbl, is_sub_burned=False, ext=initial_ext)

                def _show_modal():
                    if self._yt_cancel_event.is_set():
                        if hasattr(self, "_close_fetching_toast"):
                            self._close_fetching_toast()
                        return
                    try:
                        if hasattr(self, "_close_fetching_toast"):
                            self._close_fetching_toast()
                        if self._yt_cancel_event.is_set():
                            return

                        self.card_size.configure(text="Select Quality")

                        def _on_confirm(selected_opt: VideoFormatOption, final_dest: str):
                            self._quality_modal = None
                            if hasattr(self, "clear_last_clipboard_url"):
                                self.clear_last_clipboard_url()
                            try:
                                stream_info = resolver.build_stream_info(info, selected_opt)
                                is_hidden = self.is_window_hidden_or_minimized() if hasattr(self, "is_window_hidden_or_minimized") else False
                                yt_prog_modal = None
                                if is_hidden:
                                    yt_prog_modal = DownloadConfirmationModal(
                                        parent=self.root,
                                        url=url,
                                        default_dest_path=final_dest,
                                        theme=self._theme_dict(),
                                        parent_app=self,
                                        show_progress_immediately=True
                                    )
                                live_conn = parse_safe_int(getattr(selected_opt, "max_connections", None)) or (parse_safe_int(self.conn_var.get()) if hasattr(self, "conn_var") else None) or parse_safe_int(get_setting("max_connections", 8)) or 8
                                self._launch_stream_coordinator(stream_info, final_dest, live_conn, bytes_limit, yt_modal=yt_prog_modal)
                            except Exception as e:
                                self._quality_modal = None
                                self.log(f"[{tag} START ERROR] {e}")
                                self._engine_error_cb(str(e))

                        def _on_open_in_main(selected_opt: VideoFormatOption, final_dest: str):
                            self._quality_modal = None
                            if hasattr(self, "clear_last_clipboard_url"):
                                self.clear_last_clipboard_url()
                            if hasattr(self, "restore_window"):
                                self.restore_window()
                            try:
                                self.entry_url.delete(0, tk.END)
                                self.entry_url.insert(0, url)
                                self.entry_dest.delete(0, tk.END)
                                self.entry_dest.insert(0, final_dest)
                                self.btn_start.configure(state="normal")
                                self.btn_pause.configure(state="disabled")
                                self.btn_cancel.configure(state="disabled")
                                self.card_size.configure(text=tr("status_ready", "Ready"))
                                self._pending_media_context = {
                                    "url": url,
                                    "info": info,
                                    "options": options,
                                    "audio_tracks": audio_tracks,
                                    "subtitle_tracks": subtitle_tracks,
                                    "selected_option": selected_opt,
                                    "resolver": resolver,
                                    "final_dest": final_dest
                                }
                                self._last_media_context = dict(self._pending_media_context)
                                if hasattr(self, "populate_main_media_bar"):
                                    self.populate_main_media_bar(
                                        url=url,
                                        dest=final_dest,
                                        info=info,
                                        options=options,
                                        selected_opt=selected_opt,
                                        audio_tracks=audio_tracks,
                                        subtitle_tracks=subtitle_tracks,
                                        resolver=resolver
                                    )
                                try:
                                    from ..kanban_staged_helpers import stage_media_option_in_col1
                                    dur = info.get("duration", 0) if isinstance(info, dict) else 0
                                    raw_title = info.get("title", "") if isinstance(info, dict) else ""
                                    stage_media_option_in_col1(self, url, raw_title, selected_opt, final_dest, dur)
                                except Exception:
                                    pass
                                self.log(f"[{tag}] Ready in main window with selected media options.")
                            except Exception as e:
                                self._quality_modal = None
                                self.log(f"[{tag} OPEN IN MAIN ERROR] {e}")

                        def _on_cancel():
                            self._quality_modal = None
                            if hasattr(self, "clear_last_clipboard_url"):
                                self.clear_last_clipboard_url()
                            try:
                                self.btn_start.configure(state="normal")
                                self.btn_pause.configure(state="disabled")
                                self.btn_cancel.configure(state="disabled")
                                self.card_size.configure(text=tr("status_ready", "Ready"))
                            except Exception:
                                pass
                            self.log(f"[{tag}] Video quality selection cancelled.")

                        theme_dict = self._theme_dict() if hasattr(self, "_theme_dict") else {
                            "c_bg": getattr(self, "c_bg", "#0f172a"),
                            "c_panel": getattr(self, "c_panel", "#1e293b"),
                            "c_panel_light": getattr(self, "c_panel_light", "#334155"),
                            "c_border": getattr(self, "c_border", "#475569"),
                            "c_accent": getattr(self, "c_accent", "#38bdf8"),
                            "c_accent_dark": getattr(self, "c_accent_dark", "#0284c7"),
                            "c_success": getattr(self, "c_success", "#10b981"),
                            "c_danger": getattr(self, "c_danger", "#ef4444"),
                            "c_text_bright": getattr(self, "c_text_bright", "#f8fafc"),
                            "c_text_muted": getattr(self, "c_text_muted", "#94a3b8"),
                            "c_input_bg": getattr(self, "c_input_bg", "#090d16")
                        }

                        # Close fetching toast immediately before displaying quality modal
                        if hasattr(self, "_close_fetching_toast") and callable(self._close_fetching_toast):
                            try:
                                self._close_fetching_toast()
                            except Exception:
                                pass

                        # Dismiss any previously open quality modal
                        if hasattr(self, "_quality_modal") and self._quality_modal:
                            try:
                                if self._quality_modal.winfo_exists():
                                    self._quality_modal.destroy()
                            except Exception:
                                pass
                            self._quality_modal = None

                        if hasattr(self, "_confirm_modal") and self._confirm_modal:
                            try:
                                if self._confirm_modal.winfo_exists() and not getattr(self._confirm_modal, "is_in_progress_view", False):
                                    self._confirm_modal.destroy()
                                    self._confirm_modal = None
                            except Exception:
                                pass

                        if hasattr(self, "_candidates_modal") and self._candidates_modal:
                            try:
                                if self._candidates_modal.winfo_exists():
                                    self._candidates_modal.destroy()
                                    self._candidates_modal = None
                            except Exception:
                                pass

                        self._pending_media_context = {
                            "url": url,
                            "info": info,
                            "options": options,
                            "audio_tracks": audio_tracks,
                            "subtitle_tracks": subtitle_tracks,
                            "selected_option": init_opt,
                            "selected_opt": init_opt,
                            "resolver": resolver,
                            "final_dest": initial_dest,
                            "raw_title": raw_title,
                            "duration": duration
                        }
                        self._last_media_context = dict(self._pending_media_context)
                        if hasattr(self, "_cache_media_context"):
                            self._cache_media_context(url, self._last_media_context)

                        if hasattr(self, "_on_staged_probe_ready"):
                            try: self._on_staged_probe_ready(self._pending_media_context)
                            except Exception: pass
                        elif hasattr(self, "populate_main_media_bar"):
                            try: self.populate_main_media_bar(self._pending_media_context)
                            except Exception: pass

                        try:
                            from ...panels.kanban_staged_prober import stage_media_option_in_col1
                            stage_media_option_in_col1(self, url, raw_title, init_opt, initial_dest, duration)
                        except Exception:
                            pass

                        if hasattr(self, "update_idletasks"):
                            try: self.update_idletasks()
                            except Exception: pass

                        q_modal_cls = _get_quality_modal_cls()
                        self._quality_modal = q_modal_cls(
                            parent=self.root,
                            video_title=raw_title,
                            duration=duration,
                            options=options,
                            default_dest_path=initial_dest,
                            theme=theme_dict,
                            on_confirm=_on_confirm,
                            on_cancel=_on_cancel,
                            on_open_in_main=_on_open_in_main,
                            parent_app=self,
                            audio_tracks=audio_tracks,
                            subtitle_tracks=subtitle_tracks,
                            video_url=url,
                            raw_info=info
                        )
                    except Exception as e:
                        self._quality_modal = None
                        if hasattr(self, "clear_last_clipboard_url"):
                            self.clear_last_clipboard_url()
                        self.log(f"[{tag} MODAL ERROR] {e}")
                        self._engine_error_cb(str(e))

                try:
                    self.dispatch_to_main_thread(_show_modal)
                except Exception:
                    pass

            except Exception as e:
                err_msg = str(e)
                if hasattr(self, "clear_last_clipboard_url"):
                    self.clear_last_clipboard_url()
                if not self._yt_cancel_event.is_set():
                    self.log(f"[{tag} ERROR] {err_msg}")
                    try:
                        self.dispatch_to_main_thread(lambda msg=err_msg: self._engine_error_cb(msg))
                    except Exception:
                        pass
            finally:
                if hasattr(self, "_close_fetching_toast"):
                    try:
                        self.dispatch_to_main_thread(self._close_fetching_toast)
                    except Exception:
                        pass
                if hasattr(self, "remove_parsing_link"):
                    try:
                        self.dispatch_to_main_thread(lambda: self.remove_parsing_link(url))
                    except Exception:
                        pass

        thread_cls = _get_thread_cls()
        resolve_thread = thread_cls(target=_resolve_and_prompt, daemon=True)
        resolve_thread.start()

    _start_media_download = _start_youtube_download


__all__ = ["YouTubeExtractionFlowMixin"]
