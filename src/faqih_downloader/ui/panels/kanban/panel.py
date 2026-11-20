"""
KanbanPanelMixin: 3-Column dynamic pipeline workspace for Faqih Downloader (FD).
"""
from __future__ import annotations
from typing import Any, List, Dict

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin
from .col1_queued import KanbanQueuedColumnMixin
from .col3_vault import KanbanVaultColumnMixin
from .vault_actions import KanbanVaultActionsMixin
from .vault_scroll import KanbanVaultScrollMixin


class KanbanPanelMixin(
    KanbanActiveColumnMixin,
    KanbanQueuedColumnMixin,
    KanbanVaultColumnMixin,
    KanbanVaultActionsMixin,
    KanbanVaultScrollMixin
):
    """Provides the 3-column Kanban pipeline workspace and 100% dynamic card management."""

    def _build_kanban_pipeline(self, parent: Any):
        """Constructs the 3-column layout."""
        self.kanban_container = tk.Frame(parent, bg="#0b0e14", padx=10, pady=8)
        self.kanban_container.pack(fill=tk.BOTH, expand=True)

        # 3 Columns grid configuration
        self.kanban_container.columnconfigure(0, weight=30, uniform="col")
        self.kanban_container.columnconfigure(1, weight=40, uniform="col")
        self.kanban_container.columnconfigure(2, weight=30, uniform="col")
        self.kanban_container.rowconfigure(0, weight=1)

        # Internal tracking
        self._parsing_links: List[str] = getattr(self, "_parsing_links", [])
        self._staged_links: List[Dict[str, Any]] = getattr(self, "_staged_links", [])
        self._active_stream_live = False
        self._vault_scroll_steps = 0
        self._vault_scroll_timer = None

        # ── Column 1: Queued & Parsing ───────────────────────────────────────
        self._build_col1_queued(self.kanban_container)

        # ── Column 2: Active Turbo Streams ───────────────────────────────────
        self._build_col2_active(self.kanban_container)

        # ── Column 3: Completed Vault ────────────────────────────────────────
        self._build_col3_vault(self.kanban_container)

        # Initial dynamic population
        self.refresh_kanban_col1()
        self.reset_kanban_active_stream()
        self.refresh_kanban_col3()
