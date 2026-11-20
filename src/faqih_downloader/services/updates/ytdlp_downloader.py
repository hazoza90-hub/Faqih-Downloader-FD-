"""
YtDlpArchiveUpdaterMixin: checking PyPI/GitHub Releases, downloading, validating,
and atomically extracting yt-dlp archives.
"""
import os
import json
import time
import shutil
import zipfile
import threading
import urllib.request
from typing import Dict, Optional, Callable, Any

from .constants import APP_VERSION, YTDLP_PYPI_JSON_API, YTDLP_GITHUB_LATEST_API
from .paths_and_ssl import (
    _get_ssl_context,
    _get_verified_ssl_context,
    _is_trusted_update_url,
)
from .versioning import is_newer_version


class YtDlpArchiveUpdaterMixin:
    """Mixin handling remote version checks and atomic archive extraction for yt-dlp."""

    def check_for_update(self) -> Dict[str, Any]:
        """
        Queries PyPI JSON API (with fallback to GitHub Releases API) for the latest yt-dlp version.
        Never raises on network errors; returns a structured dict with 'success' and 'update_available'.
        """
        current_ver = self.get_current_version()
        headers = {
            "Accept": "application/json",
            "User-Agent": f"SmartDownload-Updater/{APP_VERSION}"
        }
        ctx = _get_ssl_context()

        # 1. Primary source: PyPI JSON API
        try:
            req = urllib.request.Request(YTDLP_PYPI_JSON_API, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            info = data.get("info", {})
            remote_ver = str(info.get("version") or "").strip()
            urls = data.get("urls", [])
            wheel_url = ""
            for u in urls:
                if isinstance(u, dict):
                    u_url = str(u.get("url") or "")
                    pkg_type = str(u.get("packagetype") or "")
                    if pkg_type == "bdist_wheel" or u_url.endswith(".whl"):
                        wheel_url = u_url
                        break
            if remote_ver and wheel_url:
                newer = is_newer_version(remote_ver, current_ver)
                return {
                    "success": True,
                    "update_available": newer,
                    "current_version": current_ver,
                    "latest_version": remote_ver,
                    "download_url": wheel_url,
                    "source": "pypi"
                }
        except Exception as pypi_err:
            self.log(f"[YTDLP] PyPI check failed ({pypi_err}); trying GitHub Releases fallback...")

        # 2. Fallback source: GitHub Releases API
        try:
            req = urllib.request.Request(YTDLP_GITHUB_LATEST_API, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            remote_ver = str(data.get("tag_name") or "").strip().lstrip("vV")
            assets = data.get("assets", [])
            zip_url = ""
            for asset in assets:
                if isinstance(asset, dict) and asset.get("name") == "yt-dlp":
                    zip_url = str(asset.get("browser_download_url") or "")
                    break
            if remote_ver and zip_url:
                newer = is_newer_version(remote_ver, current_ver)
                return {
                    "success": True,
                    "update_available": newer,
                    "current_version": current_ver,
                    "latest_version": remote_ver,
                    "download_url": zip_url,
                    "source": "github"
                }
            raise RuntimeError("Could not locate yt-dlp package asset in release metadata.")
        except Exception as gh_err:
            return {
                "success": False,
                "update_available": False,
                "current_version": current_ver,
                "latest_version": current_ver,
                "error": str(gh_err)
            }

    @staticmethod
    def _safe_replace_dir(src: str, dst: str, retries: int = 5, delay: float = 0.06) -> None:
        """
        Replaces directory dst with src, retrying transient Windows PermissionError/OSError
        (e.g., antivirus/indexer read handles) and falling back to copytree+rmtree if needed.
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
        # Fallback if os.replace failed due to a transient open handle on Windows
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            shutil.rmtree(src, ignore_errors=True)
            return
        if last_err:
            raise last_err

    def download_and_extract_archive(
        self,
        download_url: str,
        target_version: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Downloads a yt-dlp wheel or zipimport archive, extracts the yt_dlp package into a staging
        directory, validates its structure, atomically swaps it into self.plugin_dir, and activates it.
        """
        if not _is_trusted_update_url(download_url):
            raise ValueError(f"Untrusted yt-dlp update URL: {download_url}")
        parent_dir = os.path.dirname(self.plugin_dir)
        os.makedirs(parent_dir, exist_ok=True)
        uid = f"{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}"
        staging_dir = os.path.join(parent_dir, f"yt_dlp_staging_{uid}")
        backup_dir = f"{self.plugin_dir}_backup_{uid}"
        archive_path = os.path.join(parent_dir, f"yt_dlp_download_{uid}.zip")

        try:
            if os.path.exists(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)
            os.makedirs(staging_dir, exist_ok=True)

            headers = {"User-Agent": f"SmartDownload-Updater/{APP_VERSION}"}
            req = urllib.request.Request(download_url, headers=headers)
            ctx = _get_verified_ssl_context()

            self.log(f"[YTDLP] Downloading yt-dlp package update from {download_url}...")
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                total_size = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(archive_path, "wb") as out_f:
                    while True:
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

            if not os.path.isfile(archive_path) or os.path.getsize(archive_path) == 0:
                raise RuntimeError("Downloaded yt-dlp archive is missing or empty.")

            if not zipfile.is_zipfile(archive_path):
                raise RuntimeError("Downloaded file is not a valid ZIP/Wheel archive.")

            # Extract only yt_dlp/ package files safely (preventing path traversal)
            abs_staging = os.path.abspath(staging_dir)
            with zipfile.ZipFile(archive_path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file is not None:
                    raise RuntimeError(f"Corrupted file in yt-dlp archive: {bad_file}")
                for member in zf.infolist():
                    norm_name = member.filename.replace("\\", "/").lstrip("/")
                    if not (norm_name == "yt_dlp" or norm_name.startswith("yt_dlp/")):
                        continue
                    if ".." in norm_name.split("/"):
                        continue
                    dest_path = os.path.abspath(os.path.join(abs_staging, *norm_name.split("/")))
                    if os.path.splitdrive(dest_path)[0].lower() != os.path.splitdrive(abs_staging)[0].lower() or not (dest_path == abs_staging or dest_path.startswith(abs_staging + os.sep)):
                        continue
                    if member.is_dir() or norm_name.endswith("/"):
                        os.makedirs(dest_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with zf.open(member, "r") as src_f, open(dest_path, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

            if not self.is_plugin_valid(staging_dir):
                raise RuntimeError("Extracted archive does not contain a valid yt_dlp Python package.")

            detected_ver = self.get_plugin_version(staging_dir) or target_version or "unknown"
            meta_path = os.path.join(staging_dir, "plugin_meta.json")
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump({
                    "version": detected_ver,
                    "updated_at": time.time(),
                    "download_url": download_url
                }, mf, indent=2)

            # Thread-safe atomic swap with backup recovery
            with self._lock:
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir, ignore_errors=True)
                moved_to_backup = False
                if os.path.exists(self.plugin_dir):
                    self._safe_replace_dir(self.plugin_dir, backup_dir)
                    moved_to_backup = True

                try:
                    self._safe_replace_dir(staging_dir, self.plugin_dir)
                except Exception:
                    if moved_to_backup and os.path.exists(backup_dir):
                        try:
                            self._safe_replace_dir(backup_dir, self.plugin_dir)
                        except Exception:
                            pass
                    raise

                if not self.activate_plugin(force=True):
                    # Rollback to backup if activation failed
                    if os.path.exists(self.plugin_dir):
                        shutil.rmtree(self.plugin_dir, ignore_errors=True)
                    if os.path.exists(backup_dir):
                        self._safe_replace_dir(backup_dir, self.plugin_dir)
                        self.activate_plugin(force=True)
                    raise RuntimeError("Failed to activate newly extracted yt-dlp plugin.")

                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir, ignore_errors=True)

                active_ver = self.get_current_version()
                self.log(f"[YTDLP] Successfully updated and activated yt-dlp v{active_ver}!")
                return {
                    "success": True,
                    "updated": True,
                    "version": active_ver,
                    "plugin_dir": self.plugin_dir
                }

        except Exception as e:
            with self._lock:
                if not self.is_plugin_valid(self.plugin_dir) and os.path.exists(backup_dir):
                    try:
                        self._safe_replace_dir(backup_dir, self.plugin_dir)
                        self.activate_plugin(force=True)
                    except Exception:
                        pass
            self.log(f"[YTDLP ERROR] Update failed: {e}")
            return {
                "success": False,
                "updated": False,
                "version": self.get_current_version(),
                "error": str(e)
            }
        finally:
            if os.path.exists(archive_path):
                try:
                    os.remove(archive_path)
                except Exception:
                    pass
            if os.path.exists(staging_dir):
                try:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                except Exception:
                    pass
            if os.path.exists(backup_dir):
                try:
                    shutil.rmtree(backup_dir, ignore_errors=True)
                except Exception:
                    pass

    def update(
        self,
        force: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """Checks for a newer yt-dlp release and updates the external plugin if available."""
        check_res = self.check_for_update()
        if not check_res.get("success"):
            return {
                "success": False,
                "updated": False,
                "version": check_res.get("current_version", self.get_current_version()),
                "error": check_res.get("error", "Failed to check for yt-dlp updates")
            }

        if not check_res.get("update_available") and not force:
            cur = check_res.get("current_version", self.get_current_version())
            self.log(f"[YTDLP] yt-dlp is already up to date (v{cur}).")
            return {
                "success": True,
                "updated": False,
                "version": cur,
                "latest_version": check_res.get("latest_version", cur),
                "message": f"yt-dlp is up to date ({cur})"
            }

        download_url = check_res.get("download_url", "")
        if not download_url:
            return {
                "success": False,
                "updated": False,
                "version": check_res.get("current_version", self.get_current_version()),
                "error": "No download URL found for yt-dlp update"
            }

        return self.download_and_extract_archive(
            download_url=download_url,
            target_version=check_res.get("latest_version", ""),
            progress_cb=progress_cb
        )
