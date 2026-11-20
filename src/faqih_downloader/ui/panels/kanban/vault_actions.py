"""
KanbanVaultActionsMixin: Action handlers, context menus, and file openers for Completed Vault.
"""
from __future__ import annotations
import os
from typing import Any, Dict

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.config import is_test_environment
from faqih_downloader.utils.file_ops import open_downloaded_file, open_containing_folder
from faqih_downloader.ui.panels.kanban_vault_helpers import (
    show_vault_context_menu,
    clear_completed_vault_entries,
    restore_vault_entries_from_disk,
    open_vault_restore_dialog,
    delete_vault_entry_with_confirm,
)


class KanbanVaultActionsMixin:
    """Provides file launching, entry deletion, restoration, and context menu dispatching."""

    def _on_vault_context_menu(self, event: Any, entry: Dict[str, Any]):
        callbacks = {
            "open_file": self._open_vault_file, "open_folder": self._open_vault_folder,
            "delete_entry": self._on_delete_vault_entry, "delete_from_disk": self._on_delete_vault_from_disk,
            "redownload": self._on_vault_redownload, "gui": self,
        }
        show_vault_context_menu(event, entry, getattr(self, "root", None), callbacks)

    def _on_vault_redownload(self, url: str):
        if url and hasattr(self, "entry_url") and self.entry_url:
            try:
                self.entry_url.delete(0, tk.END if tk is not None else "end")
                self.entry_url.insert(0, url)
            except Exception: pass
            if hasattr(self, "_on_start_download") and callable(self._on_start_download):
                self._on_start_download()

    def _on_delete_vault_from_disk(self, entry: Dict[str, Any]):
        file_path = entry.get("file_path") or ""
        if file_path:
            try:
                if os.path.isfile(file_path): os.remove(file_path)
            except Exception: pass
        self._on_delete_vault_entry(entry, skip_confirm=True)

    def _on_clear_completed_vault(self):
        clear_completed_vault_entries(self)

    def _on_restore_vault_from_disk(self, open_dialog: bool = False):
        if is_test_environment() and not open_dialog:
            restore_vault_entries_from_disk(self)
        else:
            open_vault_restore_dialog(self)

    def _on_delete_vault_entry(self, entry: Dict[str, Any], skip_confirm: bool = False):
        delete_vault_entry_with_confirm(self, entry, skip_confirm=skip_confirm)

    def _open_vault_file(self, file_path_or_name: str):
        if file_path_or_name: open_downloaded_file(file_path_or_name)

    def _open_vault_folder(self, file_path_or_name: str):
        if file_path_or_name: open_containing_folder(file_path_or_name)
