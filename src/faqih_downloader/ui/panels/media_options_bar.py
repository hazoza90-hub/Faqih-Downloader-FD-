"""
Backward-compatibility shim for media_options_bar.
Re-exports MediaOptionsBarMixin, MediaOptionsActionsMixin, and modal helpers.
"""
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

from ...config import get_setting, set_setting, get_base_downloads_dir, parse_safe_int
from ..modals.quality_modal import QualitySelectionModal
from ..modals.confirm_modal import DownloadConfirmationModal
from .media_bar import (
    MediaOptionsBarMixin,
    MediaOptionsActionsMixin,
    MediaBarLayoutMixin,
    MediaBarStateSyncMixin,
    MediaBarEventHandlersMixin,
)

__all__ = [
    "MediaOptionsBarMixin",
    "MediaOptionsActionsMixin",
    "MediaBarLayoutMixin",
    "MediaBarStateSyncMixin",
    "MediaBarEventHandlersMixin",
    "QualitySelectionModal",
    "DownloadConfirmationModal",
    "get_setting",
    "set_setting",
    "tk",
    "ttk",
]
