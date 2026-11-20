"""
OS shell launch utilities (open file, reveal in explorer/finder) for Faqih Downloader.
"""
import os
import sys
import subprocess
from typing import Optional

from ...config import IS_WINDOWS, get_base_downloads_dir


def _get_resolve_existing_download_path():
    mod = sys.modules.get("faqih_downloader.utils.file_ops")
    if mod and hasattr(mod, "resolve_existing_download_path"):
        return getattr(mod, "resolve_existing_download_path")
    from .path_matcher import resolve_existing_download_path
    return resolve_existing_download_path


def open_downloaded_file(file_path: str):
    """Opens downloaded file with default OS application."""
    if not file_path:
        return
    actual_path = file_path
    if not os.path.isfile(actual_path):
        resolve_fn = _get_resolve_existing_download_path()
        resolved = resolve_fn(file_path)
        if resolved:
            actual_path = resolved
    if not os.path.isfile(actual_path):
        open_containing_folder(file_path)
        return
    try:
        if IS_WINDOWS and hasattr(os, "startfile"):
            os.startfile(actual_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", actual_path])
        else:
            subprocess.Popen(["xdg-open", actual_path])
    except Exception:
        pass


def open_containing_folder(file_path: str):
    """Opens folder containing downloaded file and highlights it on Windows."""
    if not file_path:
        return
    norm_path = os.path.normpath(file_path) if file_path else ""
    base_dir = get_base_downloads_dir() if callable(get_base_downloads_dir) else os.path.expanduser("~/Downloads")

    if not os.path.isfile(norm_path):
        resolve_fn = _get_resolve_existing_download_path()
        resolved = resolve_fn(file_path, base_dir)
        if resolved and os.path.isfile(resolved):
            norm_path = resolved

    folder = norm_path if os.path.isdir(norm_path) else os.path.dirname(norm_path)
    if not folder or not os.path.isdir(folder):
        ext = os.path.splitext(norm_path)[1].lower()
        vid_dir = os.path.join(base_dir, "Video")
        if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv") and os.path.isdir(vid_dir):
            folder = vid_dir
        elif os.path.isdir(base_dir):
            folder = base_dir
        else:
            folder = os.path.expanduser("~")

    try:
        if IS_WINDOWS:
            if os.path.isfile(norm_path):
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"')
            elif os.path.isdir(folder):
                if hasattr(os, "startfile"):
                    os.startfile(folder)
                else:
                    subprocess.Popen(f'explorer.exe "{folder}"')
            else:
                home = os.path.expanduser("~")
                if hasattr(os, "startfile"):
                    os.startfile(home)
                else:
                    subprocess.Popen(f'explorer.exe "{home}"')
        elif sys.platform == "darwin":
            if os.path.exists(norm_path) and os.path.isfile(norm_path):
                subprocess.Popen(["open", "-R", norm_path])
            else:
                subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass
