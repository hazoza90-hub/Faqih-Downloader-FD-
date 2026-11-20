"""
CoreHotPatchUpdater: OTA Core Patch checker, downloader, atomic applier, and activator.
"""
import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import threading
import urllib.request
from typing import Dict, Optional, Callable, Any

from .constants import APP_VERSION, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
from .paths_and_ssl import (
    get_core_plugin_dir,
    _get_verified_ssl_context,
    _is_trusted_update_url,
)
from .versioning import is_newer_version
from .core_loader import _ExternalCoreFinder, _purge_and_reimport_core
from ...utils.archive_utils import _safe_extract_zip


def _resolve_get_core_plugin_dir():
    legacy_mod = sys.modules.get("faqih_downloader.services.core_patch_updater")
    if legacy_mod is not None and hasattr(legacy_mod, "get_core_plugin_dir"):
        return getattr(legacy_mod, "get_core_plugin_dir")
    return get_core_plugin_dir


class CoreHotPatchUpdater:
    """
    Manages checking, downloading, atomically extracting, and dynamically activating
    the latest smart_download core package in %APPDATA%\\SmartDownload\\core_plugin.
    """
    _lock = threading.RLock()

    def __init__(
        self,
        plugin_dir: Optional[str] = None,
        repo_owner: str = GITHUB_REPO_OWNER,
        repo_name: str = GITHUB_REPO_NAME,
        current_version: Optional[str] = None,
        on_log: Optional[Callable[[str], None]] = None,
        timeout: int = 15
    ):
        resolved_dir = plugin_dir or _resolve_get_core_plugin_dir()()
        self.plugin_dir = os.path.abspath(resolved_dir)
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = str(current_version or APP_VERSION).strip()
        self.on_log = on_log
        self.timeout = max(3, int(timeout))

    def log(self, message: str):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass

    def is_plugin_valid(self, directory: Optional[str] = None) -> bool:
        target = os.path.abspath(directory or self.plugin_dir)
        for pkg in ("faqih_downloader", "smart_download"):
            init_py = os.path.join(target, pkg, "__init__.py")
            config_py = os.path.join(target, pkg, "config.py")
            ver_json1 = os.path.join(target, "core_version.json")
            ver_json2 = os.path.join(target, pkg, "core_version.json")
            if os.path.isfile(init_py) and os.path.isfile(config_py) and (os.path.isfile(ver_json1) or os.path.isfile(ver_json2)):
                return True
        return False

    def get_plugin_version(self, directory: Optional[str] = None) -> Optional[str]:
        target = os.path.abspath(directory or self.plugin_dir)
        for ver_file in (
            os.path.join(target, "core_version.json"),
            os.path.join(target, "faqih_downloader", "core_version.json"),
            os.path.join(target, "smart_download", "core_version.json"),
        ):
            if os.path.isfile(ver_file):
                try:
                    with open(ver_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    v = data.get("version")
                    if v and isinstance(v, str):
                        return v.strip().lstrip("vV")
                except Exception:
                    pass
        return None

    def check_for_core_patch(self) -> Dict[str, Any]:
        """Queries GitHub Releases API for SmartDownload-CorePatch.zip asset."""
        api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SmartDownload-CorePatchUpdater/{self.current_version}"
        }
        ctx = _get_verified_ssl_context()
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not isinstance(data, dict):
                raise RuntimeError("Invalid JSON payload from GitHub Releases API.")

            tag_name = str(data.get("tag_name") or "").strip()
            latest_clean = tag_name.lstrip("vV").strip() or self.current_version
            release_notes = str(data.get("body") or "").strip()

            assets = data.get("assets", [])
            patch_url = ""
            patch_size = 0
            if isinstance(assets, list):
                for asset in assets:
                    if isinstance(asset, dict):
                        a_name = str(asset.get("name") or "")
                        if a_name.lower() in ("faqihdownloader-corepatch.zip", "smartdownload-corepatch.zip"):
                            patch_url = str(asset.get("browser_download_url") or "")
                            patch_size = int(asset.get("size") or 0)
                            break

            newer = is_newer_version(latest_clean, self.current_version) if latest_clean else False
            return {
                "success": True,
                "patch_available": bool(newer and patch_url),
                "current_version": self.current_version,
                "latest_version": latest_clean,
                "tag_name": tag_name,
                "patch_url": patch_url,
                "patch_size": patch_size,
                "release_notes": release_notes,
                "error": None,
            }
        except Exception as e:
            self.log(f"[CORE PATCH] Check failed: {e}")
            return {
                "success": False,
                "patch_available": False,
                "current_version": self.current_version,
                "latest_version": self.current_version,
                "error": str(e)
            }

    def download_core_patch(
        self,
        download_url: str,
        dest_path: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> str:
        if not download_url or not isinstance(download_url, str):
            raise ValueError("A valid download_url is required.")
        if not _is_trusted_update_url(download_url):
            raise ValueError(f"Untrusted update URL: {download_url}")

        if not dest_path:
            dest_path = os.path.join(tempfile.gettempdir(), f"SmartDownload-CorePatch_{os.getpid()}_{threading.get_ident()}.zip")
        dest_path = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        part_path = f"{dest_path}.part_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"

        headers = {"User-Agent": f"SmartDownload-CorePatchUpdater/{self.current_version}"}
        ctx = _get_verified_ssl_context()
        try:
            req = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                total_size = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(part_path, "wb") as out_f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise RuntimeError("Core patch download cancelled by user.")
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            try:
                                progress_cb(downloaded, total_size)
                            except Exception:
                                pass

            if not os.path.isfile(part_path) or os.path.getsize(part_path) == 0:
                raise RuntimeError("Downloaded core patch file is missing or empty.")

            os.replace(part_path, dest_path)
            self.log(f"[CORE PATCH] Downloaded patch to {dest_path} ({os.path.getsize(dest_path):,} bytes).")
            return dest_path
        except Exception:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            raise

    @staticmethod
    def _safe_replace_dir(src: str, dst: str, retries: int = 5, delay: float = 0.06) -> None:
        """
        Replaces directory dst with src, retrying transient Windows PermissionError/OSError
        and falling back to copytree+rmtree if needed.
        """
        last_err: Optional[Exception] = None
        for attempt in range(max(1, retries)):
            try:
                if os.path.exists(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                os.replace(src, dst)
                return
            except OSError as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            shutil.rmtree(src, ignore_errors=True)
            return
        if last_err:
            raise last_err

    def apply_core_patch(
        self,
        zip_path: str,
        target_dir: Optional[str] = None,
        backup: bool = True
    ) -> bool:
        """
        Atomically extracts and validates SmartDownload-CorePatch.zip into target_dir
        with Zip Slip validation and automatic backup rollback if any step fails.
        """
        with self._lock:
            target = os.path.abspath(target_dir or self.plugin_dir)
            if not os.path.isfile(zip_path) or not zipfile.is_zipfile(zip_path):
                raise ValueError(f"Invalid or missing zip archive: {zip_path}")

            parent_dir = os.path.dirname(target)
            os.makedirs(parent_dir, exist_ok=True)
            stage_dir = tempfile.mkdtemp(prefix="sd_core_stage_", dir=parent_dir)
            backup_dir = f"{target}.bak_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    bad_file = zf.testzip()
                    if bad_file is not None:
                        raise ValueError(f"Corrupted file in core patch archive: {bad_file}")
                    _safe_extract_zip(zf, stage_dir)

                if not self.is_plugin_valid(stage_dir):
                    raise ValueError("Core patch archive is missing essential core modules or core_version.json.")

                if os.path.exists(target):
                    self._safe_replace_dir(target, backup_dir)

                try:
                    self._safe_replace_dir(stage_dir, target)
                except Exception:
                    if os.path.exists(backup_dir) and not os.path.exists(target):
                        self._safe_replace_dir(backup_dir, target)
                    raise

                if backup and os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir, ignore_errors=True)

                self.log(f"[CORE PATCH] Successfully applied core patch to {target}.")
                return True
            except Exception as e:
                self.log(f"[CORE PATCH] Failed to apply core patch: {e}")
                if os.path.exists(stage_dir):
                    shutil.rmtree(stage_dir, ignore_errors=True)
                if os.path.exists(backup_dir) and not os.path.exists(target):
                    try:
                        self._safe_replace_dir(backup_dir, target)
                    except Exception:
                        pass
                raise

    install_patch_from_zip = apply_core_patch

    def activate_plugin(self, force: bool = False) -> bool:
        with self._lock:
            if not self.is_plugin_valid():
                return False

            plugin_ver = self.get_plugin_version()
            if not force and plugin_ver:
                if not is_newer_version(plugin_ver, self.current_version):
                    self.log(f"[CORE PATCH] Plugin ({plugin_ver}) is not strictly newer than current ({self.current_version}); keeping current.")
                    return False

            return _purge_and_reimport_core(self.plugin_dir)

    def deactivate_plugin(self) -> None:
        with self._lock:
            norm_plugin = os.path.normcase(self.plugin_dir)
            sys.path[:] = [
                p for p in sys.path
                if not (p and os.path.normcase(os.path.abspath(p)) == norm_plugin)
            ]
            sys.meta_path[:] = [
                f for f in sys.meta_path
                if not isinstance(f, _ExternalCoreFinder)
            ]
