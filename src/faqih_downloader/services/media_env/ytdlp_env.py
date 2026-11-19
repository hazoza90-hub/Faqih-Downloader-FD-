"""
ytdlp_env.py: yt-dlp runtime availability checking, version inspection, and plugin update trigger.
"""
import sys
import shutil
from typing import Dict, Optional, Callable, Any

try:
    from ..updater_service import YtDlpAutoUpdater
except ImportError:
    try:
        from faqih_downloader.services.updater_service import YtDlpAutoUpdater
    except ImportError:
        from updater import YtDlpAutoUpdater


def is_ytdlp_available() -> bool:
    """Checks whether the yt-dlp python package or CLI binary is available."""
    ym = sys.modules.get("faqih_downloader.services.youtube_models")
    which_fn = getattr(getattr(ym, "shutil", None), "which", shutil.which) if ym else shutil.which
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return which_fn("yt-dlp") is not None


def get_ytdlp_version() -> str:
    """Returns the currently active yt-dlp version string."""
    return YtDlpAutoUpdater().get_current_version()


def update_ytdlp_engine(
    force: bool = False,
    on_log: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Checks for and applies the latest yt-dlp extractor update into %APPDATA%\\SmartDownload\\yt_dlp_plugin."""
    return YtDlpAutoUpdater(on_log=on_log).update(force=force)


__all__ = [
    "is_ytdlp_available",
    "get_ytdlp_version",
    "update_ytdlp_engine",
]
