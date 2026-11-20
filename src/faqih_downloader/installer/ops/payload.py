"""
Installer payload file discovery and resilient file copy operations for Faqih Downloader.
"""
import os
import sys
import time
import shutil
from typing import Dict


def _get_terminate_running_app():
    for mod_name in ("faqih_downloader.installer.installer_ops", "faqih_downloader.installer.ops", "installer"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "terminate_running_app"):
            return getattr(mod, "terminate_running_app")
    from .process_guard import terminate_running_app
    return terminate_running_app


def find_payload_sources() -> Dict[str, str]:
    """Finds payload files from PyInstaller bundle, dist folder, or current project root."""
    sources = {}
    base_dirs = []

    # 1. PyInstaller _MEIPASS bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dirs.append(os.path.join(sys._MEIPASS, "payload"))
        base_dirs.append(sys._MEIPASS)

    # 2. Local workspace directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    proj_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    for d in [proj_root, current_dir, os.getcwd()]:
        base_dirs.append(os.path.join(d, "installer_payload"))
        base_dirs.append(os.path.join(d, "dist"))
        base_dirs.append(os.path.join(d, "assets"))
        base_dirs.append(os.path.join(d, "scripts"))
        base_dirs.append(d)

    for b in base_dirs:
        for ex in ("FaqihDownloader.exe", "SmartDownload.exe", "TurboDownloader.exe"):
            cand = os.path.join(b, ex)
            if os.path.isfile(cand) and ex not in sources:
                sources[ex] = cand
                sources.setdefault("FaqihDownloader.exe", cand)
                sources.setdefault("SmartDownload.exe", cand)
        for cand in [os.path.join(b, "app_icon.ico"), os.path.join(b, "assets", "app_icon.ico")]:
            if os.path.isfile(cand) and "app_icon.ico" not in sources:
                sources["app_icon.ico"] = cand
        for cand in [os.path.join(b, "app_icon.png"), os.path.join(b, "assets", "app_icon.png")]:
            if os.path.isfile(cand) and "app_icon.png" not in sources:
                sources["app_icon.png"] = cand
        cand_ext = os.path.join(b, "extension")
        if os.path.isdir(cand_ext) and "extension" not in sources:
            sources["extension"] = cand_ext
        for cand in [os.path.join(b, "fd_host.bat"), os.path.join(b, "scripts", "fd_host.bat")]:
            if os.path.isfile(cand) and "fd_host.bat" not in sources:
                sources["fd_host.bat"] = cand
        for fn in ("com.faqihdownloader.host.json", "register_browser.py", "host_manifest.py", "ffmpeg.exe", "payload.lzma.zip"):
            cand = os.path.join(b, fn)
            if os.path.isfile(cand) and fn not in sources:
                sources[fn] = cand

    return sources


get_payload_dir = find_payload_sources


def _copy_file_with_retry(src: str, dst: str, retries: int = 10, delay: float = 0.3):
    """Copies src to dst with retry logic, terminating locking processes and removing read-only flags."""
    for attempt in range(retries):
        try:
            if os.path.exists(dst):
                try:
                    os.chmod(dst, 0o777)
                except Exception:
                    pass
            shutil.copy2(src, dst)
            return
        except (PermissionError, OSError):
            if attempt == retries - 1:
                raise
            term_fn = _get_terminate_running_app()
            term_fn()
            if os.path.exists(dst):
                try:
                    os.chmod(dst, 0o777)
                except Exception:
                    pass
            time.sleep(delay * (attempt + 1))
