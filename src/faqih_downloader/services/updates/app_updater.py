"""
AppAutoUpdater: GitHub Releases update checker, installer downloader, and upgrader.
"""
import os
import time
import json
import ssl
import tempfile
import threading
import subprocess
import urllib.request
from typing import Dict, Optional, Callable, Any

from .constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
)
from .paths_and_ssl import _is_trusted_update_url, _get_verified_ssl_context
from .versioning import is_newer_version


class AppAutoUpdater:
    """
    Manages checking GitHub Releases for new Faqih Downloader (FD) versions,
    downloading FaqihDownloader-Setup.exe with progress reporting, and launching upgrades.
    """

    def __init__(
        self,
        current_version: str = APP_VERSION,
        repo_owner: str = GITHUB_REPO_OWNER,
        repo_name: str = GITHUB_REPO_NAME,
        on_log: Optional[Callable[[str], None]] = None,
        timeout: int = 12,
        ssl_context: Optional[ssl.SSLContext] = None
    ):
        self.current_version = str(current_version or APP_VERSION).strip()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        self.on_log = on_log
        self.timeout = max(3, int(timeout))
        if ssl_context is not None:
            self.ssl_context = ssl_context
        else:
            self.ssl_context = _get_verified_ssl_context()

    def log(self, message: str):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass

    def check_for_update(self) -> Dict[str, Any]:
        """
        Queries GitHub Releases /releases/latest and compares tag_name against self.current_version.
        Returns a structured dictionary with release metadata and asset URLs.
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SmartDownload-AutoUpdater/{self.current_version}"
        }
        ctx = self.ssl_context if hasattr(self, 'ssl_context') and self.ssl_context is not None else _get_verified_ssl_context()
        try:
            req = urllib.request.Request(self.api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not isinstance(data, dict):
                raise RuntimeError("Invalid JSON payload from GitHub Releases API.")

            tag_name = str(data.get("tag_name") or "").strip()
            latest_clean = tag_name.lstrip("vV").strip() or self.current_version
            release_name = str(data.get("name") or f"{APP_NAME} {tag_name}").strip()
            release_notes = str(data.get("body") or "").strip()
            html_url = str(data.get("html_url") or f"https://github.com/{self.repo_owner}/{self.repo_name}/releases").strip()

            assets = data.get("assets", [])
            installer_url = ""
            installer_name = "FaqihDownloader-Setup.exe"
            installer_size = 0
            portable_url = ""
            core_patch_url = ""
            core_patch_size = 0

            if isinstance(assets, list):
                for asset in assets:
                    if not isinstance(asset, dict):
                        continue
                    a_name = str(asset.get("name") or "")
                    a_url = str(asset.get("browser_download_url") or "")
                    a_size = int(asset.get("size") or 0)
                    if a_name.lower() in ("faqihdownloader-setup.exe", "smartdownload-setup.exe"):
                        installer_url = a_url
                        installer_name = a_name
                        installer_size = a_size
                    elif a_name.lower() in ("faqihdownloader.exe", "smartdownload.exe"):
                        portable_url = a_url
                    elif a_name.lower() in ("faqihdownloader-corepatch.zip", "smartdownload-corepatch.zip"):
                        core_patch_url = a_url
                        core_patch_size = a_size

                # Fallback if Setup.exe wasn't found but another .exe asset exists
                if not installer_url:
                    for asset in assets:
                        if isinstance(asset, dict):
                            a_name = str(asset.get("name") or "")
                            a_url = str(asset.get("browser_download_url") or "")
                            if a_name.lower().endswith(".exe") and a_url:
                                installer_url = a_url
                                installer_name = a_name
                                installer_size = int(asset.get("size") or 0)
                                break

            newer = is_newer_version(tag_name, self.current_version)
            return {
                "success": True,
                "update_available": newer,
                "current_version": self.current_version,
                "latest_version": latest_clean,
                "tag_name": tag_name,
                "release_name": release_name,
                "release_notes": release_notes,
                "html_url": html_url,
                "release_url": html_url,
                "installer_url": installer_url,
                "download_url": installer_url or portable_url,
                "core_patch_url": core_patch_url,
                "core_patch_size": core_patch_size,
                "installer_name": installer_name,
                "asset_name": installer_name,
                "installer_size": installer_size,
                "asset_size": installer_size,
                "portable_url": portable_url,
                "error": None,
            }
        except Exception as e:
            self.log(f"[APP UPDATER] Check failed: {e}")
            return {
                "success": False,
                "update_available": False,
                "current_version": self.current_version,
                "latest_version": self.current_version,
                "error": str(e)
            }

    def download_update(
        self,
        download_url: str,
        dest_path: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> str:
        """
        Streams the installer executable from download_url into a temporary .part file
        and atomically renames it to dest_path upon completion.
        Returns the absolute path to the downloaded installer.
        """
        if not download_url or not isinstance(download_url, str):
            raise ValueError("A valid download_url is required to download update.")

        if not _is_trusted_update_url(download_url):
            raise ValueError(f"Untrusted update URL: {download_url}")

        auto_dest = dest_path is None
        if not dest_path:
            dest_path = os.path.join(tempfile.gettempdir(), "FaqihDownloader-Setup.exe")
        dest_path = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        part_path = f"{dest_path}.part_{os.getpid()}_{threading.get_ident()}"

        headers = {"User-Agent": f"SmartDownload-AutoUpdater/{self.current_version}"}
        ctx = self.ssl_context if hasattr(self, 'ssl_context') and self.ssl_context is not None else _get_verified_ssl_context()
        try:
            req = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                total_size = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(part_path, "wb") as out_f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise RuntimeError("Update download cancelled by user.")
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
                raise RuntimeError("Downloaded update file is missing or empty.")

            try:
                os.replace(part_path, dest_path)
            except PermissionError:
                if auto_dest:
                    alt_dest = os.path.join(
                        tempfile.gettempdir(),
                        f"FaqihDownloader-Setup-{os.getpid()}-{int(time.time())}.exe"
                    )
                    os.replace(part_path, alt_dest)
                    dest_path = os.path.abspath(alt_dest)
                else:
                    raise
            self.log(f"[APP UPDATER] Downloaded update installer to {dest_path} ({os.path.getsize(dest_path):,} bytes).")
            return dest_path
        except Exception:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            raise

    def apply_update(
        self,
        installer_path: str,
        silent: bool = True,
        launch_after: bool = True,
        exit_callback: Optional[Callable[[], None]] = None
    ) -> bool:
        """
        Launches the downloaded FaqihDownloader-Setup.exe installer to upgrade the application,
        and invokes exit_callback so the running instance closes cleanly.
        """
        if not installer_path or not os.path.isfile(installer_path):
            raise FileNotFoundError(f"Update installer not found: {installer_path}")

        abs_installer = os.path.abspath(installer_path)
        cmd = [abs_installer]
        if silent:
            cmd.append("--silent")
            if launch_after:
                cmd.append("--launch")

        self.log(f"[APP UPDATER] Launching update installer: {' '.join(cmd)}")
        subprocess.Popen(cmd, cwd=os.path.dirname(abs_installer))

        if exit_callback:
            try:
                exit_callback()
            except Exception:
                pass
        return True
