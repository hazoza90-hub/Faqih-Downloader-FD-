"""
SettingsSnifferHandlersMixin: Platform sniffer toggling, button updates, and master sniffer switches.
"""
from __future__ import annotations
from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting, DEFAULT_SNIFFER_PLATFORMS


class SettingsSnifferHandlersMixin:
    """Provides methods for toggling clipboard sniffer platforms and updating visual button states."""

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
