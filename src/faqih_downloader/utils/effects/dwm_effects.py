"""
Windows DWM dark titlebar, Acrylic, and Mica backdrop effects via Win32 APIs for Faqih Downloader.
"""
from __future__ import annotations

import sys
import ctypes
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.services.startup_service import IS_WINDOWS


def enable_dark_titlebar(win: Any, _deferred: bool = False) -> bool:
    """Applies Win32 DWM immersive dark titlebar and caption colors to any Tk or Toplevel window."""
    if not win or not IS_WINDOWS:
        return False
    try:
        try:
            win.update_idletasks()
        except Exception:
            pass
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        wintypes = ctypes.wintypes
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

        raw_id = win.winfo_id()
        hwnds = []
        try:
            frm_hex = str(win.wm_frame() or "").strip()
            if frm_hex and frm_hex != "0x0":
                frm_hwnd = int(frm_hex, 16)
                if frm_hwnd:
                    hwnds.append(frm_hwnd)
        except Exception:
            pass
        for h in (user32.GetAncestor(raw_id, 2), user32.GetParent(raw_id), raw_id):
            if h and h not in hwnds:
                hwnds.append(h)
        if not hwnds:
            return False

        dark_mode = ctypes.c_int(1)
        caption_bgr = wintypes.DWORD(0x00140E0B)  # #0b0e14
        text_bgr = wintypes.DWORD(0x00FCFAF8)     # #f8fafc
        border_bgr = wintypes.DWORD(0x00483528)   # #283548
        for hwnd in hwnds:
            for attr in (20, 19):
                try:
                    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
                except Exception:
                    pass
            for attr, col in ((35, caption_bgr), (36, text_bgr), (34, border_bgr)):
                try:
                    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(col), ctypes.sizeof(col))
                except Exception:
                    pass
            try:
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0037)
            except Exception:
                pass
        if not _deferred and not getattr(win, "_dark_titlebar_scheduled", False):
            try:
                win._dark_titlebar_scheduled = True
                win.after(15, lambda: enable_dark_titlebar(win, _deferred=True) if win.winfo_exists() else None)
            except Exception:
                pass
        return True
    except Exception:
        return False


def apply_acrylic_or_mica_effect(root: Any, alpha: float = 1.0) -> bool:
    """
    Enables Windows 11 / Windows 10 Dark Mode and rounded corners behind
    the frameless window. Eliminates ACCENT_ENABLE_ACRYLICBLURBEHIND for 60fps smooth resize.
    """
    if not root:
        return False

    clamped_alpha = max(0.60, min(1.0, float(alpha)))
    try:
        root.attributes("-alpha", clamped_alpha)
    except Exception:
        pass

    if not IS_WINDOWS:
        return True

    # Never apply DWM composition or Win32 backdrop effects to child Toplevels or modals
    if tk is not None and not isinstance(root, tk.Tk):
        return True

    # Apply Win32 DWM Backdrop Attributes on root window only
    try:
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.GetParent.restype = ctypes.c_void_p
        raw_id = root.winfo_id()
        hwnd = user32.GetParent(raw_id) or raw_id
        if not hwnd:
            return False

        enable_dark_titlebar(root)

        # DWMWA_WINDOW_CORNER_PREFERENCE (33): 2 = DWMWCP_ROUND (Rounded window corners)
        corner_pref = ctypes.c_int(2)
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(corner_pref), ctypes.sizeof(corner_pref)
            )
        except Exception:
            pass

        return True
    except Exception:
        return False


def apply_window_opacity(root: Any, alpha: float = 1.0) -> bool:
    """Sets window opacity cleanly on root window."""
    if not root:
        return False
    try:
        root.attributes("-alpha", max(0.60, min(1.0, float(alpha))))
        return True
    except Exception:
        return False
