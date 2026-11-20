"""
SettingsNetworkSystemMixin: Network thread warnings, cookie management, and OS system integrations.
"""
from __future__ import annotations
import os

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = filedialog = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting
from faqih_downloader.services import is_startup_enabled, enable_startup, disable_startup


class SettingsNetworkSystemMixin:
    """Provides network configuration, cookie selection, resolution defaults, and startup/tray settings."""

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
