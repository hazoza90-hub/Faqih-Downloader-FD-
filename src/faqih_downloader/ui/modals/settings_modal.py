"""
SettingsModal: Frameless dark application settings dialog with per-platform sniffer filtering,
speed limiter controls, engine activity log, and downloads configuration.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Any, Optional, List, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import (
    get_setting,
    set_setting,
    get_base_downloads_dir,
    get_resource_path,
    is_test_environment,
    DEFAULT_SNIFFER_PLATFORMS,
)
from faqih_downloader.services import is_startup_enabled, enable_startup, disable_startup
from faqih_downloader.ui.modals.quality_modal_helpers import build_quality_title_bar
from faqih_downloader.utils.tk_helpers import _detach_photo_tk
from .settings_modal_tabs import SettingsModalTabsMixin

_BaseToplevel = tk.Toplevel if tk is not None else object


class SettingsModal(SettingsModalTabsMixin, _BaseToplevel):
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

        self._plat_buttons: Dict[str, tk.Button] = {}
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

    def _sync_dir_to_parent_app(self, new_dir: str):
        try:
            if not new_dir or not self.parent_app or not hasattr(self.parent_app, "entry_dest") or not self.parent_app.entry_dest:
                return
            eng = getattr(self.parent_app, "engine", None)
            if eng and (getattr(eng, "is_running", False)() if callable(getattr(eng, "is_running", False)) else getattr(eng, "is_running", False)):
                return
            cur_dest = self.parent_app.entry_dest.get().strip()
            if not cur_dest or os.path.isdir(cur_dest):
                target = new_dir
            else:
                fn = os.path.basename(cur_dest)
                target = os.path.join(new_dir, fn) if fn else new_dir
            self.parent_app.entry_dest.delete(0, tk.END if tk is not None else "end")
            self.parent_app.entry_dest.insert(0, target)
        except Exception:
            pass

    def _save_manual_dir_if_valid(self):
        if hasattr(self, "entry_dir") and self.entry_dir:
            try:
                typed = self.entry_dir.get().strip()
                if typed and os.path.isdir(typed):
                    set_setting("last_download_dir", typed)
                    if self.parent_app and hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                        self.parent_app.log(f"[SETTINGS] Default download directory set to: {typed}")
                    self._sync_dir_to_parent_app(typed)
            except Exception:
                pass

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

    def _build_ui(self):
        outer = tk.Frame(self, bg=self.c_border, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self.title_bar = build_quality_title_bar(
            self, outer, self.theme, tr("settings_modal_title", "⚙ Application Settings — Faqih Downloader"), self._on_close
        )
        body = tk.Frame(outer, bg=self.c_bg, padx=14, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        try:
            st = ttk.Style(self)
            st.theme_use("clam")
            st.layout("Custom.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
            st.configure("Custom.TNotebook", background=self.c_bg, borderwidth=0, tabmargins=[0, 2, 0, 0])
            st.configure(
                "Custom.TNotebook.Tab",
                background=self.c_panel,
                foreground=self.c_text_muted,
                bordercolor=self.c_border,
                lightcolor=self.c_panel,
                darkcolor=self.c_panel,
                focuscolor=self.c_panel,
                padding=[14, 6],
                font=("Segoe UI", 9, "bold"),
            )
            st.map(
                "Custom.TNotebook.Tab",
                background=[("selected", "#1a2030"), ("active", "#252f42")],
                foreground=[("selected", "#19f3ee"), ("active", "#f8fafc")],
                bordercolor=[("selected", "#19f3ee"), ("active", self.c_border)],
            )
        except Exception:
            pass

        nb = ttk.Notebook(body, style="Custom.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Build tabs with border styling strictly matching test assertions
        def _make_tab(name: str):
            f = tk.Frame(
                nb,
                bg=self.c_bg,
                padx=12,
                pady=10,
                bd=0,
                highlightthickness=1,
                highlightbackground=self.c_border,
                highlightcolor=self.c_border,
            )
            nb.add(f, text=name)
            return f

        tab_sniffer = _make_tab(tr("settings_tab_sniffer", " ⚙ Sniffer "))
        tab_downloads = _make_tab(tr("settings_tab_downloads", " ❖ Downloads "))
        tab_limiter = _make_tab(tr("settings_tab_limiter", " ⚡ Speed Limiter "))
        tab_system = _make_tab(tr("settings_tab_system", " ⚡ System "))
        tab_log = _make_tab(tr("settings_tab_log", " ▤ Engine Log "))

        self._build_sniffer_tab(tab_sniffer)
        self._build_downloads_tab(tab_downloads)
        self._build_limiter_tab(tab_limiter)
        self._build_system_tab(tab_system)
        self._build_log_tab(tab_log)

        footer = tk.Frame(body, bg=self.c_bg)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(
            footer,
            text=tr("settings_btn_save_close", "Close"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=18,
            pady=4,
            command=self._on_close,
        ).pack(side=tk.RIGHT)

    def _toggle_master_sniffer(self):
        if self.parent_app and hasattr(self.parent_app, "toggle_clipboard_sniffer"):
            self.parent_app.toggle_clipboard_sniffer()
            active = getattr(self.parent_app, "_clipboard_sniffer_active", True)
        else:
            active = not bool(get_setting("clipboard_sniffer_active", True))
            set_setting("clipboard_sniffer_active", active)
        self.btn_master_sniffer.configure(
            text=tr("settings_sniffer_master_on") if active else tr("settings_sniffer_master_off"),
            bg="#0f292a" if active else "#182234",
            fg=self.c_success if active else self.c_text_muted,
            highlightbackground="#10b981" if active else self.c_border,
        )

    def _toggle_platform(self, key: str, tr_key: str):
        nxt = not bool(self.sniffer_platforms.get(key, True))
        if key == "threads":
            self.sniffer_platforms["threads"] = self.sniffer_platforms["snapchat"] = self.sniffer_platforms["rumble"] = nxt
        else:
            self.sniffer_platforms[key] = nxt
        set_setting("sniffer_platforms", self.sniffer_platforms)
        if self.parent_app:
            self.parent_app.sniffer_platforms = dict(self.sniffer_platforms)
            if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                self.parent_app.log(f"[SETTINGS] Clipboard sniffer for {key}: {'Enabled' if nxt else 'Disabled'}")
        self._refresh_platform_btn(key, tr_key)

    def _refresh_platform_btn(self, key: str, tr_key: str):
        btn = self._plat_buttons.get(key)
        if not btn:
            return
        is_on = bool(self.sniffer_platforms.get(key, True))
        name = tr(tr_key)
        btn.configure(
            text=f"[✓] {name}" if is_on else f"[  ] {name}",
            bg="#0f292a" if is_on else "#182234",
            fg=self.c_success if is_on else self.c_text_muted,
            highlightbackground="#10b981" if is_on else self.c_border,
        )

    def _set_all_platforms(self, state: bool):
        for k in list(DEFAULT_SNIFFER_PLATFORMS.keys()):
            self.sniffer_platforms[k] = bool(state)
        set_setting("sniffer_platforms", self.sniffer_platforms)
        if self.parent_app:
            self.parent_app.sniffer_platforms = dict(self.sniffer_platforms)
            if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                self.parent_app.log(f"[SETTINGS] {'Enabled' if state else 'Disabled'} all platforms for clipboard sniffer.")
        for k, tk_k in self.PLATFORM_DEFS:
            self._refresh_platform_btn(k, tk_k)

    def _browse_save_dir(self):
        try:
            cur = self.entry_dir.get().strip() or get_base_downloads_dir()
            chosen = filedialog.askdirectory(parent=self, initialdir=cur) if filedialog else ""
            if chosen and os.path.isdir(chosen):
                self.entry_dir.delete(0, tk.END)
                self.entry_dir.insert(0, chosen)
                set_setting("last_download_dir", chosen)
                if self.parent_app and hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                    self.parent_app.log(f"[SETTINGS] Default download directory set to: {chosen}")
                self._sync_dir_to_parent_app(chosen)
        except Exception:
            pass

    def _toggle_auto_cat(self):
        if self.parent_app and hasattr(self.parent_app, "toggle_auto_categorize"):
            self.parent_app.toggle_auto_categorize()
            state = getattr(self.parent_app, "auto_categorize_folders", True)
        else:
            state = not bool(get_setting("auto_categorize_folders", True))
            set_setting("auto_categorize_folders", state)
        self.btn_auto_cat.configure(
            text=tr("settings_downloads_auto_cat_on") if state else tr("settings_downloads_auto_cat_off"),
            bg="#0f292a" if state else "#182234",
            fg=self.c_success if state else self.c_text_muted,
            highlightbackground="#10b981" if state else self.c_border,
        )

    def _toggle_unpack(self):
        nxt = not bool(get_setting("auto_unpack_archives", False))
        set_setting("auto_unpack_archives", nxt)
        if self.parent_app:
            self.parent_app.auto_unpack_archives = nxt
            if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                self.parent_app.log(f"[SETTINGS] Auto-unpack archives: {'Enabled' if nxt else 'Disabled'}")
        self.btn_unpack.configure(
            text=tr("settings_downloads_unpack_on") if nxt else tr("settings_downloads_unpack_off"),
            bg="#0f292a" if nxt else "#182234",
            fg=self.c_success if nxt else self.c_text_muted,
            highlightbackground="#10b981" if nxt else self.c_border,
        )

    def _update_threads_warning(self, val=None):
        if not hasattr(self, "lbl_threads_warn") or not self.lbl_threads_warn:
            return
        v = str(val or (self.cb_threads.get() if hasattr(self, "cb_threads") else "")).strip()
        if v == "32":
            lang = get_setting("language", "ar")
            if str(lang).lower().startswith("en"):
                msg = "⚠ Warning: 32 connections may overload some routers or trigger temporary server rate limits (8 or 16 recommended)."
            else:
                msg = "⚠ تحذير: 32 اتصالاً قد يسبب ضغطاً عالياً على بعض أجهزة الراوتر أو تقييداً مؤقتاً من بعض الخوادم (يُنصح بـ 8 أو 16)."
            self.lbl_threads_warn.configure(text=msg)
            self.lbl_threads_warn.pack(fill=tk.X, padx=14, pady=(0, 6))
        else:
            self.lbl_threads_warn.pack_forget()

    def _on_threads_changed(self, event=None):
        try:
            n = int(self.cb_threads.get())
            set_setting("max_connections", n)
            self._update_threads_warning(str(n))
            if self.parent_app and hasattr(self.parent_app, "conn_var"):
                self.parent_app.conn_var.set(self.cb_threads.get())
            if self.parent_app and hasattr(self.parent_app, "cb_main_sub_pos") and self.parent_app.cb_main_sub_pos:
                try:
                    self.parent_app.cb_main_sub_pos.set(str(n))
                    if hasattr(self.parent_app, "_sync_media_bar_state"):
                        self.parent_app._sync_media_bar_state()
                except Exception: pass
            if self.parent_app and hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                self.parent_app.log(f"[SETTINGS] Default connections set to: {n}")
        except Exception:
            pass

    def _on_res_changed(self, event=None):
        val = next((h for h, lbl in self.RES_OPTIONS if lbl == self.cb_res.get()), 0)
        set_setting("preferred_video_height", val)
        if self.parent_app and hasattr(self.parent_app, "log") and callable(self.parent_app.log):
            self.parent_app.log(f"[SETTINGS] Preferred video resolution height set to: {val}")

    def _on_cookies_changed(self, event=None):
        sel = self.cb_cookies.get()
        if sel == "file...":
            chosen = (
                filedialog.askopenfilename(
                    parent=self,
                    title="Select Netscape cookies.txt file",
                    filetypes=[("Text / Cookie files", "*.txt;*.cookies"), ("All files", "*.*")],
                )
                if filedialog
                else ""
            )
            if chosen and os.path.isfile(chosen):
                set_setting("cookies_file", chosen)
                set_setting("cookies_browser", "file")
                if self.parent_app:
                    self.parent_app.cookies_file = chosen
                    self.parent_app.cookies_browser = "file"
                    if hasattr(self.parent_app, "_update_cookies_btn"):
                        self.parent_app._update_cookies_btn()
                    if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                        self.parent_app.log(f"[SETTINGS] Cookies file set to: {chosen}")
            else:
                self.cb_cookies.set("none")
                set_setting("cookies_file", "")
                set_setting("cookies_browser", "none")
                if self.parent_app:
                    self.parent_app.cookies_file = ""
                    self.parent_app.cookies_browser = "none"
                    if hasattr(self.parent_app, "_update_cookies_btn"):
                        self.parent_app._update_cookies_btn()
        else:
            set_setting("cookies_file", "")
            set_setting("cookies_browser", sel)
            if self.parent_app:
                self.parent_app.cookies_file = ""
                self.parent_app.cookies_browser = sel
                if hasattr(self.parent_app, "_update_cookies_btn"):
                    self.parent_app._update_cookies_btn()
                if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                    self.parent_app.log(f"[SETTINGS] Cookie browser set to: {sel.capitalize()}")

    def _toggle_startup(self):
        if self.parent_app and hasattr(self.parent_app, "toggle_startup_setting"):
            st_on = self.parent_app.toggle_startup_setting()
        else:
            cur = is_startup_enabled()
            if cur:
                disable_startup()
                st_on = False
                set_setting("startup_enabled", False)
            else:
                enable_startup(minimized=True)
                st_on = True
                set_setting("startup_enabled", True)
        self.btn_startup.configure(
            text=tr("settings_system_startup_on") if st_on else tr("settings_system_startup_off"),
            bg="#0f292a" if st_on else "#182234",
            fg=self.c_success if st_on else self.c_text_muted,
            highlightbackground="#10b981" if st_on else self.c_border,
        )

    def _toggle_tray(self):
        if self.parent_app and hasattr(self.parent_app, "toggle_minimize_to_tray_setting"):
            tray_on = self.parent_app.toggle_minimize_to_tray_setting()
        else:
            tray_on = not bool(get_setting("minimize_to_tray", True))
            set_setting("minimize_to_tray", tray_on)
        self.btn_tray.configure(
            text=tr("settings_system_tray_on") if tray_on else tr("settings_system_tray_off"),
            bg="#0f292a" if tray_on else "#182234",
            fg=self.c_success if tray_on else self.c_text_muted,
            highlightbackground="#10b981" if tray_on else self.c_border,
        )

    def _open_browser_guide(self):
        if self.parent_app:
            if hasattr(self.parent_app, "open_browser_integration_dialog"):
                self.parent_app.open_browser_integration_dialog()
            elif hasattr(self.parent_app, "_open_browser_integration_dialog"):
                self.parent_app._open_browser_integration_dialog()

    def _on_close(self):
        """Safely and immediately close SettingsModal without timer animations."""
        self._save_manual_dir_if_valid()
        self.destroy()


__all__ = ["SettingsModal"]
