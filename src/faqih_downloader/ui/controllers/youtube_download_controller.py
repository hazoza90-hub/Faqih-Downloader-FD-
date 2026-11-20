"""
Backward-compatibility shim for youtube_download_controller.
Re-exports YouTubeDownloadControllerMixin, StreamDownloadCoordinator, and QualitySelectionModal.
"""
import os
import threading
from typing import Dict, Any, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ...core.stream_coordinator import StreamDownloadCoordinator
from ..modals.quality_modal import QualitySelectionModal
from ..modals.confirm_modal import DownloadConfirmationModal
from .youtube_dl import (
    YouTubeDownloadControllerMixin,
    YouTubeExtractionFlowMixin,
    YouTubeStreamLauncherMixin,
)

__all__ = [
    "YouTubeDownloadControllerMixin",
    "YouTubeExtractionFlowMixin",
    "YouTubeStreamLauncherMixin",
    "StreamDownloadCoordinator",
    "QualitySelectionModal",
    "DownloadConfirmationModal",
    "threading",
    "tk",
]
