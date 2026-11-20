"""
VaultRestoreRowsMixin: File row generation, formatting, and pagination loading.
"""
from __future__ import annotations
from typing import Any, List, Dict

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.locales.i18n import tr


def _format_size(size_bytes: int) -> str:
    """Formats raw bytes into human-readable unit string."""
    if size_bytes <= 0:
        return "0 B"
    s = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024:
            return f"{s:.1f} {unit}" if unit != "B" else f"{int(s)} B"
        s /= 1024.0
    return f"{s:.1f} PB"


class VaultRestoreRowsMixin:
    """Provides methods for rendering file rows, pagination buttons, and filtered lists."""

    def _append_file_rows(self, files_slice: List[Dict[str, Any]]):
        """Renders a batch of file rows in scrollable frame."""
        for f_info in files_slice:
            path = f_info["file_path"]
            var = self._item_vars.get(path)
            if var is None:
                var = tk.BooleanVar(master=self, value=False)
                self._item_vars[path] = var

            is_selected = bool(var.get())
            bg_color = "#1e3a5f" if is_selected else self.c_card
            border_color = "#38bdf8" if is_selected else self.c_border

            row = tk.Frame(
                self.scrollable_frame, bg=bg_color, padx=10, pady=8,
                highlightthickness=1, highlightbackground=border_color, cursor="hand2"
            )
            row.pack(fill=tk.X, pady=2)

            cb = tk.Checkbutton(
                row, variable=var, bg=bg_color, activebackground=bg_color,
                selectcolor="#0f172a", fg=self.c_accent, activeforeground=self.c_accent,
                cursor="hand2", command=lambda p=path: self._on_cb_toggle(p)
            )
            cb.pack(side=tk.LEFT, padx=(0, 8))

            name_lbl = tk.Label(
                row, text=f_info["filename"], font=("Segoe UI", 9, "bold"),
                bg=bg_color, fg=self.c_text_bright, anchor="w", cursor="hand2"
            )
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            cat_lbl = tk.Label(
                row, text=f"[{f_info.get('category', 'general').upper()}]",
                font=("Segoe UI", 8), bg=bg_color, fg=self.c_accent, cursor="hand2"
            )
            cat_lbl.pack(side=tk.RIGHT, padx=(6, 0))

            size_lbl = tk.Label(
                row, text=_format_size(f_info.get("size_bytes", 0)),
                font=("Segoe UI", 9), bg=bg_color, fg=self.c_text_muted, cursor="hand2"
            )
            size_lbl.pack(side=tk.RIGHT, padx=(6, 6))

            self._row_widgets[path] = {
                "row": row, "cb": cb, "name": name_lbl, "cat": cat_lbl, "size": size_lbl,
            }

            for w in (row, name_lbl, cat_lbl, size_lbl):
                w.bind("<Button-1>", lambda e, p=path: self._toggle_item(p))

    def _create_load_more_button(self, filtered: List[Dict[str, Any]], remaining: int):
        """Creates an elegant load more button at the bottom of the scrollable frame."""
        btn_txt = f"⬇ {tr('vault_load_more', 'Show More')} ({remaining} {tr('vault_remaining', 'remaining')})"
        self._btn_load_more = tk.Button(
            self.scrollable_frame, text=btn_txt, font=("Segoe UI", 9, "bold"),
            bg=self.c_card, fg=self.c_accent_blue, activebackground=self.c_border,
            activeforeground="#ffffff", relief=tk.FLAT, padx=14, pady=8, cursor="hand2",
            command=lambda: self._on_load_more(filtered)
        )
        self._btn_load_more.pack(fill=tk.X, pady=6)

    def _on_load_more(self, filtered: List[Dict[str, Any]]):
        """Loads and appends the next batch of files without recreating previous rows."""
        if hasattr(self, "_btn_load_more") and self._btn_load_more:
            try:
                self._btn_load_more.destroy()
            except Exception:
                pass
            self._btn_load_more = None

        old_limit = self._display_limit
        self._display_limit += 40
        next_slice = filtered[old_limit:self._display_limit]
        self._append_file_rows(next_slice)

        remaining = len(filtered) - self._display_limit
        if remaining > 0:
            self._create_load_more_button(filtered, remaining)

        self._schedule_scrollregion_update()

    def _display_files(self):
        """Renders paginated file rows in scrollable frame, filtering by search query."""
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()

        for child in self.scrollable_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._btn_load_more = None

        query = self.entry_search.get().strip().lower() if hasattr(self, "entry_search") else ""
        filtered = [f for f in self._all_files if not query or query in f["filename"].lower()]

        if not filtered:
            lbl_empty = tk.Label(
                self.scrollable_frame, text=tr("vault_no_unregistered_files", "No unregistered files found on disk"),
                font=("Segoe UI", 10), bg=self.c_bg, fg=self.c_text_muted, pady=40
            )
            lbl_empty.pack(fill=tk.BOTH, expand=True)
            self._update_restore_btn_text()
            return

        visible = filtered[:self._display_limit]
        self._append_file_rows(visible)

        remaining = len(filtered) - self._display_limit
        if remaining > 0:
            self._create_load_more_button(filtered, remaining)

        self._update_restore_btn_text()
        self._schedule_scrollregion_update()
