"""
Faqih Downloader (FD) — High-Performance Enterprise Modular Download Engine
"""
__version__ = "2.0.2"

import sys
import importlib
import importlib.abc
import importlib.util

# In-memory backwards compatibility alias for legacy 'smart_download' imports & mocks
class _SmartDownloadAliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str):
        self.target_name = target_name

    def create_module(self, spec):
        mod = importlib.import_module(self.target_name)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class _SmartDownloadAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == "smart_download" or fullname.startswith("smart_download."):
            target_name = "faqih_downloader" + fullname[14:]
            try:
                spec = importlib.util.find_spec(target_name)
                if spec is not None:
                    alias_spec = importlib.util.spec_from_loader(
                        fullname,
                        _SmartDownloadAliasLoader(target_name),
                        origin=spec.origin,
                        is_package=spec.submodule_search_locations is not None,
                    )
                    alias_spec.submodule_search_locations = spec.submodule_search_locations
                    return alias_spec
            except Exception:
                pass
        return None


if not any(isinstance(f, _SmartDownloadAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _SmartDownloadAliasFinder())

sys.modules["smart_download"] = sys.modules[__name__]

from .config import (
    APP_NAME,
    APP_TITLE,
    APP_ID,
    APP_VERSION,
    get_resource_path,
    get_config_dir,
    get_app_config_dir,
    get_settings_file_path,
    load_settings,
    save_settings,
    get_setting,
    set_setting,
    get_base_downloads_dir,
)
from .locales.i18n import LocalizationManager, tr, get_current_language, set_current_language
from .core.engine import TurboDownloadEngine
from .core.chunk import DownloadChunk, get_permissive_ssl_context
def __getattr__(name: str):
    if name in ("ModernFramelessGUI", "main"):
        try:
            import tkinter as tk
            if tk is None:
                raise ImportError("Tkinter not available")
            from .ui.main_window import ModernFramelessGUI as _ModernFramelessGUI, main as _main
            globals()["ModernFramelessGUI"] = _ModernFramelessGUI
            globals()["main"] = _main
            return globals()[name]
        except Exception:
            globals()["ModernFramelessGUI"] = None
            globals()["main"] = None
            return None
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals().keys()) | {"ModernFramelessGUI", "main"})

__all__ = [
    "__version__",
    "APP_NAME",
    "APP_TITLE",
    "APP_ID",
    "APP_VERSION",
    "get_resource_path",
    "get_config_dir",
    "get_app_config_dir",
    "get_settings_file_path",
    "load_settings",
    "save_settings",
    "get_setting",
    "set_setting",
    "get_base_downloads_dir",
    "LocalizationManager",
    "tr",
    "get_current_language",
    "set_current_language",
    "TurboDownloadEngine",
    "DownloadChunk",
    "get_permissive_ssl_context",
    "ModernFramelessGUI",
    "main",
]
