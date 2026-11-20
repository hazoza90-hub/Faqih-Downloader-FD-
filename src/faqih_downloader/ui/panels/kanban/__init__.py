"""
kanban package for Faqih Downloader (FD).
Provides 3-column Kanban pipeline workspace and components.
"""
from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin
from .col1_queued import KanbanQueuedColumnMixin
from .col3_vault import KanbanVaultColumnMixin
from .vault_actions import KanbanVaultActionsMixin
from .vault_scroll import KanbanVaultScrollMixin
from .panel import KanbanPanelMixin

__all__ = [
    "KanbanActiveColumnMixin",
    "KanbanQueuedColumnMixin",
    "KanbanVaultColumnMixin",
    "KanbanVaultActionsMixin",
    "KanbanVaultScrollMixin",
    "KanbanPanelMixin",
]
