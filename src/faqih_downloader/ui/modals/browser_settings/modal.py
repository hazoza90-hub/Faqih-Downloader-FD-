"""
BrowserSettingsModalMixin: Browser WebExtension setup dialog and host registration.
"""
from __future__ import annotations
import os
import sys

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from ....config import get_resource_path
from ....locales.i18n import tr
from ....utils.tk_helpers import _detach_photo_tk
from ....utils.window_effects import enable_dark_titlebar
from ...controllers.browser_controller import BrowserControllerMixin
from .status_section import build_status_section
from .capture_settings_section import build_capture_settings_section
from .extension_section import build_extension_section


class BrowserSettingsModalMixin(BrowserControllerMixin):
    """
    Mixin providing browser integration dialog and background self-registration
    for ModernFramelessGUI.
    """

    def _open_browser_integration_dialog(self):
        """Displays settings, connection status, and extension installation instructions."""
        if hasattr(self, "_browser_integration_dlg") and self._browser_integration_dlg:
            try:
                if hasattr(self._browser_integration_dlg, "_browser_icon_photo"):
                    _detach_photo_tk(self._browser_integration_dlg._browser_icon_photo)
                    self._browser_integration_dlg._browser_icon_photo = None
                if self._browser_integration_dlg.winfo_exists():
                    self._browser_integration_dlg.destroy()
            except Exception:
                pass
            self._browser_integration_dlg = None

        dlg = tk.Toplevel(self.root)
        self._browser_integration_dlg = dlg
        dlg.title(tr("browser_dlg_title", "❖ Browser Integration & WebExtension Setup"))
        dlg.transient(self.root)
        dlg.grab_set = lambda: None
        dlg.grab_set_global = lambda: None
        try:
            dlg.lift()
            dlg.attributes("-topmost", True)
            dlg.focus_force()
            dlg.after(250, lambda: dlg.attributes("-topmost", False) if dlg.winfo_exists() else None)
        except Exception:
            pass

        dpi_scale = getattr(self, "dpi_scale", 1.0)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        dlg_w = min(int(680 * dpi_scale), max(600, int(sw * 0.92)))
        dlg_h = min(int(800 * dpi_scale), max(680, int(sh * 0.92)))
        try:
            px = self.root.winfo_x()
            py = self.root.winfo_y()
            pw = self.root.winfo_width() or self.width
            ph = self.root.winfo_height() or self.height
        except Exception:
            px, py, pw, ph = 0, 0, self.width, self.height
        x = px + (pw - dlg_w) // 2
        y = py + (ph - dlg_h) // 2
        pos_x = f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"
        pos_y = f"+{int(y)}" if int(y) >= 0 else f"{int(y)}"
        dlg.geometry(f"{dlg_w}x{dlg_h}{pos_x}{pos_y}")
        dlg.minsize(min(580, dlg_w), min(540, dlg_h))
        dlg.configure(bg=self.c_bg)

        # Apply application icon to dialog window
        ico_path = get_resource_path("app_icon.ico")
        png_path = get_resource_path("app_icon.png")
        if os.path.isfile(ico_path):
            try:
                dlg.iconbitmap(ico_path)
            except Exception:
                pass
        if os.path.isfile(png_path):
            try:
                from PIL import ImageTk
                dlg._browser_icon_photo = ImageTk.PhotoImage(file=png_path)
                dlg.iconphoto(False, dlg._browser_icon_photo)
                dlg.bind(
                    "<Destroy>",
                    lambda e: (_detach_photo_tk(getattr(dlg, "_browser_icon_photo", None)), setattr(dlg, "_browser_icon_photo", None)) if e.widget == dlg else None,
                    add="+"
                )
            except Exception:
                pass

        # Top Header Bar
        hdr = tk.Frame(dlg, bg=self.c_header, height=44, padx=14)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        lbl_hdr = tk.Label(hdr, text=tr("browser_dlg_header", "⚡ BROWSER INTEGRATION & WEBEXTENSION SETUP"), font=("Segoe UI", 10, "bold"), bg=self.c_header, fg=self.c_accent)
        lbl_hdr.pack(side=tk.LEFT, pady=10)

        btn_dlg_updates = tk.Button(
            hdr,
            text=tr("browser_btn_check_ext_updates", "↻ Check Updates"),
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light,
            fg=self.c_accent,
            relief="flat",
            activebackground=self.c_accent,
            activeforeground="white",
            cursor="hand2",
            padx=10,
            pady=2,
            command=self.check_for_updates_manual
        )
        btn_dlg_updates.pack(side=tk.RIGHT, pady=8)

        # Main Body
        body = tk.Frame(dlg, bg=self.c_bg, padx=14, pady=8)
        body.pack(fill=tk.BOTH, expand=True)

        # Sections
        build_capture_settings_section(self, body, dlg)
        build_status_section(self, body, dlg)
        build_extension_section(self, body, dlg, dlg_w)

        enable_dark_titlebar(dlg)

    open_browser_integration_dialog = _open_browser_integration_dialog


__all__ = ["BrowserSettingsModalMixin"]
