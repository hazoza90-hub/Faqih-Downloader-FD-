"""
Consolidated compatibility and legacy re-export surface for Faqih Downloader GUI.
"""
from ...core.engine import TurboDownloadEngine
from ...config import DEFAULT_SNIFFER_PLATFORMS

SmartDownloadEngine = TurboDownloadEngine

__all__ = [
    "SmartDownloadEngine",
    "DEFAULT_SNIFFER_PLATFORMS",
]
