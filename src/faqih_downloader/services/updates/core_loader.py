"""
Dynamic Core Loader & Import Hook (_ExternalCoreFinder, _purge_and_reimport_core, init_core_loader).
"""
import os
import sys
import importlib
import importlib.abc
import importlib.machinery
from typing import List, Optional

from .constants import APP_VERSION
from .paths_and_ssl import get_core_plugin_dir
from .versioning import is_newer_version, is_version_ge


class _ExternalCoreFinder(importlib.abc.MetaPathFinder):
    """
    MetaPathFinder placed at sys.meta_path[0] to ensure an updated external faqih_downloader
    package in %APPDATA%\\SmartDownload\\core_plugin or local dev src takes precedence
    over PyInstaller's PyiFrozenImporter when frozen as a standalone .exe.
    """
    def __init__(self, core_root: str):
        self.core_root = os.path.abspath(core_root)

    def find_spec(self, fullname: str, path=None, target=None):
        if not (fullname in ("faqih_downloader", "smart_download") or fullname.startswith(("faqih_downloader.", "smart_download."))):
            return None
        pkg_root = os.path.join(self.core_root, "faqih_downloader")
        if not os.path.isfile(os.path.join(pkg_root, "__init__.py")):
            pkg_root = os.path.join(self.core_root, "smart_download")
            if not os.path.isfile(os.path.join(pkg_root, "__init__.py")):
                return None
        try:
            parts = fullname.split(".")
            parent_dir = os.path.join(self.core_root, *parts[:-1])
            if os.path.isdir(parent_dir):
                spec = importlib.machinery.PathFinder.find_spec(fullname, [parent_dir], target)
                if spec is not None:
                    return spec
            if path is not None:
                return importlib.machinery.PathFinder.find_spec(fullname, path, target)
        except Exception:
            return None
        return None


def _purge_and_reimport_core(core_root: str) -> bool:
    """
    Installs _ExternalCoreFinder and sys.path[0], purges cached core modules
    from sys.modules, and re-imports faqih_downloader to verify successful dynamic loading.
    """
    norm_root = os.path.normcase(os.path.abspath(core_root))
    sys.path[:] = [
        p for p in sys.path
        if not (p and os.path.normcase(os.path.abspath(p)) == norm_root)
    ]
    sys.path.insert(0, core_root)

    sys.meta_path[:] = [
        f for f in sys.meta_path
        if not isinstance(f, _ExternalCoreFinder)
    ]
    sys.meta_path.insert(0, _ExternalCoreFinder(core_root))

    to_delete = [
        k for k in list(sys.modules.keys())
        if k in ("faqih_downloader", "smart_download")
        or k.startswith(("faqih_downloader.", "smart_download."))
    ]
    saved_modules = {k: sys.modules.pop(k) for k in to_delete}

    try:
        mod = None
        for pkg_name in ("faqih_downloader", "smart_download"):
            try:
                mod = importlib.import_module(pkg_name)
                importlib.import_module(f"{pkg_name}.config")
                break
            except Exception:
                continue
        if mod is None:
            raise ImportError("Could not import faqih_downloader or smart_download")
        loaded_file = os.path.normcase(os.path.abspath(getattr(mod, "__file__", "") or ""))
        norm_pkg = os.path.normcase(os.path.abspath(os.path.join(core_root, "faqih_downloader")))
        if not os.path.isdir(norm_pkg):
            norm_pkg = os.path.normcase(os.path.abspath(os.path.join(core_root, "smart_download")))
        if not loaded_file.startswith(norm_pkg):
            raise RuntimeError(f"Loaded core from {loaded_file} instead of {norm_pkg}")
        return True
    except Exception:
        sys.path[:] = [
            p for p in sys.path
            if not (p and os.path.normcase(os.path.abspath(p)) == norm_root)
        ]
        sys.meta_path[:] = [
            f for f in sys.meta_path
            if not isinstance(f, _ExternalCoreFinder)
        ]
        for k in [m for m in list(sys.modules.keys()) if m in ("faqih_downloader", "smart_download") or m.startswith(("faqih_downloader.", "smart_download."))]:
            sys.modules.pop(k, None)
        sys.modules.update(saved_modules)
        return False


def init_core_loader(force: bool = False) -> Optional[str]:
    """
    Checks external core override locations before falling back to bundled PYZ:
    1) Local Dev / Source Mode Override (SD_DEV_SRC env or adjacent dev folder)
    2) OTA Hot-Patch Plugin Directory (%APPDATA%\\SmartDownload\\core_plugin)
    Returns 'dev', 'plugin', or None.
    """
    # 1. Local Dev / Source Mode Override
    dev_src = os.environ.get("SD_DEV_SRC")
    candidate_dev_roots: List[str] = []
    if dev_src and os.path.isdir(dev_src):
        candidate_dev_roots.append(dev_src)
        candidate_dev_roots.append(os.path.dirname(dev_src))

    if getattr(sys, "frozen", False) or force:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidate_dev_roots.extend([
            os.path.abspath(os.path.join(exe_dir, "..", "src")),
            os.path.join(exe_dir, "src"), exe_dir,
            os.path.abspath(os.path.join(exe_dir, "..", "..", "src")),
        ])

    for root_cand in candidate_dev_roots:
        if not root_cand or not os.path.isdir(root_cand):
            continue
        for pkg_name in ("faqih_downloader", "smart_download"):
            pkg_cand = os.path.join(root_cand, pkg_name)
            if os.path.isfile(os.path.join(pkg_cand, "__init__.py")):
                if _purge_and_reimport_core(root_cand):
                    return "dev"

    # 2. OTA Hot-Patch Plugin Directory (only for frozen executable or forced runs)
    if getattr(sys, "frozen", False) or force:
        legacy_mod = sys.modules.get("faqih_downloader.services.core_patch_updater")
        get_dir_fn = getattr(legacy_mod, "get_core_plugin_dir", get_core_plugin_dir) if legacy_mod else get_core_plugin_dir
        plugin_dir = get_dir_fn()
        from .core_hotpatch import CoreHotPatchUpdater
        updater = CoreHotPatchUpdater(plugin_dir=plugin_dir)
        if updater.is_plugin_valid():
            patch_ver = updater.get_plugin_version()
            if patch_ver and (is_newer_version(patch_ver, APP_VERSION) or (force and is_version_ge(patch_ver, APP_VERSION))):
                if updater.activate_plugin(force=True):
                    return "plugin"

    return None
