"""
QualitySelectionModal: Interactive video/audio resolution and stream format picker.
"""
from __future__ import annotations
import os
from typing import Optional, Callable, Dict, Any, List

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.config import get_resource_path
from faqih_downloader.locales.i18n import tr
from faqih_downloader.services.youtube_service import VideoFormatOption
from faqih_downloader.utils.tk_helpers import _detach_photo_tk, animate_window_open, animate_window_close
from .layout_builder import QualityModalLayoutMixin
from .selection_handlers import QualityModalSelectionMixin
from .action_handlers import QualityModalActionsMixin

_BaseToplevel = tk.Toplevel if tk is not None else object


class QualitySelectionModal(
    QualityModalActionsMixin,
    QualityModalSelectionMixin,
    QualityModalLayoutMixin,
    _BaseToplevel
):
    """Modern dark-themed modal dialog for choosing video quality, audio dubbing, and subtitle options."""

    def __init__(
        self, parent: Any, video_title: str, duration: int, options: List[VideoFormatOption],
        default_dest_path: str, theme: Dict[str, str], on_confirm: Callable[[VideoFormatOption, str], None],
        on_cancel: Optional[Callable[[], None]] = None,
        on_open_in_main: Optional[Callable[[VideoFormatOption, str], None]] = None,
        parent_app: Optional[Any] = None, audio_tracks: Optional[List[Dict[str, Any]]] = None,
        subtitle_tracks: Optional[List[Dict[str, Any]]] = None, video_url: str = "",
        raw_info: Optional[Dict[str, Any]] = None, initial_option: Optional[VideoFormatOption] = None
    ):
        if tk is not None:
            super().__init__(parent)
        self.video_title, self.duration = str(video_title or "YouTube Video"), int(duration or 0)
        self.options, self.dest_path, self.theme = options or [], str(default_dest_path or ""), theme
        self.on_confirm, self.on_cancel, self.on_open_in_main = on_confirm, on_cancel, on_open_in_main
        self.parent_app, self.video_url, self.raw_info = parent_app, str(video_url or ""), raw_info or {}
        self._initial_option = initial_option
        self.audio_tracks, self.subtitle_tracks = audio_tracks or [], subtitle_tracks or []
        self.cb_audio = self.cb_sub = None
        init_idx = self._resolve_initial_index()
        self.selected_option: Optional[VideoFormatOption] = self.options[init_idx] if (self.options and 0 <= init_idx < len(self.options)) else (self.options[0] if self.options else None)
        self._confirmed = False

        if tk is not None:
            self.title(tr("modal_quality_title", "Select Video Quality — Smart Download"))
            self.configure(bg=self.theme["c_bg"])
            try: self.overrideredirect(True)
            except Exception: pass

            try: dpi = float(parent.winfo_fpixels('1i')) if parent and parent.winfo_exists() else 96.0
            except Exception: dpi = 96.0
            dpi_scale = max(1.0, dpi / 96.0)
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            dlg_w, dlg_h = min(int(800 * dpi_scale), max(640, int(sw * 0.92))), min(int(655 * dpi_scale), max(550, int(sh * 0.90)))
            is_vis = False
            if parent is not None:
                try: is_vis = parent.winfo_exists() and parent.winfo_viewable() and parent.state() not in ("withdrawn", "iconic")
                except Exception: is_vis = False
            if is_vis:
                try:
                    self.transient(parent)
                    px, py = parent.winfo_x(), parent.winfo_y()
                    pw, ph = parent.winfo_width() or dlg_w, parent.winfo_height() or dlg_h
                    x, y = px + (pw - dlg_w) // 2, py + (ph - dlg_h) // 2
                except Exception:
                    x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)
            else:
                try: self.transient(""); self.deiconify()
                except Exception: pass
                x, y = max(0, (sw - dlg_w) // 2), max(0, (sh - dlg_h) // 2)
            pos_x = f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"
            pos_y = f"+{int(y)}" if int(y) >= 0 else f"{int(y)}"
            self.geometry(f"{dlg_w}x{dlg_h}{pos_x}{pos_y}")
            self.minsize(min(640, dlg_w), min(520, dlg_h))

            ico_path, png_path = get_resource_path("app_icon.ico"), get_resource_path("app_icon.png")
            if os.path.isfile(ico_path):
                try: self.iconbitmap(ico_path)
                except Exception: pass
            if os.path.isfile(png_path):
                try:
                    from PIL import ImageTk
                    self._modal_icon_photo = ImageTk.PhotoImage(file=png_path)
                    self.iconphoto(False, self._modal_icon_photo)
                except Exception: pass

            self._build_ui()
            animate_window_open(self, duration_ms=130)
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self.bind("<Escape>", lambda e: self._on_close())

            self._topmost_job = None
            self._idle_job = None
            try:
                self.lift()
                self.attributes("-topmost", True)
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
        try: self.withdraw()
        except Exception: pass
        for a in ("_idle_job", "_topmost_job"):
            j = getattr(self, a, None)
            if j:
                try: self.after_cancel(j)
                except Exception: pass
                setattr(self, a, None)
        try: self.grab_release()
        except Exception: pass
        if self.parent_app and getattr(self.parent_app, "_quality_modal", None) is self:
            self.parent_app._quality_modal = None
        try:
            super().destroy()
        finally:
            for p in ("_modal_icon_photo", "_modal_title_photo"):
                if hasattr(self, p) and getattr(self, p):
                    _detach_photo_tk(getattr(self, p)); setattr(self, p, None)

    def _on_close(self):
        if self.parent_app and getattr(self.parent_app, "_quality_modal", None) is self:
            self.parent_app._quality_modal = None
        def _cleanup():
            self.destroy()
            for host in (self.parent_app, self.master):
                if host and hasattr(host, "clear_last_clipboard_url"):
                    try: host.clear_last_clipboard_url()
                    except Exception: pass
            if self.on_cancel:
                try: self.on_cancel()
                except Exception: pass
        animate_window_close(self, on_done=_cleanup)
