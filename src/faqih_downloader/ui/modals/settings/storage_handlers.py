"""
SettingsStorageHandlersMixin: Directory selection, path synchronization, and archive/categorization settings.
"""
from __future__ import annotations
import os

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = filedialog = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting, get_base_downloads_dir


class SettingsStorageHandlersMixin:
    """Provides methods for managing download directories and file organization options."""

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

    def _browse_save_dir(self):
        try:
            cur = self.entry_dir.get().strip() or get_base_downloads_dir()
            chosen = filedialog.askdirectory(parent=self, initialdir=cur) if filedialog else ""
            if chosen and os.path.isdir(chosen):
                self.entry_dir.delete(0, tk.END if tk is not None else "end")
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
