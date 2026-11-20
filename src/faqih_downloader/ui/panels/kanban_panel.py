"""
Backward-compatibility shim for kanban_panel.
Logic has moved to faqih_downloader.ui.panels.kanban.
"""
from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin
from .kanban import (
    KanbanPanelMixin,
    KanbanQueuedColumnMixin,
    KanbanVaultColumnMixin,
    KanbanVaultActionsMixin,
    KanbanVaultScrollMixin,
)

__all__ = [
    "KanbanPanelMixin",
    "KanbanActiveColumnMixin",
    "KanbanQueuedColumnMixin",
    "KanbanVaultColumnMixin",
    "KanbanVaultActionsMixin",
    "KanbanVaultScrollMixin",
]
