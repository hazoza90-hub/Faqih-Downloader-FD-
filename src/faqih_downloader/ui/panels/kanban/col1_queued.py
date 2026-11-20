"""
KanbanQueuedColumnMixin: Column 1 queued and parsing links manager for Kanban pipeline.
"""
from __future__ import annotations
from typing import Any, Dict

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.ui.panels.kanban_cards import create_empty_state


class KanbanQueuedColumnMixin:
    """Manages Column 1 layout and dynamic updates for active parsing links and queued tasks."""

    def _build_col1_queued(self, parent: Any):
        col_frame = tk.Frame(parent, bg="#0b0e14", padx=4, pady=2)
        col_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Header
        hdr = tk.Frame(col_frame, bg="#0b0e14")
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.lbl_col1_title = tk.Label(
            hdr,
            text=f"{tr('pipeline_col_queued', 'Queued & Parsing')} (0)",
            font=("Segoe UI", 10, "bold"),
            bg="#0b0e14",
            fg="#94a3b8"
        )
        self.lbl_col1_title.pack(side=tk.LEFT)

        # Cards Container
        self.cards_col1_container = tk.Frame(col_frame, bg="#0b0e14")
        self.cards_col1_container.pack(fill=tk.BOTH, expand=True)

    def refresh_kanban_col1(self):
        """Dynamically re-renders Column 1 based on real parsing tasks, staged links, and download queue."""
        if not hasattr(self, "cards_col1_container") or not self.cards_col1_container.winfo_exists():
            return

        for child in self.cards_col1_container.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        parsing = getattr(self, "_parsing_links", [])
        staged = getattr(self, "_staged_links", [])
        queued = getattr(self, "_download_queue", [])
        total = len(parsing) + len(staged) + len(queued)

        if hasattr(self, "lbl_col1_title") and self.lbl_col1_title.winfo_exists():
            self.lbl_col1_title.configure(text=f"{tr('pipeline_col_queued', 'Queued & Parsing')} ({total})")

        if total == 0:
            create_empty_state(
                self.cards_col1_container,
                icon="⏳",
                title=tr("pipeline_empty_queued", "No queued links"),
                subtitle=tr("status_ready", "Ready"),
                height=140
            )
            return

        from faqih_downloader.ui.panels.kanban_staged_helpers import render_kanban_col1_content
        render_kanban_col1_content(self.cards_col1_container, self, parsing, staged, queued)

    def stage_probed_link_in_col1(self, info_dict: Dict[str, Any]):
        """Adds or updates a probed download link card in Column 1."""
        def _do():
            if not hasattr(self, "_staged_links"):
                self._staged_links = []
            u = info_dict.get("url")
            self._staged_links = [it for it in self._staged_links if it.get("url") != u]
            self._staged_links.insert(0, info_dict)
            self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        elif hasattr(self, "after"):
            self.after(0, _do)
        else:
            _do()

    def remove_staged_link(self, url: str):
        """Removes a staged download link card from Column 1."""
        def _do():
            if hasattr(self, "_staged_links"):
                self._staged_links = [it for it in self._staged_links if it.get("url") != url]
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        elif hasattr(self, "after"):
            self.after(0, _do)
        else:
            _do()

    def add_parsing_link(self, url: str):
        """Notifies Column 1 that a link metadata extraction has commenced."""
        def _do():
            if not hasattr(self, "_parsing_links"):
                self._parsing_links = []
            if url and url not in self._parsing_links:
                self._parsing_links.append(url)
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        else:
            _do()

    def remove_parsing_link(self, url: str):
        """Removes a link from the active parsing indicator list."""
        def _do():
            if hasattr(self, "_parsing_links") and url in self._parsing_links:
                self._parsing_links.remove(url)
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        else:
            _do()
