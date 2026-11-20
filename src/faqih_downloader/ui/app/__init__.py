"""
app package: Main application window GUI, bootstrap launcher, and legacy export bindings.
"""
from .legacy_exports import SmartDownloadEngine, DEFAULT_SNIFFER_PLATFORMS
from .gui import (
    ModernFramelessGUI,
    TurboDownloaderGUI,
    DownloaderApp,
    SmartDownloadGUI,
    SmartDownloadApp,
)
from .bootstrap import main

__all__ = [
    "ModernFramelessGUI",
    "TurboDownloaderGUI",
    "DownloaderApp",
    "SmartDownloadGUI",
    "SmartDownloadApp",
    "SmartDownloadEngine",
    "DEFAULT_SNIFFER_PLATFORMS",
    "main",
]
