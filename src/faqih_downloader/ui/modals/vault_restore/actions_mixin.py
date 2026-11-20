"""
VaultRestoreActionsMixin: Disk browsing, folder loading, history batch additions, and modal finalization.
"""
from __future__ import annotations
import os
from typing import Any, List, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = filedialog = None  # type: ignore

from faqih_downloader.locales.i18n import tr
from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files


class VaultRestoreActionsMixin:
    """Provides methods for folder/file selection, batch adding to history, and modal closing."""

    def browse_folder(self) -> int:
        """Prompts user to select a folder from disk and loads unregistered files from it."""
        if not filedialog:
            return 0
        selected_dir = filedialog.askdirectory(parent=self, title=tr("vault_btn_browse_folder", "▤ Browse Folder..."))
        if not selected_dir or not os.path.isdir(selected_dir):
            return 0
        self._current_scan_dir = selected_dir
        if hasattr(self, "lbl_current_folder") and self.lbl_current_folder:
            self.lbl_current_folder.configure(text=f"📂 {selected_dir}")
            try: self.update_idletasks()
            except Exception: pass

        self._all_files = scan_unregistered_disk_files(self.gui, custom_dir=selected_dir)
        self._item_vars.clear()
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()
        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=False)
        self._display_limit = 40
        self._display_files()
        return len(self._all_files)

    def _batch_add_entries(self, items: List[Tuple[str, int]]) -> int:
        """Adds a batch of files to history_manager efficiently with a single flush."""
        hm = getattr(self.gui, "history_manager", None)
        if not hm or not items:
            return 0
        added = 0
        for path, sz in items:
            try:
                hm.add_or_update_entry(url="", file_path=path, size_bytes=sz, status="Completed", save=False)
            except TypeError:
                hm.add_or_update_entry(url="", file_path=path, size_bytes=sz, status="Completed")
            added += 1
        for s_fn in ("_save_entries", "save_entries", "save"):
            fn = getattr(hm, s_fn, None)
            if callable(fn):
                try: fn(); break
                except Exception: pass
        return added

    def restore_selected(self) -> int:
        """Restores only files with active checkbox checked."""
        items = [
            (f["file_path"], f.get("size_bytes", 0))
            for f in self._all_files
            if self._item_vars.get(f["file_path"]) and self._item_vars[f["file_path"]].get()
        ]
        count = self._batch_add_entries(items)
        self._finalize_and_close()
        return count

    def restore_all(self) -> int:
        """Restores all discovered files regardless of filter or checkbox state."""
        items = [(f["file_path"], f.get("size_bytes", 0)) for f in self._all_files]
        count = self._batch_add_entries(items)
        self._finalize_and_close()
        return count

    def browse_files(self) -> int:
        """Prompts user to select arbitrary files from disk and adds them to history."""
        if not filedialog:
            return 0
        selected = filedialog.askopenfilenames(parent=self, title=tr("vault_btn_browse_file", "▣ Browse File..."))
        if not selected:
            return 0
        items = [(p, os.path.getsize(p) if os.path.isfile(p) else 0) for p in selected if os.path.isfile(p)]
        count = self._batch_add_entries(items)
        if count > 0:
            self._finalize_and_close()
        return count

    def _finalize_and_close(self):
        """Refreshes Column 3 and history table, then cleanly destroys modal dialog."""
        if hasattr(self.gui, "_vault_filter_category"):
            self.gui._vault_filter_category = "all"
        for fn_name in ("refresh_history_table", "refresh_kanban_col3"):
            fn = getattr(self.gui, fn_name, None)
            if callable(fn):
                try: fn()
                except Exception: pass
        if hasattr(self.gui, "_refresh_history_table") and callable(self.gui._refresh_history_table):
            try: self.gui._refresh_history_table(force=True)
            except Exception:
                try: self.gui._refresh_history_table()
                except Exception: pass
        self.destroy()
