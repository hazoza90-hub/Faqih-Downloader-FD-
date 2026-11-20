"""
KanbanVaultColumnMixin: Column 3 Completed Vault workspace for Kanban pipeline.
"""
from __future__ import annotations
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.ui.panels.kanban_cards import create_empty_state, build_vault_card
from faqih_downloader.ui.panels.kanban_vault_helpers import (
    build_vault_filter_pills,
    build_load_more_button,
    setup_vault_scroll_view,
    render_vault_view,
)


class KanbanVaultColumnMixin:
    """Manages Column 3 layout, filter pills, completed downloads rendering, and completion notifications."""

    def _build_col3_vault(self, parent: Any):
        col_frame = tk.Frame(parent, bg="#0b0e14", padx=4, pady=2)
        col_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.col3_frame = col_frame

        # Header: "Completed Vault (N)" + Clear Button
        hdr = tk.Frame(col_frame, bg="#0b0e14")
        hdr.pack(fill=tk.X, pady=(0, 4))
        self.lbl_col3_title = tk.Label(
            hdr,
            text=f"{tr('pipeline_col_vault', 'Completed Vault')} (0)",
            font=("Segoe UI", 10, "bold"),
            bg="#0b0e14",
            fg="#94a3b8"
        )
        self.lbl_col3_title.pack(side=tk.LEFT)

        self.btn_clear_vault = tk.Label(
            hdr, text=tr("vault_btn_clear", "✕ Clear"), font=("Segoe UI", 8, "bold"),
            bg="#0b0e14", fg="#64748b", cursor="hand2"
        )
        self.btn_clear_vault.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_clear_vault.bind("<Enter>", lambda e: self.btn_clear_vault.configure(fg="#ef4444"))
        self.btn_clear_vault.bind("<Leave>", lambda e: self.btn_clear_vault.configure(fg="#64748b"))
        self.btn_clear_vault.bind("<Button-1>", lambda e: self._on_clear_completed_vault())

        self.btn_restore_vault = tk.Label(
            hdr, text=tr("vault_btn_restore", "↻ Restore"), font=("Segoe UI", 8, "bold"),
            bg="#0b0e14", fg="#64748b", cursor="hand2"
        )
        self.btn_restore_vault.pack(side=tk.RIGHT, padx=(0, 6))
        self.btn_restore_vault.bind("<Enter>", lambda e: self.btn_restore_vault.configure(fg="#38bdf8"))
        self.btn_restore_vault.bind("<Leave>", lambda e: self.btn_restore_vault.configure(fg="#64748b"))
        self.btn_restore_vault.bind("<Button-1>", lambda e: self._on_restore_vault_from_disk())

        # Category Filter Pills Container
        self.vault_pills_container = tk.Frame(col_frame, bg="#0b0e14")
        self.vault_pills_container.pack(fill=tk.X, pady=(0, 4))

        # Scrollable container setup
        body = tk.Frame(col_frame, bg="#0b0e14")
        body.pack(fill=tk.BOTH, expand=True)
        cv, container = setup_vault_scroll_view(col_frame, body, panel=self)
        self.vault_cards_canvas = cv
        self.vault_cards_container = container

    def refresh_kanban_col3(self):
        """Dynamically populates Column 3 with real completed downloads from DownloadHistoryManager."""
        if not hasattr(self, "vault_cards_container") or not self.vault_cards_container.winfo_exists():
            return

        if hasattr(self, "btn_clear_vault") and self.btn_clear_vault.winfo_exists():
            self.btn_clear_vault.configure(text=tr("vault_btn_clear", "✕ Clear"))
        if hasattr(self, "btn_restore_vault") and self.btn_restore_vault.winfo_exists():
            self.btn_restore_vault.configure(text=tr("vault_btn_restore", "↻ Restore"))

        if hasattr(self, "vault_pills_container") and self.vault_pills_container.winfo_exists():
            for c in self.vault_pills_container.winfo_children():
                try: c.destroy()
                except Exception: pass
            pills = build_vault_filter_pills(
                self.vault_pills_container,
                getattr(self, "_vault_filter_category", "all"),
                self._on_vault_category_select
            )
            pills.pack(fill=tk.X)

        entries = []
        if hasattr(self, "history_manager") and self.history_manager:
            entries = [
                e for e in self.history_manager.get_entries()
                if str(e.get("status", "")).strip().lower() in ("completed", "مكتمل", "success")
            ]

        def _empty(cont):
            create_empty_state(cont, icon="📁", title=tr("pipeline_empty_vault", "No completed downloads yet"), subtitle="", height=140)

        callbacks = {
            "open_file": self._open_vault_file,
            "open_folder": self._open_vault_folder,
            "delete_entry": self._on_delete_vault_entry,
            "context_menu": self._on_vault_context_menu,
            "load_more": self._on_vault_load_more,
        }

        curr_cat = getattr(self, "_vault_filter_category", "all")
        limit = getattr(self, "_vault_display_limit", 25)
        total = render_vault_view(
            self.vault_cards_container, entries, curr_cat, limit, callbacks,
            card_builder=build_vault_card, empty_builder=_empty, load_more_builder=build_load_more_button
        )
        if hasattr(self, "lbl_col3_title") and self.lbl_col3_title.winfo_exists():
            self.lbl_col3_title.configure(text=f"{tr('pipeline_col_vault', 'Completed Vault')} ({total})")

    def _on_vault_category_select(self, cat: str):
        self._vault_filter_category, self._vault_display_limit = cat, 25
        self.refresh_kanban_col3()

    def _on_vault_load_more(self):
        self._vault_display_limit = getattr(self, "_vault_display_limit", 25) + 25
        self.refresh_kanban_col3()

    def on_kanban_download_completed(self, path: str, total_bytes: int):
        """Adds dynamically completed download to Completed Vault and resets active stream."""
        self.reset_kanban_active_stream()
        self.refresh_kanban_col3()
