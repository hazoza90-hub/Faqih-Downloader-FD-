"""
DownloadConfirmationModal: Download metadata inspection, category routing, and pre-start confirmation modal.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Optional, Callable, Dict, Any

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception:
    tk = ttk = filedialog = messagebox = None  # type: ignore

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from ...config import get_resource_path, get_setting, set_setting
from ...locales.i18n import tr
from ..components.base_modal import SafeModalDialog
from ..components.tooltip import ToolTip
from ...utils.url_utils import derive_download_filename, is_potential_html_url, parse_speed_limit
from ...utils.file_ops import (
    get_file_category_and_icon,
    resolve_categorized_path,
    open_containing_folder,
    open_downloaded_file,
)
from ...core.html_resolver import resolve_real_download_url
from ...core.engine import TurboDownloadEngine
from ...core.history import DownloadHistoryManager
from ...utils.tk_helpers import _detach_photo_tk, animate_window_open

from .confirm_modal_logic import ConfirmModalLogicMixin
from .confirm_modal_progress import ConfirmModalProgressMixin
from .confirm_modal_widgets import ConfirmModalWidgetsMixin

_BaseToplevel = tk.Toplevel if tk is not None else object


class DownloadConfirmationModal(ConfirmModalLogicMixin, ConfirmModalWidgetsMixin, _BaseToplevel):
    """
    Modern dark-themed TDM-style Download Confirmation & Standalone Progress Dialog:
    - Displays intercepted URL, extracted filename, file category badge & icon, and target save path.
    - Connection count selector and Speed limiter controls.
    - Three action buttons: Start Download, Open in Main App, Cancel.
    - Standalone compact download progress view with Pause/Resume/Cancel/Open.
    - Grab-free: strictly avoids grab_set() to eliminate Win32 message pump traps.
    """
    def __init__(
        self, parent: Optional[tk.Tk], url: str, default_dest_path: str,
        theme: Optional[Dict[str, str]] = None, on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable[[], None]] = None, on_start_in_window: Optional[Callable] = None,
        on_open_in_main: Optional[Callable] = None, parent_app: Optional[Any] = None,
        default_connections: int = 8, default_speed_limit: float = 0.0,
        show_progress_immediately: bool = False, history_manager: Optional[Any] = None
    ):
        super().__init__(parent)
        self.url = str(url or "").strip()
        self.dest_path = str(default_dest_path or "").strip()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.on_start_in_window = on_start_in_window
        self.on_open_in_main = on_open_in_main
        self.parent_app = parent_app
        self.history_manager = history_manager or (getattr(parent_app, "history_manager", None) if parent_app else None)
        self.default_connections = default_connections
        self.default_speed_limit = default_speed_limit
        self._confirmed = False
        self.is_in_progress_view = False
        self.is_completed = False
        self.engine: Optional[Any] = None

        self.file_name = os.path.basename(self.dest_path) if self.dest_path else derive_download_filename(self.url)
        self.category, self.icon = get_file_category_and_icon(self.file_name or self.url)

        th = theme or {}
        _c_defaults = {
            "c_bg": "#0f172a", "c_panel": "#1e293b", "c_panel_light": "#334155",
            "c_border": "#475569", "c_text_bright": "#f8fafc", "c_text_muted": "#94a3b8",
            "c_accent": "#38bdf8", "c_accent_dark": "#0284c7", "c_danger": "#ef4444",
            "c_success": "#10b981", "c_warning": "#f59e0b", "c_input_bg": "#0b1220"
        }
        for k, v in _c_defaults.items():
            setattr(self, k, th.get(k, v))

        self.title(tr("modal_confirm_title", "Download File Info — Smart Download"))
        self.configure(bg=self.c_bg)
        self._last_pct = 0.0

        # Determine parent DPI scale
        try:
            dpi = float(parent.winfo_fpixels('1i')) if parent and parent.winfo_exists() else 96.0
        except Exception:
            dpi = 96.0
        self.dpi_scale = max(1.0, dpi / 96.0)

        # Center on parent window with DPI scaling (or center on screen if parent is hidden/minimized)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        dlg_w = min(int(630 * self.dpi_scale), max(500, int(sw * 0.90)))
        dlg_h = min(int(410 * self.dpi_scale), max(340, int(sh * 0.80)))

        is_parent_vis = False
        try:
            is_parent_vis = bool(parent and parent.winfo_exists() and parent.winfo_viewable() and parent.state() == "normal")
        except Exception:
            pass

        if is_parent_vis:
            try:
                self.transient(parent)
                px, py = parent.winfo_x(), parent.winfo_y()
                pw, ph = parent.winfo_width() or dlg_w, parent.winfo_height() or dlg_h
                x, y = px + (pw - dlg_w) // 2, py + (ph - dlg_h) // 2
            except Exception:
                x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)
        else:
            try:
                self.transient("")
                self.deiconify()
            except Exception:
                pass
            x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)

        pos_x = f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"
        pos_y = f"+{int(y)}" if int(y) >= 0 else f"{int(y)}"
        self.geometry(f"{dlg_w}x{dlg_h}{pos_x}{pos_y}")
        animate_window_open(self)
        self.minsize(min(480, dlg_w), min(270, dlg_h))

        # Apply application icon to modal window
        ico_path = get_resource_path("app_icon.ico")
        png_path = get_resource_path("app_icon.png")
        if os.path.isfile(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        if os.path.isfile(png_path):
            try:
                from PIL import ImageTk
                self._modal_icon_photo = ImageTk.PhotoImage(file=png_path)
                self.iconphoto(False, self._modal_icon_photo)
            except Exception:
                pass

        self._build_ui()

        # Elevate and focus to ensure modal stays above parent window
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self._topmost_job = self.after(250, lambda: self.attributes("-topmost", False) if self.winfo_exists() else None)
            self._idle_job = self.after_idle(lambda: (self.lift(), self.focus_force()) if self.winfo_exists() else None)
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("<Return>", lambda e: self._on_start())

        if show_progress_immediately:
            self.show_progress_view()


DownloadConfirmationDialog = DownloadConfirmationModal
DownloadConfirmModal = DownloadConfirmationModal
__all__ = [
    "DownloadConfirmationModal",
    "DownloadConfirmationDialog",
    "DownloadConfirmModal",
    "ConfirmModalLogicMixin",
    "ConfirmModalProgressMixin",
    "ConfirmModalWidgetsMixin",
]
