"""
YtDlpPluginActivationMixin: validation, version inspection, activation, and rollback
for the external yt_dlp plugin package.
"""
import os
import re
import sys
import json
import importlib
from typing import Optional

from .versioning import is_newer_version
from .ytdlp_finder import _ExternalYtDlpFinder


class YtDlpPluginActivationMixin:
    """Mixin managing validation and runtime activation/deactivation of external yt_dlp."""

    @staticmethod
    def _reset_extractor_caches() -> None:
        for mod_name in (
            "youtube_resolver",
            "faqih_downloader.services.youtube.url_matcher",
            "faqih_downloader.services.youtube_models",
        ):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                try:
                    setattr(mod, "_YTDLP_EXTRACTORS_CACHE", None)
                    setattr(mod, "_CACHED_YTDLP_EXTRACTORS", None)
                except Exception:
                    pass

    def is_plugin_valid(self, directory: Optional[str] = None) -> bool:
        """Checks whether the given directory contains a valid yt_dlp Python package."""
        target = os.path.abspath(directory or self.plugin_dir)
        pkg_dir = os.path.join(target, "yt_dlp")
        init_py = os.path.join(pkg_dir, "__init__.py")
        ver_py = os.path.join(pkg_dir, "version.py")
        extractor_py = os.path.join(pkg_dir, "extractor", "__init__.py")
        return os.path.isfile(init_py) and os.path.isfile(ver_py) and os.path.isfile(extractor_py)

    def get_plugin_version(self, directory: Optional[str] = None) -> Optional[str]:
        """Reads the yt-dlp version string from the external plugin directory without importing it."""
        target = os.path.abspath(directory or self.plugin_dir)
        ver_py = os.path.join(target, "yt_dlp", "version.py")
        if os.path.isfile(ver_py):
            try:
                with open(ver_py, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
                if m:
                    return m.group(1).strip()
            except Exception:
                pass
        meta_file = os.path.join(target, "plugin_meta.json")
        if os.path.isfile(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                v = data.get("version")
                if v and isinstance(v, str):
                    return v.strip()
            except Exception:
                pass
        return None

    def get_current_version(self) -> str:
        """Returns the currently active yt-dlp version (from external plugin or bundled package)."""
        if self.is_plugin_valid():
            norm_plugin = os.path.normcase(self.plugin_dir)
            if any(os.path.normcase(os.path.abspath(p)) == norm_plugin for p in sys.path if p):
                p_ver = self.get_plugin_version()
                if p_ver:
                    return p_ver
        try:
            import yt_dlp
            return str(getattr(yt_dlp.version, "__version__", "0.0.0"))
        except Exception:
            p_ver = self.get_plugin_version()
            return p_ver if p_ver else "0.0.0"

    def activate_plugin(self, force: bool = False) -> bool:
        """
        Prepends self.plugin_dir to sys.path[0] and registers _ExternalYtDlpFinder on sys.meta_path[0],
        then reloads yt_dlp in-process. If loading fails, cleanly rolls back to bundled yt_dlp.
        """
        with self._lock:
            if not self.is_plugin_valid():
                return False

            plugin_ver = self.get_plugin_version()
            if not force and plugin_ver:
                # Check if currently loaded/bundled yt_dlp is strictly newer than the plugin on disk
                try:
                    import yt_dlp
                    cur_ver = str(getattr(yt_dlp.version, "__version__", ""))
                    if cur_ver and is_newer_version(cur_ver, plugin_ver):
                        self.log(f"[YTDLP] Bundled yt-dlp ({cur_ver}) is newer than plugin ({plugin_ver}); keeping bundled.")
                        return False
                except Exception:
                    pass

            norm_plugin = os.path.normcase(self.plugin_dir)
            # Clean existing occurrences in sys.path and insert at index 0
            sys.path[:] = [
                p for p in sys.path
                if not (p and os.path.normcase(os.path.abspath(p)) == norm_plugin)
            ]
            sys.path.insert(0, self.plugin_dir)

            # Register or update _ExternalYtDlpFinder at sys.meta_path[0]
            sys.meta_path[:] = [
                finder for finder in sys.meta_path
                if not isinstance(finder, _ExternalYtDlpFinder)
            ]
            sys.meta_path.insert(0, _ExternalYtDlpFinder(self.plugin_dir))

            # Evict cached yt_dlp modules so Python imports the updated package
            to_delete = [k for k in list(sys.modules.keys()) if k == "yt_dlp" or k.startswith("yt_dlp.")]
            saved_modules = {k: sys.modules.pop(k) for k in to_delete}

            self._reset_extractor_caches()

            try:
                mod = importlib.import_module("yt_dlp")
                importlib.import_module("yt_dlp.version")
                importlib.import_module("yt_dlp.extractor")
                loaded_file = os.path.normcase(os.path.abspath(getattr(mod, "__file__", "") or ""))
                if not loaded_file.startswith(norm_plugin):
                    raise RuntimeError(f"Loaded yt_dlp from {loaded_file} instead of plugin {self.plugin_dir}")
                return True
            except Exception as e:
                self.log(f"[YTDLP] Failed to activate external yt-dlp plugin ({e}); falling back to bundled yt-dlp.")
                # Remove broken plugin from sys.path and sys.meta_path
                sys.path[:] = [
                    p for p in sys.path
                    if not (p and os.path.normcase(os.path.abspath(p)) == norm_plugin)
                ]
                sys.meta_path[:] = [
                    finder for finder in sys.meta_path
                    if not isinstance(finder, _ExternalYtDlpFinder)
                ]
                for k in [m for m in list(sys.modules.keys()) if m == "yt_dlp" or m.startswith("yt_dlp.")]:
                    sys.modules.pop(k, None)
                sys.modules.update(saved_modules)
                return False

    def deactivate_plugin(self) -> None:
        """Removes external plugin hooks and restores bundled yt_dlp."""
        with self._lock:
            norm_plugin = os.path.normcase(self.plugin_dir)
            sys.path[:] = [
                p for p in sys.path
                if not (p and os.path.normcase(os.path.abspath(p)) == norm_plugin)
            ]
            sys.meta_path[:] = [
                finder for finder in sys.meta_path
                if not isinstance(finder, _ExternalYtDlpFinder)
            ]
            for k in [m for m in list(sys.modules.keys()) if m == "yt_dlp" or m.startswith("yt_dlp.")]:
                sys.modules.pop(k, None)
            self._reset_extractor_caches()
