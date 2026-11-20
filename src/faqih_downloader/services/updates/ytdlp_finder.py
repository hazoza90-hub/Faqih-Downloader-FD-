"""
_ExternalYtDlpFinder: sys.meta_path import hook giving precedence to an updated external yt_dlp plugin.
"""
import os
import importlib.abc
import importlib.machinery


class _ExternalYtDlpFinder(importlib.abc.MetaPathFinder):
    """
    MetaPathFinder placed at sys.meta_path[0] to ensure an updated external yt_dlp
    package in %APPDATA%\\SmartDownload\\yt_dlp_plugin takes precedence over
    PyInstaller's PyiFrozenImporter when frozen as a standalone .exe.
    """

    def __init__(self, plugin_dir: str):
        self.plugin_dir = os.path.abspath(plugin_dir)

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != "yt_dlp" and not fullname.startswith("yt_dlp."):
            return None
        pkg_root = os.path.join(self.plugin_dir, "yt_dlp")
        if not os.path.isfile(os.path.join(pkg_root, "__init__.py")):
            return None
        try:
            if fullname == "yt_dlp":
                return importlib.machinery.PathFinder.find_spec(fullname, [self.plugin_dir], target)
            parts = fullname.split(".")
            parent_dir = os.path.join(self.plugin_dir, *parts[:-1])
            if os.path.isdir(parent_dir):
                return importlib.machinery.PathFinder.find_spec(fullname, [parent_dir], target)
        except Exception:
            return None
        return None
