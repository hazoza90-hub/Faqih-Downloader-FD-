"""
Backward-compatibility shim for ytdlp_updater.
All yt-dlp dynamic plugin update logic now lives in faqih_downloader.services.updates.
"""
from .updates.constants import (
    APP_NAME,
    APP_ID,
    APP_VERSION,
    YTDLP_PYPI_JSON_API,
    YTDLP_GITHUB_LATEST_API,
)
from .updates.paths_and_ssl import (
    get_app_data_dir,
    get_ytdlp_plugin_dir,
    _get_ssl_context,
    _get_verified_ssl_context,
    _is_trusted_update_url,
)
from .updates.versioning import parse_version, is_newer_version
from .updates.ytdlp_finder import _ExternalYtDlpFinder
from .updates.ytdlp_manager import YtDlpAutoUpdater

__all__ = [
    "APP_NAME",
    "APP_ID",
    "APP_VERSION",
    "YTDLP_PYPI_JSON_API",
    "YTDLP_GITHUB_LATEST_API",
    "get_app_data_dir",
    "get_ytdlp_plugin_dir",
    "_get_ssl_context",
    "_get_verified_ssl_context",
    "_is_trusted_update_url",
    "parse_version",
    "is_newer_version",
    "_ExternalYtDlpFinder",
    "YtDlpAutoUpdater",
]
