"""
Backward-compatibility shim for core_patch_updater.
All OTA core hot-patch logic now lives in faqih_downloader.services.updates.
"""
from .updates.constants import (
    APP_NAME,
    APP_ID,
    APP_VERSION,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
)
from .updates.paths_and_ssl import (
    get_app_data_dir,
    get_core_plugin_dir,
    _get_verified_ssl_context,
    _is_trusted_update_url,
)
from .updates.versioning import parse_version, is_newer_version, is_version_ge
from .updates.core_packager import build_core_patch_zip
from .updates.core_loader import (
    _ExternalCoreFinder,
    _purge_and_reimport_core,
    init_core_loader,
)
from .updates.core_hotpatch import CoreHotPatchUpdater

__all__ = [
    "get_core_plugin_dir",
    "is_version_ge",
    "build_core_patch_zip",
    "_ExternalCoreFinder",
    "_purge_and_reimport_core",
    "CoreHotPatchUpdater",
    "init_core_loader",
]
