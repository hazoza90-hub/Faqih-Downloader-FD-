"""
FileInfoModal: Detailed File & Link Information modal dialog for Faqih Downloader (FD) v2.0.2.
Provides a comprehensive overview of file metadata, disk status, source URL, and resume capability.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = messagebox = None  # type: ignore

from faqih_downloader.locales.i18n import tr
from faqih_downloader.config import get_resource_path
from faqih_downloader.utils.file_ops import open_containing_folder
from faqih_downloader.utils.tk_helpers import _detach_photo_tk


def _format_size_with_bytes(size_bytes: int) -> str:
    """Formats bytes into human readable size along with exact byte count."""
    if size_bytes <= 0:
        return "0 B (0 bytes)"
    s = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    while s >= 1024.0 and unit_idx < len(units) - 1:
        s /= 1024.0
        unit_idx += 1
    h_str = f"{s:.2f} {units[unit_idx]}" if unit_idx > 0 else f"{int(s)} B"
    return f"{h_str} ({size_bytes:,} bytes)"


def open_file_info_modal(parent: Any, item_data: Dict[str, Any], theme: Optional[Dict[str, str]] = None) -> Optional[FileInfoModal]:
    """Convenience helper to open FileInfoModal safely."""
    if tk is None:
        return None
    try:
        return FileInfoModal(parent=parent, item_data=item_data, theme=theme)
    except Exception:
        return None


class FileInfoModal(tk.Toplevel if tk is not None else object):
    """
    Frameless/themed modal window displaying detailed properties of a file or staged link:
    - Real filename and category/extension
    - Size in MB/GB and exact bytes
    - Status (Completed / Staged / Queued)
    - Source URL with one-click copy button
    - Saved File Path with one-click folder reveal
    - Resume compatibility flag
    - Creation timestamp and elapsed download time
    """

    def __init__(self, parent: Any, item_data: Dict[str, Any], theme: Optional[Dict[str, str]] = None):
        if tk is None:
            return
        super().__init__(parent)
        self.parent = parent
        self.item_data = item_data or {}
        self._closing = False
        self._modal_icon_photo = None

        # Color palette
        t = theme or {}
        self.c_bg = t.get("c_bg", "#0b0e14")
        self.c_panel = t.get("c_panel", "#151a24")
        self.c_card = t.get("c_card", "#1c2333")
        self.c_border = t.get("c_border", "#283548")
        self.c_accent = t.get("c_accent", "#19f3ee")
        self.c_accent_blue = t.get("c_accent_blue", "#38bdf8")
        self.c_text_bright = t.get("c_text_bright", "#f8fafc")
        self.c_text_muted = t.get("c_text_muted", "#94a3b8")
        self.c_success = t.get("c_success", "#22c55e")
        self.c_warning = t.get("c_warning", "#f59e0b")
        self.c_danger = t.get("c_danger", "#ef4444")

        self.title(tr("file_info_title", "File & Link Information"))
        self.configure(bg=self.c_bg)
        try:
            self.attributes("-alpha", 0.96)
        except Exception:
            pass

        # Safe window icon
        ico_path = get_resource_path("app_icon.png")
        if os.path.isfile(ico_path):
            try:
                from PIL import ImageTk
                self._modal_icon_photo = ImageTk.PhotoImage(file=ico_path, master=self)
                self.iconphoto(False, self._modal_icon_photo)
            except Exception:
                pass

        dlg_w, dlg_h = 620, 500
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
            px = max(10, px)
            py = max(10, py)
        except Exception:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            px = max(10, (sw - dlg_w) // 2)
            py = max(10, (sh - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{px}+{py}")
        self.minsize(520, 420)

        self._build_ui()

    def grab_set(self):
        """No-op: Eliminates Win32 modal input locks."""
        pass

    def grab_set_global(self):
        """No-op: Eliminates Win32 modal input locks."""
        pass

    def destroy(self):
        self._closing = True
        try:
            super().destroy()
        finally:
            if hasattr(self, "_modal_icon_photo") and self._modal_icon_photo:
                _detach_photo_tk(self._modal_icon_photo)
                self._modal_icon_photo = None

    def _build_ui(self):
        is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
        pad_side = tk.RIGHT if is_ar else tk.LEFT
        opp_side = tk.LEFT if is_ar else tk.RIGHT

        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=self.c_panel, height=44, padx=16)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        lbl_title = tk.Label(
            hdr,
            text=f"ℹ  {tr('file_info_title', 'File & Link Information')}",
            font=("Segoe UI", 11, "bold"),
            bg=self.c_panel,
            fg=self.c_accent
        )
        lbl_title.pack(side=pad_side, pady=10)

        btn_close = tk.Button(
            hdr,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_panel,
            fg=self.c_text_muted,
            activebackground=self.c_danger,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            command=self.destroy
        )
        btn_close.pack(side=opp_side, pady=8)

        # Window drag support
        def _start_drag(e):
            self._drag_x = e.x
            self._drag_y = e.y

        def _do_drag(e):
            x = self.winfo_x() + (e.x - getattr(self, "_drag_x", 0))
            y = self.winfo_y() + (e.y - getattr(self, "_drag_y", 0))
            self.geometry(f"+{x}+{y}")

        hdr.bind("<Button-1>", _start_drag)
        hdr.bind("<B1-Motion>", _do_drag)
        lbl_title.bind("<Button-1>", _start_drag)
        lbl_title.bind("<B1-Motion>", _do_drag)

        # ── Main Content Container ───────────────────────────────────────────
        content = tk.Frame(self, bg=self.c_bg, padx=18, pady=14)
        content.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(content, bg=self.c_panel, highlightbackground=self.c_border, highlightthickness=1, padx=14, pady=12)
        card.pack(fill=tk.BOTH, expand=True)

        # Extract item metadata
        data = self.item_data
        url = data.get("url") or data.get("source_url") or ""
        file_path = data.get("file_path") or data.get("final_dest") or data.get("dest") or ""
        filename = (
            data.get("filename")
            or data.get("file_name")
            or (os.path.basename(file_path) if file_path else "")
            or "Unknown"
        )
        size_bytes = int(data.get("file_size") or data.get("size") or data.get("size_bytes") or 0)
        category = str(data.get("category") or "file").capitalize()
        ext = os.path.splitext(filename)[1].upper().lstrip(".") or data.get("format") or "FILE"
        cat_fmt = f"{category} ({ext})"

        # Determine status
        is_completed = bool(data.get("completed_at") or data.get("timestamp") or data.get("status") == "completed")
        status_text = tr("info_status_completed", "Completed") if is_completed else tr("info_status_staged", "Staged (Ready)")

        # Resume support
        supports_resume = data.get("supports_resume")
        if supports_resume is None:
            resume_str = tr("info_resumable", "✓ Resumable")
        else:
            resume_str = tr("info_resumable", "✓ Resumable") if supports_resume else tr("info_not_resumable", "✕ Non-resumable")

        # Disk status
        disk_status = ""
        if file_path:
            if os.path.isfile(file_path):
                disk_status = tr("info_exists_on_disk", "✓ File exists on disk")
            else:
                disk_status = tr("info_missing_on_disk", "✕ File not found on disk")

        # Timestamp & duration
        ts_val = data.get("timestamp") or data.get("completed_at") or ""
        if isinstance(ts_val, (int, float)) and ts_val > 0:
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_val))
        else:
            ts_str = str(ts_val) if ts_val else "—"

        elapsed_sec = data.get("elapsed") or data.get("duration") or ""
        if isinstance(elapsed_sec, (int, float)) and elapsed_sec > 0:
            m, s = divmod(int(elapsed_sec), 60)
            dur_str = f"{m}m {s}s" if m > 0 else f"{s}s"
        else:
            dur_str = str(elapsed_sec) if elapsed_sec else "—"

        # ── Render Property Rows ─────────────────────────────────────────────
        rows = [
            (tr("info_lbl_filename", "Filename:"), filename, None),
            (tr("info_lbl_size", "Size:"), _format_size_with_bytes(size_bytes), None),
            (tr("info_lbl_category", "Category & Format:"), cat_fmt, None),
            (tr("info_lbl_status", "Status:"), f"{status_text}  •  {resume_str}" + (f"  •  {disk_status}" if disk_status else ""), None),
            (tr("info_lbl_url", "Source URL:"), url, "copy_url"),
            (tr("info_lbl_path", "File Path:"), file_path or "—", "open_folder" if file_path else None),
            (tr("info_lbl_date", "Timestamp:"), ts_str, None),
            (tr("info_lbl_duration", "Elapsed:"), dur_str, None),
        ]

        for i, (label, val, action) in enumerate(rows):
            row_bg = self.c_panel if i % 2 == 0 else self.c_card
            r_frame = tk.Frame(card, bg=row_bg, padx=10, pady=7)
            r_frame.pack(fill=tk.X, pady=1)

            lbl_f = tk.Label(
                r_frame,
                text=label,
                font=("Segoe UI", 9, "bold"),
                bg=row_bg,
                fg=self.c_text_muted,
                width=16,
                anchor="e" if is_ar else "w"
            )
            lbl_f.pack(side=pad_side)

            val_box = tk.Frame(r_frame, bg=row_bg)
            val_box.pack(side=pad_side, fill=tk.X, expand=True, padx=(8, 8))

            val_color = self.c_accent if action == "copy_url" else self.c_text_bright
            val_entry = tk.Entry(
                val_box,
                font=("Segoe UI", 9),
                bg=row_bg,
                fg=val_color,
                relief="flat",
                bd=0,
                readonlybackground=row_bg,
                insertbackground=self.c_accent
            )
            val_entry.insert(0, val)
            val_entry.configure(state="readonly")
            val_entry.pack(side=pad_side, fill=tk.X, expand=True)

            if action == "copy_url":
                def _do_copy():
                    try:
                        self.clipboard_clear()
                        self.clipboard_append(url)
                    except Exception:
                        pass

                btn_cp = tk.Button(
                    r_frame,
                    text=f"⎘ {tr('menu_copy_url', 'Copy URL')}",
                    font=("Segoe UI", 8, "bold"),
                    bg="#1e293b",
                    fg=self.c_accent_blue,
                    activebackground=self.c_accent_blue,
                    activeforeground="#0b0e14",
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    padx=8,
                    pady=2,
                    command=_do_copy
                )
                btn_cp.pack(side=opp_side)

            elif action == "open_folder":
                def _do_open():
                    open_containing_folder(file_path)

                btn_op = tk.Button(
                    r_frame,
                    text=f"▣ {tr('btn_open_folder', 'Open Folder')}",
                    font=("Segoe UI", 8, "bold"),
                    bg="#1e293b",
                    fg=self.c_accent,
                    activebackground=self.c_accent,
                    activeforeground="#0b0e14",
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    padx=8,
                    pady=2,
                    command=_do_open
                )
                btn_op.pack(side=opp_side)

        # ── Footer ───────────────────────────────────────────────────────────
        ftr = tk.Frame(self, bg=self.c_bg, padx=18, pady=10)
        ftr.pack(fill=tk.X)

        btn_dismiss = tk.Button(
            ftr,
            text=tr("btn_close_settings", "Close"),
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg=self.c_text_bright,
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=18,
            pady=6,
            command=self.destroy
        )
        btn_dismiss.pack(side=tk.RIGHT if is_ar else tk.LEFT)
