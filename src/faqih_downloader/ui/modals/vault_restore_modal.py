"""
Backward-compatibility shim for vault_restore_modal.
Logic has moved to faqih_downloader.ui.modals.vault_restore.
"""
from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files
from .vault_restore import (
    VaultRestoreModal,
    _format_size,
    VaultRestoreScrollMixin,
    VaultRestoreSelectionMixin,
    VaultRestoreRowsMixin,
    VaultRestoreActionsMixin,
)

__all__ = [
    "VaultRestoreModal",
    "scan_unregistered_disk_files",
    "_format_size",
    "VaultRestoreScrollMixin",
    "VaultRestoreSelectionMixin",
    "VaultRestoreRowsMixin",
    "VaultRestoreActionsMixin",
]
