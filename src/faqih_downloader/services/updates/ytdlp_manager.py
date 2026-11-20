"""
YtDlpAutoUpdater: orchestrator class composing plugin activation and archive updates.
"""
import os
import sys
import threading
from typing import Optional, Callable

from .paths_and_ssl import get_ytdlp_plugin_dir
from .ytdlp_activation import YtDlpPluginActivationMixin
from .ytdlp_downloader import YtDlpArchiveUpdaterMixin


def _resolve_get_ytdlp_plugin_dir():
    for mod_name in (
        "faqih_downloader.services.ytdlp_updater",
        "faqih_downloader.services.updater_service",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "get_ytdlp_plugin_dir"):
            fn = getattr(mod, "get_ytdlp_plugin_dir")
            if fn is not get_ytdlp_plugin_dir:
                return fn
    return get_ytdlp_plugin_dir


class YtDlpAutoUpdater(YtDlpPluginActivationMixin, YtDlpArchiveUpdaterMixin):
    """
    Manages checking, downloading, atomically extracting, and dynamically activating
    the latest yt-dlp Python package inside %APPDATA%\\SmartDownload\\yt_dlp_plugin.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        plugin_dir: Optional[str] = None,
        on_log: Optional[Callable[[str], None]] = None,
        timeout: int = 15
    ):
        resolved_dir = plugin_dir or _resolve_get_ytdlp_plugin_dir()()
        self.plugin_dir = os.path.abspath(resolved_dir)
        self.on_log = on_log
        self.timeout = max(3, int(timeout))

    def log(self, message: str):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass
