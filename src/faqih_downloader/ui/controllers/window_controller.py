"""
Window management, title bar chrome, and geometry controller mixin for Smart Download (SD).
"""
import os
import ctypes
from typing import Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import LocalizationManager, tr
from faqih_downloader.config import get_resource_path, APP_VERSION, get_setting, is_test_environment
from faqih_downloader.ui.components.tooltip import ToolTip
from faqih_downloader.utils.dpi import get_windows_work_area
from faqih_downloader.services import (
    IS_WINDOWS, GWL_STYLE, GWL_EXSTYLE, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW,
    WS_MINIMIZEBOX, WS_SYSMENU, SW_HIDE, SW_MINIMIZE, SW_RESTORE, SW_SHOW,
)

from .lifecycle_controller import WindowLifecycleMixin
from .theme_controller import ThemeControllerMixin
from .dispatch_controller import DispatchControllerMixin
from .window_resize_mixin import WindowResizeMixin

class WindowChromeMixin(ThemeControllerMixin, DispatchControllerMixin, WindowLifecycleMixin, WindowResizeMixin):
    """Provides window setup, custom frameless title bar dragging, and window geometry."""

    @staticmethod
    def _format_geometry(w: Optional[int], h: Optional[int], x: int, y: int) -> str:
        px, py = (f"+{int(x)}" if int(x) >= 0 else f"{int(x)}"), (f"+{int(y)}" if int(y) >= 0 else f"{int(y)}")
        return f"{int(w)}x{int(h)}{px}{py}" if w is not None and h is not None else f"{px}{py}"

    def _setup_window(self):
        """Configures frameless window, centering, and dragging."""
        if getattr(self, "_start_hidden", False):
            try: self.root.withdraw()
            except Exception: pass
        self.root.overrideredirect(True)
        try: self.root.title(tr("app_title", "فقيه التنزيلات (FD)"))
        except Exception: pass

        # Center on screen
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = max(0, (sw - self.width) // 2), max(0, (sh - self.height) // 2)
        geo = self._format_geometry(self.width, self.height, x, y)
        self.root.geometry(geo)
        self._is_maximized = False
        self._normal_geometry = geo
        scale = getattr(self, "dpi_scale", 1.0)
        self._min_width, self._min_height = max(820, int(820 * scale)), max(620, int(620 * scale))
        self._resize_state, self._resize_grips = {}, []
        self._setup_resizing()

        # Set Window Icons
        ico_path, png_path = get_resource_path("app_icon.ico"), get_resource_path("app_icon.png")
        if os.path.isfile(ico_path):
            try: self.root.iconbitmap(ico_path)
            except Exception: pass
        if os.path.isfile(png_path):
            try:
                from PIL import ImageTk
                self._app_icon_photo = ImageTk.PhotoImage(file=png_path)
                self.root.iconphoto(True, self._app_icon_photo)
            except Exception: pass

        # Windows Taskbar Integration
        if IS_WINDOWS:
            self.root.update_idletasks()
            try:
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE) | WS_MINIMIZEBOX | WS_SYSMENU
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

                is_hidden = getattr(self, "_start_hidden", False)
                ex_style = (ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & ~(WS_EX_TOOLWINDOW if not is_hidden else WS_EX_APPWINDOW)) | (WS_EX_TOOLWINDOW if is_hidden else WS_EX_APPWINDOW)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
                ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE if is_hidden else SW_SHOW)
                if is_hidden:
                    self.root.withdraw()

                if os.path.isfile(ico_path):
                    try:
                        ctypes.windll.user32.LoadImageW.restype = ctypes.c_void_p
                        ctypes.windll.user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
                        sm_cx, sm_cy = ctypes.windll.user32.GetSystemMetrics(49) or 16, ctypes.windll.user32.GetSystemMetrics(50) or 16
                        hicon_sm = ctypes.windll.user32.LoadImageW(None, ico_path, 1, sm_cx, sm_cy, 0x10)
                        if hicon_sm: ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_sm)
                        lg_cx, lg_cy = ctypes.windll.user32.GetSystemMetrics(11) or 32, ctypes.windll.user32.GetSystemMetrics(12) or 32
                        hicon_lg = ctypes.windll.user32.LoadImageW(None, ico_path, 1, lg_cx, lg_cy, 0x10)
                        if hicon_lg: ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_lg)
                    except Exception: pass
            except Exception: pass

        # Native Windows 10/11 Dark Mode and Window Alpha (1.0 default)
        try:
            from faqih_downloader.utils.window_effects import apply_acrylic_or_mica_effect
            from faqih_downloader.config import is_test_environment, set_setting
            alpha = float(getattr(self, "_window_alpha", None) or get_setting("window_alpha", 1.0))
            if alpha <= 0.95 and not get_setting("window_alpha_migrated_v203", False) and not is_test_environment():
                alpha = 1.0
                set_setting("window_alpha", 1.0)
                set_setting("window_opacity", 1.0)
                set_setting("window_alpha_migrated_v203", True)
            self._window_alpha = alpha
            apply_acrylic_or_mica_effect(self.root, alpha=alpha)
            if not is_test_environment() and not getattr(self, "_start_hidden", False):
                self.root.attributes("-alpha", 0.2)
                for _s in range(1, 9):
                    _a = 0.2 + (alpha - 0.2) * (_s / 8.0)
                    self.root.after(_s * 20, lambda a=_a: self.root.winfo_exists() and self.root.attributes("-alpha", a))
            else:
                self.root.attributes("-alpha", alpha)
        except Exception: pass
        if getattr(self, "_start_hidden", False):
            try: self.root.withdraw()
            except Exception: pass

        self.root.bind("<Map>", self._on_window_map, add="+")
        self.root.bind("<FocusIn>", self._on_window_focus_in, add="+")
        self._drag_offset_x = self._drag_offset_y = 0
        self._min_anim_jobs = []

    def _cancel_min_anim_jobs(self):
        """Cancels any pending minimize/fade after jobs."""
        for j in getattr(self, "_min_anim_jobs", []):
            try: self.root.after_cancel(j)
            except Exception: pass
        self._min_anim_jobs = []

    def _on_window_map(self, event=None):
        """Ensures that when OS maps the window, transparency is fully restored and hidden states handled."""
        self._cancel_min_anim_jobs()
        if getattr(event, "widget", None) == self.root:
            try:
                target_alpha = float(getattr(self, "_window_alpha", None) or get_setting("window_alpha", 1.0))
                self.root.attributes("-alpha", target_alpha)
            except Exception: pass
            if getattr(self, "_start_hidden", False):
                self.restore_window()

    def _on_window_focus_in(self, event=None):
        """Restores alpha if window regained focus while stuck in transparent minimize state."""
        if getattr(event, "widget", None) == self.root:
            try:
                if float(self.root.attributes("-alpha") or 1.0) < 0.60:
                    self._cancel_min_anim_jobs()
                    target_alpha = float(getattr(self, "_window_alpha", None) or get_setting("window_alpha", 1.0))
                    self.root.attributes("-alpha", target_alpha)
            except Exception: pass

    def restore_window(self):
        """Restores and brings the main window to foreground if hidden or minimized."""
        self._cancel_min_anim_jobs()
        self._start_hidden = False
        target_alpha = float(getattr(self, "_window_alpha", None) or get_setting("window_alpha", 1.0))
        try:
            self.root.attributes("-alpha", target_alpha)
            self.root.deiconify()
            if getattr(self, "_normal_geometry", None) and self.root.winfo_width() <= 1:
                self.root.geometry(self._normal_geometry)
            self.root.update_idletasks()
        except Exception: pass
        if IS_WINDOWS:
            try:
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                cur_ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (cur_ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
                ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0043)
                ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0043)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception: pass
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self._restore_idle_job = self.root.after_idle(lambda: self.root.attributes("-topmost", False) if hasattr(self, "root") and self.root else None)
            self.root.focus_force()
        except Exception: pass

    def _build_title_bar(self, parent):
        """Constructs the custom dark draggable title bar."""
        tb_height = max(38, int(38 * getattr(self, "dpi_scale", 1.0)))
        title_bar = tk.Frame(parent, bg=self.c_panel, height=tb_height)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)

        # Drag bindings using root coordinates for silky-smooth motion
        title_bar.bind("<ButtonPress-1>", self._on_title_press)
        title_bar.bind("<B1-Motion>", self._on_title_drag)

        # App Logo Icon in Title Bar
        png_path = get_resource_path("app_icon.png")
        if os.path.isfile(png_path):
            try:
                from PIL import Image, ImageTk
                icon_dim = max(20, int(20 * getattr(self, "dpi_scale", 1.0)))
                with Image.open(png_path) as im:
                    raw_icon = im.resize((icon_dim, icon_dim), Image.Resampling.LANCZOS)
                    self._title_icon_photo = ImageTk.PhotoImage(raw_icon)
                logo_lbl = tk.Label(title_bar, image=self._title_icon_photo, bg=self.c_panel)
                logo_lbl.pack(side=tk.LEFT, padx=(12, 4))
                logo_lbl.bind("<ButtonPress-1>", self._on_title_press)
                logo_lbl.bind("<B1-Motion>", self._on_title_drag)
            except Exception:
                pass

        # App Title
        self.title_lbl = tk.Label(
            title_bar, text=tr("app_header"),
            font=("Segoe UI", 10, "bold"), bg=self.c_panel, fg=self.c_accent
        )
        self.title_lbl.pack(side=tk.LEFT, padx=(6, 8))

        self.subtitle_lbl = tk.Label(
            title_bar, text=tr("app_subtitle"),
            font=("Segoe UI", 8), bg=self.c_panel, fg=self.c_text_muted
        )
        self.subtitle_lbl.pack(side=tk.LEFT)

        # Window Control Buttons (Close, Maximize/Restore, Minimize)
        for txt, fn, bg_hover, fg_hover, attr in [
            ("✕", lambda e: self._on_close(), self.c_danger, "white", None),
            ("□", self.toggle_maximize, self.c_panel_light, "white", "btn_max"),
            ("—", lambda e: self._on_minimize(), self.c_panel_light, "white", None),
        ]:
            b = tk.Label(title_bar, text=txt, font=("Segoe UI", 10 if txt != "✕" else 11, "bold"), bg=self.c_panel, fg=self.c_text_muted, width=4)
            b.pack(side=tk.RIGHT, fill=tk.Y)
            b.bind("<Enter>", lambda e, w=b, bg=bg_hover, fg=fg_hover: w.configure(bg=bg, fg=fg))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=self.c_panel, fg=self.c_text_muted))
            b.bind("<Button-1>", fn)
            if attr: setattr(self, attr, b)

        self.btn_check_updates = tk.Button(
            title_bar, text=tr("btn_check_updates", "↻ Check for Updates"), font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark,
            activeforeground="white", cursor="hand2", padx=10, pady=2, command=self.check_for_updates_manual
        )
        self.btn_check_updates.pack(side=tk.RIGHT, padx=(6, 8), pady=6)
        self.btn_update = self.btn_check_updates

        # Prominent Language Toggle Button
        cur_lang = LocalizationManager.get_instance().get_language()
        toggle_txt = "⇄ English" if cur_lang == "ar" else "⇄ العربية"
        self.btn_lang_toggle = tk.Button(
            title_bar, text=toggle_txt, font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark,
            activeforeground="white", cursor="hand2", padx=10, pady=2, command=self.toggle_language
        )
        self.btn_lang_toggle.pack(side=tk.RIGHT, padx=(4, 6), pady=6)
        ToolTip(self.btn_lang_toggle, "tip_lang_toggle")

        self.btn_settings = tk.Button(
            title_bar, text=tr("btn_settings", "⚙ Settings"), font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light, fg=self.c_accent, relief="flat", activebackground=self.c_accent_dark,
            activeforeground="white", cursor="hand2", padx=10, pady=2, command=self.open_settings_dialog
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(4, 4), pady=6)
        ToolTip(self.btn_settings, "tip_settings")

        lbl_ver = tk.Label(
            title_bar,
            text=f"v{APP_VERSION}",
            font=("Consolas", 8, "bold"),
            bg=self.c_panel,
            fg=self.c_success
        )
        lbl_ver.pack(side=tk.RIGHT, padx=(4, 4))

        # Double-click and drag bindings on title bar and text labels
        for w in (title_bar, self.title_lbl, self.subtitle_lbl, lbl_ver):
            w.bind("<ButtonPress-1>", self._on_title_press)
            w.bind("<B1-Motion>", self._on_title_drag)
            w.bind("<ButtonRelease-1>", self._on_title_release)
            w.bind("<Double-Button-1>", self.toggle_maximize)

        # Separator Line
        sep = tk.Frame(parent, bg=self.c_panel_light, height=1)
        sep.pack(fill=tk.X, side=tk.TOP)

    def _on_title_press(self, event):
        self._drag_offset_x = event.x_root - self.root.winfo_x()
        self._drag_offset_y = event.y_root - self.root.winfo_y()

    def _on_title_release(self, event):
        if not getattr(self, "_is_maximized", False):
            try: self._normal_geometry = self.root.geometry()
            except Exception: pass

    def _on_title_drag(self, event):
        if getattr(self, "_is_maximized", False):
            cur_w = max(1, self.root.winfo_width())
            click_x_rel = event.x_root - self.root.winfo_x()
            ratio = max(0.0, min(1.0, click_x_rel / cur_w))

            norm_geo = getattr(self, "_normal_geometry", "")
            restored_w = getattr(self, "width", 850)
            restored_h = getattr(self, "height", 650)
            if norm_geo and "x" in norm_geo:
                try:
                    w_part, rest = norm_geo.split("x", 1)
                    restored_w = int(w_part)
                    restored_h = int(rest.split("+")[0].split("-")[0])
                except Exception: pass

            self._is_maximized = False
            if hasattr(self, "btn_max") and self.btn_max:
                try:
                    self.btn_max.configure(text="□")
                except Exception: pass
            self._show_resize_grips()

            self._drag_offset_x = int(restored_w * ratio)
            self._drag_offset_y = max(10, min(30, getattr(event, "y", 20)))
            x = event.x_root - self._drag_offset_x
            y = event.y_root - self._drag_offset_y
            self.root.geometry(self._format_geometry(restored_w, restored_h, x, y))
            return

        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self.root.geometry(self._format_geometry(None, None, x, y))

    _on_drag_motion = _on_title_drag

    def toggle_maximize(self, event=None):
        """Toggles between maximized work area and restored normal window geometry."""
        if not getattr(self, "_is_maximized", False):
            try: self._normal_geometry = self.root.geometry()
            except Exception: pass
            hwnd = None
            try: hwnd = self.root.winfo_id()
            except Exception: pass
            wa = get_windows_work_area(hwnd) if IS_WINDOWS else None
            if wa:
                work_x, work_y = wa[0], wa[1]
                work_w, work_h = wa[2] - wa[0], wa[3] - wa[1]
            else:
                work_x, work_y = 0, 0
                try: sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                except Exception: sw, sh = 1920, 1080
                work_w, work_h = sw, max(getattr(self, "_min_height", 620), sh - 40)

            try: self.root.geometry(self._format_geometry(work_w, work_h, work_x, work_y))
            except Exception: pass
            self._is_maximized = True
            if hasattr(self, "btn_max") and self.btn_max:
                try: self.btn_max.configure(text="❐")
                except Exception: pass
            self._hide_resize_grips()
        else:
            norm_geo = getattr(self, "_normal_geometry", None)
            if norm_geo:
                try: self.root.geometry(norm_geo)
                except Exception: pass
            self._is_maximized = False
            if hasattr(self, "btn_max") and self.btn_max:
                try: self.btn_max.configure(text="□")
                except Exception: pass
            self._show_resize_grips()

    def _on_minimize(self):
        """Minimize frameless window smoothly with fade-out."""
        self._cancel_min_anim_jobs()
        target_alpha = float(getattr(self, "_window_alpha", None) or get_setting("window_alpha", 0.92))

        def _do_min():
            if IS_WINDOWS:
                try:
                    hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                    ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
                except Exception: pass
            else:
                try:
                    self.root.overrideredirect(False)
                    self.root.iconify()
                except Exception: pass
            job = self.root.after(50, lambda: self.root.winfo_exists() and self.root.attributes("-alpha", target_alpha))
            self._min_anim_jobs.append(job)

        if is_test_environment() or not getattr(self, "root", None):
            return _do_min()
        for s in range(1, 7):
            _a = max(0.05, target_alpha - (target_alpha - 0.05) * (s / 6.0))
            if s == 6:
                j = self.root.after(s * 20, _do_min)
            else:
                j = self.root.after(s * 20, lambda a=_a: self.root.winfo_exists() and self.root.attributes("-alpha", a))
            self._min_anim_jobs.append(j)

    def is_window_hidden_or_minimized(self) -> bool:
        """Determines if the main application window is minimized, iconic, withdrawn, or hidden."""
        if getattr(self, "_start_hidden", False): return True
        if not hasattr(self, "root") or not self.root: return False
        try:
            if not self.root.winfo_exists(): return False
            if self.root.state() in ("withdrawn", "iconic") or not self.root.winfo_viewable(): return True
            if IS_WINDOWS:
                try:
                    hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                    if ctypes.windll.user32.IsIconic(hwnd): return True
                except Exception: pass
        except Exception: pass
        return False

    def open_settings_dialog(self):
        """Fallback for opening settings dialog; overridden by SettingsControllerMixin."""
        pass

WindowControllerMixin = WindowChromeMixin
__all__ = [
    'WindowChromeMixin',
    'WindowControllerMixin',
    'WindowLifecycleMixin',
    'ThemeControllerMixin',
    'DispatchControllerMixin',
    'WindowResizeMixin',
]

