"""
Updates package: Application auto-updater, yt-dlp dynamic plugin updater, and core hot-patch engine.
"""
from .constants import (
    APP_NAME,
    APP_ID,
    APP_VERSION,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
    GITHUB_LATEST_RELEASE_API,
    YTDLP_PYPI_JSON_API,
    YTDLP_GITHUB_LATEST_API,
    YTDLP_GITHUB_RELEASES_API,
)
from .paths_and_ssl import (
    get_app_data_dir,
    get_ytdlp_plugin_dir,
    get_core_plugin_dir,
    _is_trusted_update_url,
    _get_ssl_context,
    _get_verified_ssl_context,
)
from .versioning import (
    parse_version,
    _compare_prerelease,
    is_newer_version,
    is_version_ge,
)
from .app_updater import AppAutoUpdater
from .ytdlp_finder import _ExternalYtDlpFinder
from .ytdlp_activation import YtDlpPluginActivationMixin
from .ytdlp_downloader import YtDlpArchiveUpdaterMixin
from .ytdlp_manager import YtDlpAutoUpdater
from .core_packager import build_core_patch_zip
from .core_loader import _ExternalCoreFinder, _purge_and_reimport_core, init_core_loader
from .core_hotpatch import CoreHotPatchUpdater

__all__ = [
    "APP_NAME",
    "APP_ID",
    "APP_VERSION",
    "GITHUB_REPO_OWNER",
    "GITHUB_REPO_NAME",
    "GITHUB_LATEST_RELEASE_API",
    "YTDLP_PYPI_JSON_API",
    "YTDLP_GITHUB_LATEST_API",
    "YTDLP_GITHUB_RELEASES_API",
    "get_app_data_dir",
    "get_ytdlp_plugin_dir",
    "get_core_plugin_dir",
    "_is_trusted_update_url",
    "_get_ssl_context",
    "_get_verified_ssl_context",
    "parse_version",
    "_compare_prerelease",
    "is_newer_version",
    "is_version_ge",
    "AppAutoUpdater",
    "_ExternalYtDlpFinder",
    "YtDlpPluginActivationMixin",
    "YtDlpArchiveUpdaterMixin",
    "YtDlpAutoUpdater",
    "build_core_patch_zip",
    "_ExternalCoreFinder",
    "_purge_and_reimport_core",
    "init_core_loader",
    "CoreHotPatchUpdater",
]
