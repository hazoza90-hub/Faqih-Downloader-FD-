"""
ConfirmModalProgressMixin: Live progress tracking, canvas drawing, metrics updating, and completion handling.
"""
from __future__ import annotations

import os
import threading
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ...locales.i18n import tr
from ...utils.file_ops import get_file_category_and_icon
from ...core.history import DownloadHistoryManager


class ConfirmModalProgressMixin:
    """Mixin handling live download progress display, canvas bar drawing, and completion/error transitions."""

    def show_progress_view(self):
        """Transitions modal interface into standalone compact download progress view."""
        self.is_in_progress_view = True
        self.title(f"Downloading: {self.file_name} — Smart Download")
        self.frame_confirmation.pack_forget()
        self.frame_progress.pack(fill=tk.BOTH, expand=True)

        self.lbl_prog_filename.configure(text=self.file_name)
        cat, icon = get_file_category_and_icon(self.file_name)
        self.lbl_prog_cat.configure(text=f"{icon}  {cat}")
        self.lbl_prog_threads.configure(text=f"Threads: {self.get_max_connections()} Max")

        # Compact size
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        prog_w = min(int(580 * self.dpi_scale), max(500, int(sw * 0.90)))
        prog_h = min(int(320 * self.dpi_scale), max(270, int(sh * 0.70)))
        try:
            cur_x = self.winfo_x()
            cur_y = self.winfo_y()
            if 0 <= cur_x <= 1 and 0 <= cur_y <= 1:
                cur_x = max(0, (sw - prog_w) // 2)
                cur_y = max(0, (sh - prog_h) // 2)
        except Exception:
            cur_x = max(0, (sw - prog_w) // 2)
            cur_y = max(0, (sh - prog_h) // 2)
        pos_x = f"+{int(cur_x)}" if int(cur_x) >= 0 else f"{int(cur_x)}"
        pos_y = f"+{int(cur_y)}" if int(cur_y) >= 0 else f"{int(cur_y)}"
        self.geometry(f"{prog_w}x{prog_h}{pos_x}{pos_y}")
        self._draw_modal_progress(0.0)

    def _draw_modal_progress(self, pct: float):
        try:
            self._last_pct = float(pct)
            if not hasattr(self, "canvas_prog") or not self.canvas_prog.winfo_exists():
                return
            self.canvas_prog.delete("all")
            w = self.canvas_prog.winfo_width()
            if w <= 1:
                w = int(500 * self.dpi_scale)
            h = self.canvas_prog.winfo_height() or int(24 * self.dpi_scale)

            # Background track
            self.canvas_prog.create_rectangle(0, 0, w, h, fill=self.c_input_bg, outline=self.c_border)

            # Progress fill
            fill_w = max(0.0, min(float(w), (pct / 100.0) * float(w)))
            if fill_w > 0:
                fill_color = self.c_success if pct >= 100.0 else self.c_accent_dark
                line_color = "#34d399" if pct >= 100.0 else self.c_accent
                self.canvas_prog.create_rectangle(0, 0, fill_w, h, fill=fill_color, outline="")
                self.canvas_prog.create_line(0, 1, fill_w, 1, fill=line_color)

            # Percentage text overlay
            text_color = "white" if fill_w > (w * 0.45) else self.c_text_bright
            self.canvas_prog.create_text(w // 2, h // 2, text=f"{pct:.1f}%", font=("Segoe UI", 9, "bold"), fill=text_color)
        except Exception:
            pass

    def update_progress(self, downloaded: int, total: int, speed: float, eta: str, active_chunks: int = 1):
        """Thread-safe update of live download progress bar, speed, size, and ETA."""
        if threading.current_thread() != threading.main_thread():
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self.update_progress(downloaded, total, speed, eta, active_chunks))
            except Exception:
                pass
            return

        pct = (downloaded / total * 100.0) if total > 0 else 0.0
        self._draw_modal_progress(pct)

        # Format speed
        if speed >= 1024 * 1024:
            speed_str = f"{speed / (1024*1024):.2f} MB/s"
        elif speed >= 1024:
            speed_str = f"{speed / 1024:.1f} KB/s"
        else:
            speed_str = f"{int(speed)} B/s"

        # Format sizes
        def _fmt(b):
            if b >= 1024 * 1024 * 1024:
                return f"{b / (1024**3):.2f} GB"
            if b >= 1024 * 1024:
                return f"{b / (1024**2):.1f} MB"
            if b >= 1024:
                return f"{b / 1024:.1f} KB"
            return f"{b} B"

        if total > 0:
            size_str = f"Transferred: {_fmt(downloaded)} / {_fmt(total)} ({pct:.1f}%)"
        else:
            size_str = f"Transferred: {_fmt(downloaded)} (Streaming...)"

        try:
            self.lbl_prog_size.configure(text=size_str)
            self.lbl_prog_speed.configure(text=f"Speed: {speed_str}")
            self.lbl_prog_eta.configure(text=f"Time Left: {eta}")
            self.lbl_prog_threads.configure(text=f"Threads: {active_chunks} Active")
            if not (self.engine and getattr(self.engine, "is_paused", False)):
                self.lbl_status.configure(text=tr("modal_status_downloading", "Status: Downloading..."), fg=self.c_accent)
        except Exception:
            pass

    def on_download_complete(self, dest_path: str, total_bytes: int, elapsed: float):
        """Thread-safe transition to completion view with Open File, Open Folder, and Close buttons."""
        if threading.current_thread() != threading.main_thread():
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self.on_download_complete(dest_path, total_bytes, elapsed))
            except Exception:
                pass
            return

        self.dest_path = dest_path
        self.is_completed = True
        self._draw_modal_progress(100.0)
        try:
            self.lbl_status.configure(text=tr("modal_status_complete", "✅ Download Complete!"), fg=self.c_success)

            def _fmt(b):
                if b >= 1024 * 1024 * 1024:
                    return f"{b / (1024**3):.2f} GB"
                if b >= 1024 * 1024:
                    return f"{b / (1024**2):.1f} MB"
                if b >= 1024:
                    return f"{b / 1024:.1f} KB"
                return f"{b} B"

            avg_speed = (total_bytes / elapsed) if elapsed > 0 else 0
            if avg_speed >= 1024 * 1024:
                avg_str = f"{avg_speed / (1024*1024):.2f} MB/s"
            else:
                avg_str = f"{avg_speed / 1024:.1f} KB/s"

            self.lbl_prog_size.configure(text=f"Total: {_fmt(total_bytes)} in {elapsed:.1f}s")
            self.lbl_prog_speed.configure(text=f"Avg Speed: {avg_str}")
            self.lbl_prog_eta.configure(text="Time Left: 00:00:00")

            # Swap buttons to completion action buttons
            self.btn_pause_resume.pack_forget()
            self.btn_cancel_prog.pack_forget()
            self.btn_open_app_prog.pack_forget()

            self.btn_close_prog.pack(side=tk.RIGHT, padx=(6, 0))
            self.btn_open_folder.pack(side=tk.RIGHT, padx=(6, 0))
            self.btn_open_file.pack(side=tk.RIGHT)
        except Exception:
            pass

        try:
            hm = getattr(self, "history_manager", None)
            if not hm and self.parent_app:
                hm = getattr(self.parent_app, "history_manager", None)
            if not hm:
                hm = DownloadHistoryManager()
            hm.add_or_update_entry(
                url=self.url,
                file_path=dest_path,
                size_bytes=total_bytes,
                status="Completed",
                elapsed_sec=elapsed
            )
            if self.parent_app and hasattr(self.parent_app, "_refresh_history_table"):
                self.parent_app._refresh_history_table()
        except Exception:
            pass

    def on_download_error(self, err_msg: str):
        """Thread-safe display of download failure message."""
        if threading.current_thread() != threading.main_thread():
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self.on_download_error(err_msg))
            except Exception:
                pass
            return
        try:
            self.lbl_status.configure(text=f"❌ Error: {err_msg}", fg=self.c_danger)
            self.btn_pause_resume.configure(state="disabled")
        except Exception:
            pass

        try:
            hm = getattr(self, "history_manager", None)
            if not hm and self.parent_app:
                hm = getattr(self.parent_app, "history_manager", None)
            if not hm:
                hm = DownloadHistoryManager()
            hm.add_or_update_entry(
                url=self.url,
                file_path=self.dest_path or (self.entry_dest.get().strip() if hasattr(self, "entry_dest") else ""),
                size_bytes=0,
                status="Failed",
                elapsed_sec=0.0
            )
            if self.parent_app and hasattr(self.parent_app, "_refresh_history_table"):
                self.parent_app._refresh_history_table()
        except Exception:
            pass
