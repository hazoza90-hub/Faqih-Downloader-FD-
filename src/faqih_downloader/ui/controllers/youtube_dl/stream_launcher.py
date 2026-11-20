"""
YouTubeStreamLauncherMixin: Stream coordinator instantiation, queue coordination, and event hook attachment.
"""
import os
import sys
from typing import Any, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ....i18n import tr
from ....utils.file_ops import generate_unique_destination_path
from ....core.stream_coordinator import StreamDownloadCoordinator


def _get_stream_coordinator_cls():
    mod = sys.modules.get("faqih_downloader.ui.controllers.youtube_download_controller")
    if mod and hasattr(mod, "StreamDownloadCoordinator"):
        return getattr(mod, "StreamDownloadCoordinator")
    return StreamDownloadCoordinator


class YouTubeStreamLauncherMixin:
    """Initializes and runs StreamDownloadCoordinator with GUI progress and status hooks."""

    def _launch_stream_coordinator(
        self,
        stream_info: Any,
        final_dest: str,
        max_conn: int = 8,
        bytes_limit: float = 0.0,
        yt_modal: Optional[Any] = None,
        from_queue: bool = False
    ):
        """Initializes and runs StreamDownloadCoordinator with GUI progress and status hooks."""
        if from_queue:
            in_prog = [
                e.get("file_path", "")
                for e in getattr(self.history_manager, "_entries", [])
                if str(e.get("status", "")).strip().lower() in ("in progress", "قيد التحميل") and e.get("file_path")
            ] if hasattr(self, "history_manager") and self.history_manager else None
            final_dest = generate_unique_destination_path(final_dest, reserved_paths=in_prog)
        else:
            reserved = self.history_manager.get_active_or_queued_paths() if (hasattr(self, "history_manager") and self.history_manager) else None
            final_dest = generate_unique_destination_path(final_dest, reserved_paths=reserved)

        if self.engine and getattr(self.engine, "is_running", False):
            if not hasattr(self, "_download_queue"):
                self._download_queue = []

            def _queued_task():
                self._launch_stream_coordinator(stream_info, final_dest, max_conn, bytes_limit, yt_modal=yt_modal, from_queue=True)

            _queued_task.url = getattr(stream_info, "webpage_url", "") or os.path.basename(final_dest)
            if not hasattr(self, "_queued_metadata"):
                self._queued_metadata = {}
            badge_name = getattr(stream_info, "resolution", "") or getattr(stream_info, "format_note", "") or "MEDIA"
            self._queued_metadata[_queued_task.url] = {
                "title": getattr(stream_info, "title", "") or os.path.basename(final_dest),
                "badge": badge_name,
                "badge_bg": "#0284c7"
            }
            self._download_queue.append(_queued_task)
            if hasattr(self, "refresh_kanban_col1"): self.refresh_kanban_col1()
            self.log(f"[QUEUE] Media stream queued: {os.path.basename(final_dest)} ({len(self._download_queue)} queued)")
            if hasattr(self, "history_manager") and self.history_manager:
                q_url = getattr(stream_info, "webpage_url", "") or (self.entry_url.get().strip() if hasattr(self, "entry_url") else "")
                est_sz = (getattr(stream_info, "video_size", 0) or 0) + (getattr(stream_info, "audio_size", 0) or 0)
                from ....services.media_clipper_engine import estimate_clip_total_bytes
                est_sz = estimate_clip_total_bytes(stream_info, est_sz)
                self.history_manager.add_or_update_entry(
                    url=q_url, file_path=final_dest, size_bytes=est_sz, status="Queued", elapsed_sec=0.0
                )
                if hasattr(self, "_refresh_history_table"):
                    self._refresh_history_table(force=True)
            return

        try:
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, final_dest)
            self.btn_pause.configure(state="normal", text=tr("btn_pause", "|| Pause"), bg=self.c_panel_light)
            self.btn_cancel.configure(state="normal")
            self.btn_start.configure(state="disabled")
        except Exception:
            pass

        def _comb_progress(downloaded, total, speed, eta, active):
            if yt_modal:
                try:
                    if yt_modal.winfo_exists():
                        yt_modal.update_progress(downloaded, total, speed, eta, active)
                except Exception:
                    pass
            self._engine_progress_cb(downloaded, total, speed, eta, active)

        def _comb_complete(path, total_bytes, elapsed):
            has_yt_modal = False
            if yt_modal:
                try:
                    if yt_modal.winfo_exists():
                        yt_modal.on_download_complete(path, total_bytes, elapsed)
                        has_yt_modal = True
                except Exception:
                    pass
            self._engine_complete_cb(path, total_bytes, elapsed, suppress_dialog=has_yt_modal)

        def _comb_error(err):
            if yt_modal:
                try:
                    if yt_modal.winfo_exists():
                        yt_modal.on_download_error(err)
                except Exception:
                    pass
            self._engine_error_cb(err)

        coord_cls = _get_stream_coordinator_cls()
        coordinator = coord_cls(
            stream_info=stream_info,
            destination_path=final_dest,
            max_connections=max_conn,
            rate_limit_bytes_per_sec=bytes_limit,
            on_progress=_comb_progress,
            on_chunk_update=self._engine_chunk_update_cb,
            on_log=self.log,
            on_complete=_comb_complete,
            on_error=_comb_error
        )
        self._active_download_url = getattr(stream_info, "webpage_url", "") or getattr(stream_info, "video_url", "") or ""
        self.engine = coordinator
        if yt_modal and hasattr(yt_modal, "attach_engine"):
            yt_modal.attach_engine(coordinator)
        coordinator.start()
        if hasattr(self, "history_manager") and self.history_manager:
            try:
                q_url = getattr(stream_info, "webpage_url", "") or (self.entry_url.get().strip() if hasattr(self, "entry_url") else "")
                est_sz = (getattr(stream_info, "video_size", 0) or 0) + (getattr(stream_info, "audio_size", 0) or 0)
                from ....services.media_clipper_engine import estimate_clip_total_bytes
                est_sz = estimate_clip_total_bytes(stream_info, est_sz)
                self.history_manager.add_or_update_entry(url=q_url, file_path=final_dest, size_bytes=est_sz, status="In Progress", elapsed_sec=0.0)
                self._refresh_history_table()
            except Exception: pass


__all__ = ["YouTubeStreamLauncherMixin"]
