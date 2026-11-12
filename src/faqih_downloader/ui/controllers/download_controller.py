"""
Download execution, progress coordination, and lifecycle controller mixin for Smart Download (SD).
"""
import os
import sys
import threading
from typing import Optional, Callable, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None  # type: ignore
    messagebox = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.core import TurboDownloadEngine, StreamDownloadCoordinator
from faqih_downloader.services.youtube_service import (
    YouTubeResolver,
    VideoFormatOption,
    is_media_url,
    extract_media_platform,
    sanitize_filename,
)
from faqih_downloader.utils import resolve_categorized_path, derive_download_filename, generate_unique_destination_path, get_base_downloads_dir
from faqih_downloader.ui.modals.quality_modal import QualitySelectionModal
from faqih_downloader.ui.modals.confirm_modal import DownloadConfirmationModal
from faqih_downloader.ui.modals.candidates_modal import MultipleCandidatesModal
from faqih_downloader.ui.modals.refresh_modal import RefreshLinkModal
from faqih_downloader.ui.components.base_modal import SafeModalDialog


from .media_download_controller import MediaDownloadControllerMixin
from .download_callbacks_mixin import DownloadCallbacksMixin


class DownloadControllerMixin(MediaDownloadControllerMixin, DownloadCallbacksMixin):
    """Handles download triggers, background thread dispatch, progress monitoring, and completion/error states."""

    def queue_download(self, url: str, dest: str, max_conn: int = 8, bytes_limit: float = 0.0):
        """Queues a download task, starting it immediately if no download is currently running."""
        if not hasattr(self, "_download_queue"):
            self._download_queue = []
        reserved = self.history_manager.get_active_or_queued_paths() if (hasattr(self, "history_manager") and self.history_manager) else None
        dest = generate_unique_destination_path(dest, reserved_paths=reserved)
        if not (self.engine and getattr(self.engine, "is_running", False)):
            self._start_download_with_engine(url, dest, max_conn, bytes_limit)
        else:
            self._download_queue.append((url, dest, max_conn, bytes_limit))
            if hasattr(self, "refresh_kanban_col1"): self.refresh_kanban_col1()
            self.log(f"[QUEUE] Task queued: {os.path.basename(dest)} ({len(self._download_queue)} queued)")
            if hasattr(self, "history_manager") and self.history_manager:
                try:
                    self.history_manager.add_or_update_entry(url=url, file_path=dest, size_bytes=0, status="Queued", elapsed_sec=0.0)
                    self._refresh_history_table()
                except Exception: pass

    enqueue_download = queue_download

    def _on_start_download(self, skip_resolver: bool = False):
        if getattr(self, "_is_resolving_start", False):
            return

        if hasattr(self, "_yt_cancel_event") and self._yt_cancel_event:
            try:
                self._yt_cancel_event.set()
            except Exception:
                pass

        url = self.entry_url.get().strip()
        dest = self.entry_dest.get().strip()

        if not url:
            self.show_safe_warning("Missing URL", "Please enter a valid HTTP/HTTPS download URL.")
            return
        if not dest:
            self.show_safe_warning("Missing Save Path", "Please select a valid destination file path.")
            return

        if hasattr(self, "remove_staged_link"):
            self.remove_staged_link(url)

        try: max_conn = int(self.conn_var.get())
        except ValueError: max_conn = 8

        try: kb_limit = float(self.entry_custom_speed.get().strip())
        except ValueError: kb_limit = 0.0

        bytes_limit = kb_limit * 1024.0 if kb_limit > 0 else 0.0

        pending = getattr(self, "_pending_media_context", None)
        if pending and pending.get("url") == url:
            if hasattr(self, "_start_pending_media_download"):
                self._start_pending_media_download()
                return

        if is_media_url(url, check_ytdlp_extractors=True):
            self._start_youtube_download(url, dest, max_conn, bytes_limit, modal=None)
            return

        if skip_resolver:
            if self.engine and getattr(self.engine, "is_running", False):
                self.enqueue_download(url, dest, max_conn, bytes_limit)
            else:
                self._start_download_with_engine(url, dest, max_conn, bytes_limit, modal=None)
            return

        self._is_resolving_start = True
        try:
            self.btn_start.configure(state="disabled")
        except Exception:
            pass

        # Manually typed non-media URL: resolve in background thread before starting
        def _on_resolved(info: Dict[str, Any]):
            self._is_resolving_start = False
            try:
                self.btn_start.configure(state="normal")
            except Exception:
                pass
            if info.get("error") and not info.get("resolved"):
                return
            real_url = info.get("url") or url
            if info.get("resolved"):
                self.log(f"[LINK RESOLVER] Web page detected. Real file found: {real_url}")

            downloads_dir = self._get_base_downloads_dir() if hasattr(self, "_get_base_downloads_dir") else get_base_downloads_dir()
            dest_dir = os.path.dirname(dest) if dest else downloads_dir
            if not os.path.isdir(dest_dir):
                dest_dir = downloads_dir

            real_fn = info.get("filename") or derive_download_filename(real_url)
            if getattr(self, "auto_categorize_folders", True) and self._is_downloads_or_category_subfolder(dest_dir, downloads_dir):
                final_dest = resolve_categorized_path(downloads_dir, real_fn, auto_categorize=True)
            else:
                final_dest = os.path.join(dest_dir, real_fn)

            try:
                self.entry_url.delete(0, tk.END)
                self.entry_url.insert(0, real_url)
                self.entry_dest.delete(0, tk.END)
                self.entry_dest.insert(0, final_dest)
            except Exception:
                pass

            if self.engine and getattr(self.engine, "is_running", False):
                self.enqueue_download(real_url, final_dest, max_conn, bytes_limit)
            else:
                self._start_download_with_engine(real_url, final_dest, max_conn, bytes_limit, modal=None, pre_probed_info=info)

        self._resolve_real_url_async(url, on_resolved=_on_resolved)

    def _start_download_with_engine(
        self,
        url: str,
        dest: str,
        max_conn: int = 8,
        bytes_limit: float = 0.0,
        modal: Optional[Any] = None,
        pre_probed_info: Optional[Dict[str, Any]] = None
    ):
        """Starts download engine, optionally bridging metrics and controls to a standalone modal."""
        if self.engine and self.engine.is_running:
            return
        self._active_download_url = url
        if hasattr(self, "remove_staged_link"):
            self.remove_staged_link(url)

        if hasattr(self, "_yt_cancel_event") and self._yt_cancel_event:
            try: self._yt_cancel_event.set()
            except Exception: pass

        dest = generate_unique_destination_path(dest)
        # Populate GUI entry fields
        try:
            self.entry_url.delete(0, tk.END); self.entry_url.insert(0, url)
            self.entry_dest.delete(0, tk.END); self.entry_dest.insert(0, dest)
            self.conn_var.set(str(max_conn))
            self.entry_custom_speed.delete(0, tk.END)
            if bytes_limit > 0: self.entry_custom_speed.insert(0, str(int(bytes_limit / 1024.0)))
        except Exception:
            pass

        if hasattr(self, "hide_main_media_bar"):
            try: self.hide_main_media_bar()
            except Exception: pass

        # UI state transitions in main window
        try:
            self.btn_start.configure(state="disabled")
            self.btn_pause.configure(state="normal", text=tr("btn_pause", "|| Pause"), bg=self.c_panel_light)
            self.btn_cancel.configure(state="normal")
            if hasattr(self, "btn_refresh_link"):
                self.btn_refresh_link.configure(state="normal", bg=self.c_panel_light, fg=self.c_accent)
            self.txt_log.delete("1.0", tk.END)
            for item in self.tree_chunks.get_children():
                self.tree_chunks.delete(item)
            self._draw_main_progress(0.0)
            self._draw_chunk_segments([])
        except Exception:
            pass

        # Check if URL is YouTube or supported social media
        if is_media_url(url, check_ytdlp_extractors=True):
            self._start_youtube_download(url, dest, max_conn, bytes_limit, modal=modal)
            return

        # Wrapped callbacks for modal + main UI
        def _comb_progress(downloaded: int, total: int, speed: float, eta: str, active_chunks: int):
            if modal and hasattr(modal, "update_progress"):
                try: modal.update_progress(downloaded, total, speed, eta, active_chunks)
                except Exception: pass
            self._engine_progress_cb(downloaded, total, speed, eta, active_chunks)

        def _comb_complete(path: str, total_bytes: int, elapsed: float):
            has_modal = False
            if modal and hasattr(modal, "on_download_complete"):
                try:
                    modal.on_download_complete(path, total_bytes, elapsed)
                    has_modal = True
                except Exception: pass
            self._engine_complete_cb(path, total_bytes, elapsed, suppress_dialog=has_modal)

        def _comb_error(err: str):
            if modal and hasattr(modal, "on_download_error"):
                try: modal.on_download_error(err)
                except Exception: pass
            self._engine_error_cb(err)

        if not pre_probed_info:
            pre_probed_info = getattr(modal, "probed_info", None) if modal else getattr(self, "_last_probed_info", None)

        self.engine = TurboDownloadEngine(
            url=url,
            destination_path=dest,
            max_connections=max_conn,
            rate_limit_bytes_per_sec=bytes_limit,
            on_progress=_comb_progress,
            on_chunk_update=self._engine_chunk_update_cb,
            on_log=self.log,
            on_complete=_comb_complete,
            on_error=_comb_error,
            pre_probed_info=pre_probed_info
        )
        if modal and hasattr(modal, "attach_engine"):
            modal.attach_engine(self.engine)

        self.engine.start()
        if hasattr(self, "history_manager") and self.history_manager and not is_media_url(url, check_ytdlp_extractors=False):
            try:
                self.history_manager.add_or_update_entry(url=url, file_path=dest, size_bytes=getattr(self.engine, "total_size", 0) or 0, status="In Progress", elapsed_sec=0.0)
                self._refresh_history_table()
            except Exception: pass

    def _resolve_history_url(self) -> str:
        act = (getattr(self, "_active_download_url", "") or "").strip()
        if act and "googlevideo.com" not in act.lower():
            return act
        u = (self.engine.url if self.engine and getattr(self.engine, "url", None) else (act or (self.entry_url.get() if hasattr(self, "entry_url") else ""))).strip()
        if "googlevideo.com" in u.lower():
            if act and "googlevideo.com" not in act.lower():
                return act
            eu = (self.entry_url.get() if hasattr(self, "entry_url") else "").strip()
            if eu and "googlevideo.com" not in eu.lower():
                return eu
            if hasattr(self, "engine") and hasattr(self.engine, "stream_info"):
                wp = getattr(self.engine.stream_info, "webpage_url", "")
                if wp and "googlevideo.com" not in wp.lower():
                    return wp
        return u

    def _on_pause_resume(self):
        eng = getattr(self, "engine", None)
        if not eng:
            return
        pending = getattr(self, "_pause_desired_state", None) if getattr(self, "_pause_desired_engine", None) is eng else None
        cur_paused = pending if pending is not None else bool(getattr(eng, "is_paused", False))
        target_paused = not cur_paused
        should_resume = not target_paused
        self._pause_desired_engine = eng
        self._pause_desired_state = target_paused

        snap = eng.get_chunks_snapshot() if hasattr(eng, "get_chunks_snapshot") else list(getattr(eng, "chunks", []) or [])
        dl_bytes, real_total = 0, 0
        if hasattr(eng, "_current_progress_pair") and callable(eng._current_progress_pair):
            try:
                pair = eng._current_progress_pair()
                if isinstance(pair, (tuple, list)) and len(pair) == 2 and isinstance(pair[0], int) and isinstance(pair[1], int):
                    dl_bytes, real_total = pair[0], pair[1]
            except Exception:
                pass
        if dl_bytes <= 0 and real_total <= 0:
            dl_bytes = sum(getattr(c, "downloaded_bytes", 0) for c in snap)
            real_total = int(getattr(eng, "total_size", 0) or sum(getattr(c, "total_bytes", 0) for c in snap) or 0)
        if real_total <= 0:
            real_total = int(getattr(self, "_last_active_total", 0) or 0)
        if dl_bytes <= 0 and int(getattr(self, "_last_active_downloaded", 0) or 0) > 0:
            dl_bytes = int(getattr(self, "_last_active_downloaded", 0) or 0)
        pct_val = (dl_bytes / real_total * 100.0) if real_total > 0 else float(getattr(self, "_last_active_pct", 0.0) or 0.0)
        fn = getattr(eng, "destination_path", None) or getattr(eng, "dest_path", None) or ""

        if should_resume:
            if hasattr(self, "btn_pause"):
                try: self.btn_pause.configure(text=tr("btn_pause", "|| Pause"), bg=self.c_panel_light)
                except Exception: pass
            if hasattr(self, "btn_a1_pause") and self.btn_a1_pause and self.btn_a1_pause.winfo_exists():
                try: self.btn_a1_pause.configure(text="⏸")
                except Exception: pass
            if hasattr(self, "update_kanban_active_stream"):
                try:
                    self.update_kanban_active_stream(fn, pct_val, "0.0 MB/s", snap, 0, downloaded=dl_bytes, total=real_total, eta="Downloading")
                except TypeError:
                    self.update_kanban_active_stream(fn, pct_val, "0.0 MB/s", snap, 0)
        else:
            if hasattr(self, "btn_pause"):
                try: self.btn_pause.configure(text=tr("btn_resume", "▶ Resume"), bg=self.c_warning)
                except Exception: pass
            if hasattr(self, "btn_refresh_link"):
                try: self.btn_refresh_link.configure(state="normal", bg=self.c_panel_light, fg=self.c_accent)
                except Exception: pass
            if hasattr(self, "btn_a1_pause") and self.btn_a1_pause and self.btn_a1_pause.winfo_exists():
                try: self.btn_a1_pause.configure(text="▶")
                except Exception: pass
            if hasattr(self, "card_speed"):
                try: self.card_speed.configure(text="0.0 MB/s")
                except Exception: pass
            if hasattr(self, "update_kanban_active_stream"):
                try:
                    self.update_kanban_active_stream(fn, pct_val, "0.0 MB/s", snap, 0, downloaded=dl_bytes, total=real_total, eta="Paused")
                except TypeError:
                    self.update_kanban_active_stream(fn, pct_val, "0.0 MB/s", snap, 0)

        dl_url = ""
        try: dl_url = self._resolve_history_url()
        except Exception: pass
        dl_dest = (fn or (self.entry_dest.get() if hasattr(self, "entry_dest") else "")).strip()

        def _bg_toggle():
            lk = getattr(self, "_pause_toggle_lock", None)
            if lk is None:
                lk = self._pause_toggle_lock = threading.Lock()
            with lk:
                while True:
                    desired = getattr(self, "_pause_desired_state", None) if getattr(self, "_pause_desired_engine", None) is eng else None
                    if desired is None:
                        desired = target_paused
                    if bool(getattr(eng, "is_paused", False)) == bool(desired):
                        break
                    try:
                        eng.pause() if desired else eng.resume()
                    except Exception:
                        break
                    latest = getattr(self, "_pause_desired_state", None) if getattr(self, "_pause_desired_engine", None) is eng else None
                    if latest is None or latest == desired:
                        break
                if getattr(self, "_pause_desired_engine", None) is eng and getattr(self, "_pause_desired_state", None) == bool(getattr(eng, "is_paused", False)):
                    self._pause_desired_state = None
            try:
                final_paused = bool(getattr(eng, "is_paused", False))
                if dl_url and dl_dest and hasattr(self, "history_manager") and self.history_manager:
                    self.history_manager.add_or_update_entry(
                        url=dl_url,
                        file_path=dl_dest,
                        size_bytes=real_total,
                        status="Paused" if final_paused else "In Progress",
                        elapsed_sec=0.0,
                    )
            except Exception:
                pass

        threading.Thread(target=_bg_toggle, daemon=True).start()

    def _on_cancel_download(self):
        for ev_name in ("_yt_cancel_event", "_fetch_cancel_event"):
            ev = getattr(self, ev_name, None)
            if ev:
                ev.set()
        if hasattr(self, "_close_fetching_toast"):
            try: self._close_fetching_toast()
            except Exception: pass
        if hasattr(self, "clear_last_clipboard_url"):
            try: self.clear_last_clipboard_url()
            except Exception: pass
        for m_name in ("_quality_modal", "_active_modal_dialog", "_refresh_modal"):
            m = getattr(self, m_name, None)
            if m:
                try:
                    if m.winfo_exists():
                        try: m.grab_release()
                        except Exception: pass
                        m.destroy()
                except Exception: pass
                setattr(self, m_name, None)
        self._pause_desired_state = None
        self._pause_desired_engine = None
        if self.engine:
            self.engine.cancel()
            if hasattr(self.engine, "_active_subproc") and self.engine._active_subproc:
                try: self.engine._active_subproc.kill()
                except Exception: pass
            try: self.engine.is_running = False; self.engine._is_running = False
            except Exception: pass
            self.engine = None
        c_light = getattr(self, "c_panel_light", "#334155")
        c_muted = getattr(self, "c_text_muted", "#94a3b8")
        if hasattr(self, "btn_start"): self.btn_start.configure(state="normal")
        if hasattr(self, "btn_pause"): self.btn_pause.configure(state="disabled", text=tr("btn_pause", "|| Pause"))
        if hasattr(self, "btn_cancel"): self.btn_cancel.configure(state="disabled")
        if hasattr(self, "btn_refresh_link"): self.btn_refresh_link.configure(state="disabled", bg=c_light, fg=c_muted)
        if hasattr(self, "card_size"): self.card_size.configure(text=tr("status_ready", "Ready"))
        if hasattr(self, "card_speed"): self.card_speed.configure(text="0 B/s")
        if hasattr(self, "card_eta"): self.card_eta.configure(text="--:--:--")
        if hasattr(self, "card_threads"): self.card_threads.configure(text=f"0 / 0 {tr('lbl_threads_unit', 'Threads')}")
        if hasattr(self, "_draw_main_progress"): self._draw_main_progress(0.0)
        if hasattr(self, "reset_kanban_active_stream"): self.reset_kanban_active_stream()
        if hasattr(self, "log"): self.log("[CANCEL] Operation cancelled by user.")
        if hasattr(self, "_pop_and_start_next_queued_download"): self._pop_and_start_next_queued_download()


__all__ = [
    "DownloadControllerMixin",
    "MediaDownloadControllerMixin",
    "DownloadCallbacksMixin",
]

