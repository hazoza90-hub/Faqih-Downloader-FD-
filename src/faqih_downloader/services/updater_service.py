"""
Backward-compatibility shim for updater_service.
All auto-update logic has been decomposed into faqih_downloader.services.updates.
"""
from .updates.constants import (
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
from .updates.paths_and_ssl import (
    get_app_data_dir,
    get_ytdlp_plugin_dir,
    get_core_plugin_dir,
    _is_trusted_update_url,
    _get_ssl_context,
    _get_verified_ssl_context,
)
from .updates.versioning import (
    parse_version,
    _compare_prerelease,
    is_newer_version,
    is_version_ge,
)
from .updates.app_updater import AppAutoUpdater
from .ytdlp_updater import _ExternalYtDlpFinder, YtDlpAutoUpdater
from .core_patch_updater import (
    build_core_patch_zip,
    CoreHotPatchUpdater,
    _ExternalCoreFinder,
    _purge_and_reimport_core,
    init_core_loader,
)

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
    "_is_trusted_update_url",
    "_get_ssl_context",
    "_get_verified_ssl_context",
    "parse_version",
    "is_newer_version",
    "is_version_ge",
    "YtDlpAutoUpdater",
    "_ExternalYtDlpFinder",
    "AppAutoUpdater",
    "build_core_patch_zip",
    "CoreHotPatchUpdater",
    "_ExternalCoreFinder",
    "get_core_plugin_dir",
    "init_core_loader",
]
