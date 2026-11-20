"""
VaultRestoreSelectionMixin: Search filtering and interactive row selection handling.
"""
from __future__ import annotations
from typing import Any
from faqih_downloader.locales.i18n import tr


class VaultRestoreSelectionMixin:
    """Provides file search filtering, selection toggles, visual row state updates, and button counters."""

    def _on_search_changed(self, event=None):
        """Reset pagination limit and re-render files on live search query edit."""
        self._display_limit = 40
        self._display_files()

    def _toggle_all_selection(self, select: bool):
        """Sets all checkboxes to either checked or unchecked and refreshes visuals."""
        for var in self._item_vars.values():
            var.set(select)
        self._refresh_selection_visuals()

    def _toggle_item(self, path: str):
        """Toggles check state for a file, updating visuals and restore button counter."""
        var = self._item_vars.get(path)
        if var is not None:
            var.set(not var.get())
        self._update_row_visual(path)
        self._update_restore_btn_text()

    def _on_cb_toggle(self, path: str):
        """Called when user clicks directly on the tk.Checkbutton."""
        self._update_row_visual(path)
        self._update_restore_btn_text()

    def _update_row_visual(self, path: str):
        """Updates row background, border, and checkbox to reflect selection state."""
        widgets = getattr(self, "_row_widgets", {}).get(path)
        if not widgets:
            return
        var = self._item_vars.get(path)
        is_selected = bool(var.get()) if var else False
        bg = "#1e3a5f" if is_selected else self.c_card
        border = "#38bdf8" if is_selected else self.c_border
        try:
            widgets["row"].configure(bg=bg, highlightbackground=border)
            widgets["cb"].configure(bg=bg, activebackground=bg)
            for k in ("name", "cat", "size"):
                widgets[k].configure(bg=bg)
        except Exception:
            pass

    def _refresh_selection_visuals(self):
        """Refreshes all visible row visuals and the restore button text."""
        if hasattr(self, "_row_widgets"):
            for path in self._row_widgets:
                self._update_row_visual(path)
        self._update_restore_btn_text()

    def _update_restore_btn_text(self):
        """Updates text on btn_restore_sel to display the count of selected files."""
        if not hasattr(self, "btn_restore_sel") or not self.btn_restore_sel:
            return
        sel_count = sum(1 for v in self._item_vars.values() if v.get())
        base_text = tr("vault_btn_restore_selected", "✓ Restore Selected")
        self.btn_restore_sel.configure(text=f"{base_text} ({sel_count})" if sel_count > 0 else base_text)
