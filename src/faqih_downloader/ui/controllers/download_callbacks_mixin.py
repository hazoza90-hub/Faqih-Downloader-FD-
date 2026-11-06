"""
download_callbacks_mixin.py: Engine progress, chunk visualization, GUI periodic tick,
queue advance, completion, and error callback handlers for Smart Download (SD).
"""
import os
import sys
from typing import Optional, Callable, Dict, Any, List

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None  # type: ignore
    messagebox = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.ui.components.base_modal import SafeModalDialog


class DownloadCallbacksMixin:
    """Handles engine progress, chunk updating, completion dialogs, error alerts, and queue stepping."""

    def _engine_progress_cb(self, downloaded: int, total: int, speed: float, eta: str, active_chunks: int):
        self._last_prog_args = (downloaded, total, speed, eta, active_chunks)
        if getattr(self, "_prog_update_pending", False):
            return
        self._prog_update_pending = True

        def _update():
            self._prog_update_pending = False
            args = getattr(self, "_last_prog_args", None)
            if not args:
                return
            d, t, sp, et, ac = args
            pct = (d / t * 100.0) if t > 0 else 0.0
            self._draw_main_progress(pct)

            speed_str = f"{sp / (1024*1024):.2f} MB/s" if sp >= 1024*1024 else (f"{sp / 1024:.1f} KB/s" if sp >= 1024 else f"{int(sp)} B/s")
            self.card_speed.configure(text=speed_str)

            def _fmt_size(b):
                if b >= 1024**3:
                    return f"{b / (1024**3):.2f} GB"
                if b >= 1024**2:
                    return f"{b / (1024**2):.1f} MB"
                return f"{b / 1024:.1f} KB" if b >= 1024 else f"{b} B"

            size_str = f"{_fmt_size(d)} / {_fmt_size(t)} ({pct:.1f}%)" if t > 0 else f"{_fmt_size(d)} (Streaming...)"
            if hasattr(self, "card_size"):
                self.card_size.configure(text=size_str)
            if hasattr(self, "card_eta"):
                self.card_eta.configure(text=et)
            snap = self.engine.get_chunks_snapshot() if hasattr(self.engine, "get_chunks_snapshot") else (self.engine.chunks if self.engine else [])
            total_chunks = max(ac, len(snap))
            if hasattr(self, "card_threads"):
                self.card_threads.configure(text=f"{ac} / {total_chunks} {tr('lbl_threads_unit', 'Threads')}")
            if hasattr(self, "update_kanban_active_stream"):
                fn = getattr(self.engine, "dest_path", None) or getattr(self.engine, "destination_path", None) or (self.entry_url.get() if hasattr(self, "entry_url") else "")
                self.update_kanban_active_stream(fn, pct, speed_str, snap, ac)

        try:
            if self.root.winfo_exists():
                self.root.after(0, _update)
            else:
                self._prog_update_pending = False
        except Exception:
            self._prog_update_pending = False

    def _engine_chunk_update_cb(self):
        if getattr(self, "_chunk_ui_update_pending", False) or getattr(self, "_chunk_update_pending", False):
            return
        self._chunk_ui_update_pending = self._chunk_update_pending = True

        def _do_chunk():
            self._chunk_ui_update_pending = self._chunk_update_pending = False
            self._refresh_chunk_displays()

        try:
            if self.root.winfo_exists():
                self.root.after(0, _do_chunk)
            else:
                self._chunk_ui_update_pending = self._chunk_update_pending = False
        except Exception:
            self._chunk_ui_update_pending = self._chunk_update_pending = False

    def _gui_refresh_tick(self):
        """Periodic tick ensuring smooth chunk visualization animation and processing queued thread tasks."""
        if getattr(self, "_closing", False):
            return
        try:
            if not hasattr(self, "root") or not self.root or not self.root.winfo_exists():
                return
        except Exception:
            return

        self._drain_dispatch_queue()

        if self.engine and self.engine.is_running and not self.engine.is_paused:
            try:
                self._refresh_chunk_displays()
            except Exception:
                pass
        try:
            if not getattr(self, "_closing", False) and self.root.winfo_exists():
                self._refresh_job = self.root.after(250, self._gui_refresh_tick)
        except Exception:
            pass

    def _pop_and_start_next_queued_download(self):
        if hasattr(self, "_download_queue") and self._download_queue:
            next_task = self._download_queue.pop(0)
            if hasattr(self, "refresh_kanban_col1"):
                self.refresh_kanban_col1()
            if callable(next_task):
                if hasattr(self, "log"):
                    self.log(f"[QUEUE] Launching next queued stream ({len(self._download_queue)} remaining)")
                next_task()
            elif isinstance(next_task, (list, tuple)) and len(next_task) >= 4:
                q_url, q_dest, q_conn, q_limit = next_task[:4]
                if hasattr(self, "log"):
                    self.log(f"[QUEUE] Launching next queued download: {os.path.basename(q_dest)} ({len(self._download_queue)} remaining)")
                self._start_download_with_engine(q_url, q_dest, q_conn, q_limit)

    def _engine_complete_cb(self, path: str, total_bytes: int, elapsed: float, suppress_dialog: bool = False):
        def _done():
            self._draw_main_progress(100.0)
            self._refresh_chunk_displays()
            self.btn_start.configure(state="normal")
            self.btn_pause.configure(state="disabled", text=tr("btn_pause", "|| Pause"))
            self.btn_cancel.configure(state="disabled")
            if hasattr(self, "btn_refresh_link"):
                self.btn_refresh_link.configure(state="disabled", bg=self.c_panel_light, fg=self.c_text_muted)
            if hasattr(self, "log"):
                self.log(f"[COMPLETE] Download complete: {os.path.basename(path)} ({total_bytes:,} bytes in {elapsed:.1f}s)")
            try:
                dl_url = self._resolve_history_url()
                if hasattr(self, "history_manager") and self.history_manager:
                    self.history_manager.add_or_update_entry(url=dl_url, file_path=path, size_bytes=total_bytes, status="Completed", elapsed_sec=elapsed)
                    self._refresh_history_table()
            except Exception:
                pass
            if hasattr(self, "on_kanban_download_completed"):
                self.on_kanban_download_completed(path, total_bytes)
            if self.engine:
                try:
                    self.engine.is_running = False
                    self.engine._is_running = False
                except Exception:
                    pass
                self.engine = None
            if hasattr(self, "_pop_and_start_next_queued_download"):
                self._pop_and_start_next_queued_download()

            if suppress_dialog:
                return
            msg = (f"{tr('dialog_complete_msg_verified', 'File verified & assembled without corruption!')}\n\n"
                   f"{tr('dialog_complete_msg_saved', 'Saved to:')} {path}\n"
                   f"{tr('dialog_complete_msg_size', 'Size:')} {total_bytes:,} bytes\n"
                   f"{tr('dialog_complete_msg_time', 'Total Time:')} {elapsed:.1f} seconds")
            complete_title = tr("toast_completed_title", "Download Completed Successfully! ⚡")
            if hasattr(self, "show_safe_info"):
                self.show_safe_info(complete_title, msg)
            elif getattr(messagebox.showinfo, "_mock_name", None) or hasattr(messagebox.showinfo, "mock"):
                messagebox.showinfo(complete_title, msg)
            elif hasattr(self, "root") and self.root and self.root.winfo_exists():
                try:
                    SafeModalDialog(self.root, title=complete_title, message=msg, dialog_type="info", theme=getattr(self, "_theme_dict", lambda: None)())
                except Exception:
                    pass
        try:
            if self.root.winfo_exists():
                self.root.after(0, _done)
        except Exception:
            pass

    def _engine_error_cb(self, error_msg: str):
        def _err():
            if hasattr(self, "_quality_modal") and self._quality_modal:
                try:
                    if self._quality_modal.winfo_exists():
                        try:
                            self._quality_modal.grab_release()
                        except Exception:
                            pass
                        self._quality_modal.destroy()
                except Exception:
                    pass
                self._quality_modal = None
            if hasattr(self, "btn_start"):
                try:
                    self.btn_start.configure(state="normal")
                except Exception:
                    pass
            if hasattr(self, "btn_pause"):
                try:
                    self.btn_pause.configure(state="disabled", text=tr("btn_pause", "|| Pause"))
                except Exception:
                    pass
            if hasattr(self, "btn_cancel"):
                try:
                    self.btn_cancel.configure(state="disabled")
                except Exception:
                    pass
            is_expired = any(k in str(error_msg) for k in ("401", "403", "410", "Forbidden", "Expired", "Unauthorized"))
            if hasattr(self, "btn_refresh_link"):
                try:
                    b_bg = getattr(self, "c_warning", "#f59e0b") if is_expired else getattr(self, "c_panel_light", "#334155")
                    b_fg = "#0f172a" if is_expired else getattr(self, "c_accent", "#38bdf8")
                    self.btn_refresh_link.configure(state="normal", bg=b_bg, fg=b_fg)
                except Exception:
                    pass
            if hasattr(self, "card_size"):
                try:
                    self.card_size.configure(text=tr("status_ready", "Ready"))
                except Exception:
                    pass
            if hasattr(self, "log"):
                try:
                    self.log(f"[ERROR] Download Error: {error_msg}")
                except Exception:
                    pass

            try:
                dl_url = self._resolve_history_url()
                dl_dest = (self.engine.dest_path if self.engine and getattr(self.engine, "dest_path", None) else self.entry_dest.get()).strip()
                if dl_url and dl_dest and hasattr(self, "history_manager") and self.history_manager:
                    self.history_manager.add_or_update_entry(url=dl_url, file_path=dl_dest, size_bytes=0, status="Failed", elapsed_sec=0.0)
                    self._refresh_history_table()
            except Exception:
                pass

            if self.engine:
                try:
                    self.engine.is_running = False
                    self.engine._is_running = False
                except Exception:
                    pass
                self.engine = None
            if hasattr(self, "_pop_and_start_next_queued_download"):
                self._pop_and_start_next_queued_download()

            if is_expired:
                msg = (
                    f"{tr('dialog_expired_msg1', 'Download stopped: Server rejected session (HTTP 401/403/410).')}\n\n"
                    f"{tr('dialog_expired_details', 'Details:')} {error_msg}\n\n"
                    f"{tr('dialog_expired_msg2', '★ All partially downloaded chunk files are safely preserved on disk.')}\n"
                    f"{tr('dialog_expired_msg3', 'Would you like to refresh the download link now to resume?')}"
                )
                if hasattr(self, "ask_safe_yesno"):
                    self.ask_safe_yesno(tr("dialog_expired_title", "Download Link Expired ⚠️"), msg, on_yes=self._open_refresh_link_dialog)
                    return

            msg = f"{tr('dialog_error_prefix', 'Encountered error during download:')}\n\n{error_msg}"
            err_title = tr("dialog_error_title", "Download Error")
            if hasattr(self, "show_safe_error"):
                self.show_safe_error(err_title, msg)
            elif getattr(messagebox.showerror, "_mock_name", None) or hasattr(messagebox.showerror, "mock"):
                messagebox.showerror(err_title, msg)
            else:
                try:
                    if hasattr(self, "root") and self.root and self.root.winfo_exists():
                        SafeModalDialog(self.root, title=err_title, message=msg, dialog_type="error", theme=getattr(self, "_theme_dict", lambda: None)())
                except Exception:
                    pass
        try:
            if hasattr(self, "root") and self.root and self.root.winfo_exists():
                self.root.after(0, _err)
            else:
                _err()
        except Exception:
            pass


__all__ = ["DownloadCallbacksMixin"]
