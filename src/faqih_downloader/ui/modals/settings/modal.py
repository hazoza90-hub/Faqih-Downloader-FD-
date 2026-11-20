"""
SettingsModal: Frameless dark application settings dialog with per-platform sniffer filtering,
speed limiter controls, engine activity log, and downloads configuration.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, List, Tuple

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import (
    get_setting,
    get_resource_path,
    DEFAULT_SNIFFER_PLATFORMS,
)
from faqih_downloader.ui.modals.settings_modal_tabs import SettingsModalTabsMixin
from faqih_downloader.utils.tk_helpers import _detach_photo_tk
from .layout_builder import SettingsModalLayoutMixin
from .sniffer_handlers import SettingsSnifferHandlersMixin
from .storage_handlers import SettingsStorageHandlersMixin
from .network_system_handlers import SettingsNetworkSystemMixin

_BaseToplevel = tk.Toplevel if tk is not None else object


class SettingsModal(
    SettingsModalTabsMixin,
    SettingsSnifferHandlersMixin,
    SettingsStorageHandlersMixin,
    SettingsNetworkSystemMixin,
    SettingsModalLayoutMixin,
    _BaseToplevel
):
    """Frameless dark theme modal dialog for user preferences and platform sniffer toggles."""

    PLATFORM_DEFS: List[Tuple[str, str]] = [
        ("youtube", "plat_youtube"),
        ("tiktok", "plat_tiktok"),
        ("instagram", "plat_instagram"),
        ("facebook", "plat_facebook"),
        ("twitter", "plat_twitter"),
        ("direct_files", "plat_direct_files"),
        ("reddit", "plat_reddit"),
        ("twitch", "plat_twitch"),
        ("vimeo", "plat_vimeo"),
        ("dailymotion", "plat_dailymotion"),
        ("pinterest", "plat_pinterest"),
        ("threads", "plat_threads"),
    ]

    RES_OPTIONS: List[Tuple[int, str]] = [
        (0, "0 (Ask / Best)"),
        (2160, "2160p (4K UHD)"),
        (1440, "1440p (2K QHD)"),
        (1080, "1080p (Full HD)"),
        (720, "720p (HD)"),
        (480, "480p (SD)"),
        (360, "360p (Low)"),
        (-1, "Audio Only (MP3)"),
    ]

    def __init__(self, parent: Any = None, parent_app: Any = None, theme: Optional[Dict[str, str]] = None):
        if tk is not None:
            super().__init__(parent)
        self.parent_app = parent_app
        self.theme = theme or (
            parent_app._theme_dict()
            if parent_app and hasattr(parent_app, "_theme_dict")
            else {
                "c_bg": "#0b0e14",
                "c_panel": "#151a24",
                "c_panel_light": "#1c2333",
                "c_border": "#283548",
                "c_accent": "#19f3ee",
                "c_accent_dark": "#0ea5e9",
                "c_text_bright": "#f8fafc",
                "c_text_muted": "#94a3b8",
                "c_success": "#22c55e",
                "c_danger": "#ef4444",
                "c_input_bg": "#0f1520",
            }
        )
        self.c_bg = self.theme.get("c_bg", "#0b0e14")
        self.c_panel = self.theme.get("c_panel", "#151a24")
        self.c_panel_light = self.theme.get("c_panel_light", "#1c2333")
        self.c_border = self.theme.get("c_border", "#283548")
        self.c_accent = self.theme.get("c_accent", "#19f3ee")
        self.c_accent_dark = self.theme.get("c_accent_dark", "#0ea5e9")
        self.c_text_bright = self.theme.get("c_text_bright", "#f8fafc")
        self.c_text_muted = self.theme.get("c_text_muted", "#94a3b8")
        self.c_success = self.theme.get("c_success", "#22c55e")
        self.c_danger = self.theme.get("c_danger", "#ef4444")
        self.c_input_bg = self.theme.get("c_input_bg", "#0f1520")

        if tk is not None:
            self.title(tr("settings_modal_title", "⚙ Application Settings — Faqih Downloader"))
            try:
                self.overrideredirect(True)
            except Exception:
                pass

            dpi_scale = getattr(parent_app, "dpi_scale", 1.0) if parent_app else 1.0
            sw = self.winfo_screenwidth() if hasattr(self, "winfo_screenwidth") else 1920
            sh = self.winfo_screenheight() if hasattr(self, "winfo_screenheight") else 1080
            dlg_w = min(int(720 * dpi_scale), max(640, int(sw * 0.92)))
            dlg_h = min(int(640 * dpi_scale), max(560, int(sh * 0.90)))

            try:
                if parent and parent.winfo_exists() and parent.winfo_viewable():
                    self.transient(parent)
                    x = parent.winfo_x() + ((parent.winfo_width() or dlg_w) - dlg_w) // 2
                    y = parent.winfo_y() + ((parent.winfo_height() or dlg_h) - dlg_h) // 2
                else:
                    x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)
            except Exception:
                x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)

            pos_x = f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"
            pos_y = f"+{int(y)}" if int(y) >= 0 else f"{int(y)}"
            self.geometry(f"{dlg_w}x{dlg_h}{pos_x}{pos_y}")

            try:
                self.attributes("-alpha", 0.96)
            except Exception:
                pass

            ico_path, png_path = get_resource_path("app_icon.ico"), get_resource_path("app_icon.png")
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

        if self.parent_app and hasattr(self.parent_app, "sniffer_platforms") and isinstance(self.parent_app.sniffer_platforms, dict):
            self.sniffer_platforms = dict(self.parent_app.sniffer_platforms)
        else:
            self.sniffer_platforms = dict(get_setting("sniffer_platforms", DEFAULT_SNIFFER_PLATFORMS) or DEFAULT_SNIFFER_PLATFORMS)

        self._plat_buttons: Dict[str, Any] = {}
        if tk is not None:
            self._build_ui()
            self.bind("<Escape>", lambda e: self._on_close())

            self._topmost_job = None
            self._idle_job = None
            try:
                self.lift()
                self.attributes("-topmost", True)
                self.focus_force()
                self._topmost_job = self.after(250, lambda: self.attributes("-topmost", False) if self.winfo_exists() else None)
                self._idle_job = self.after_idle(lambda: (self.lift(), self.focus_force()) if self.winfo_exists() else None)
            except Exception:
                pass

    def _on_drag_press(self, event):
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event):
        x = event.x_root - getattr(self, "_drag_offset_x", 0)
        y = event.y_root - getattr(self, "_drag_offset_y", 0)
        pos_x = f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"
        pos_y = f"+{int(y)}" if int(y) >= 0 else f"{int(y)}"
        self.geometry(f"{pos_x}{pos_y}")

    def grab_set(self): pass
    def grab_set_global(self): pass

    def destroy(self):
        try:
            self.withdraw()
        except Exception:
            pass
        for job_attr in ("_topmost_job", "_idle_job"):
            job = getattr(self, job_attr, None)
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                setattr(self, job_attr, None)
        if self.parent_app and getattr(self.parent_app, "_settings_modal", None) is self:
            self.parent_app._settings_modal = None
        try:
            super().destroy()
        finally:
            for p in ("_modal_icon_photo", "_modal_title_photo"):
                if hasattr(self, p) and getattr(self, p):
                    try:
                        _detach_photo_tk(getattr(self, p))
                    except Exception:
                        pass

    def _on_close(self):
        """Safely and immediately close SettingsModal without timer animations."""
        self._save_manual_dir_if_valid()
        self.destroy()
