"""
process_launcher.py: Subprocess lifecycle, pywebview launcher, and chromeless browser discovery.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from typing import Optional

IS_WINDOWS = sys.platform.startswith("win")
_ACTIVE_PREVIEW_PROC: Optional[subprocess.Popen] = None


class _PreviewJsApi:
    def close_window(self) -> None:
        try:
            import webview
            for w in getattr(webview, "windows", []): w.destroy()
        except Exception: pass


def terminate_active_preview_proc() -> None:
    """Terminates currently running preview subprocess to prevent hanging webview instances."""
    global _ACTIVE_PREVIEW_PROC
    vpm_mod = sys.modules.get("faqih_downloader.ui.modals.video_preview_modal")
    procs = [_ACTIVE_PREVIEW_PROC]
    if vpm_mod is not None:
        vpm_proc = getattr(vpm_mod, "_ACTIVE_PREVIEW_PROC", None)
        if vpm_proc is not None and vpm_proc is not _ACTIVE_PREVIEW_PROC:
            procs.append(vpm_proc)
    for proc in procs:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=0.8)
                    except Exception: proc.kill()
            except Exception: pass
    _ACTIVE_PREVIEW_PROC = None
    if vpm_mod is not None:
        try: vpm_mod._ACTIVE_PREVIEW_PROC = None
        except Exception: pass


def _launch_webview_subprocess(html_target: str, title: str = "Faqih Downloader — Video Preview", width: int = 920, height: int = 720) -> None:
    """Subprocess target executing pywebview with bridge js_api and immediate exit on close."""
    try:
        import webview
        webview.create_window(title, html_target, width=width, height=height, js_api=_PreviewJsApi())
        webview.start()
    except Exception: pass
    finally: os._exit(0)


def _find_chromeless_browser() -> Optional[str]:
    """Finds installed Microsoft Edge, Google Chrome, or Brave executable on Windows."""
    # 1. Edge
    edge_paths = [
        shutil.which("msedge"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if p and os.path.isfile(p):
            return os.path.abspath(p)

    # 2. Chrome
    chrome_paths = [
        shutil.which("chrome"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if p and os.path.isfile(p):
            return os.path.abspath(p)

    # 3. Brave
    brave_paths = [
        shutil.which("brave"),
        shutil.which("brave-browser"),
        os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for p in brave_paths:
        if p and os.path.isfile(p):
            return os.path.abspath(p)

    # 4. Chromium / Google Chrome on Linux/Mac
    for name in ("google-chrome", "chromium", "chromium-browser"):
        w = shutil.which(name)
        if w and os.path.isfile(w):
            return os.path.abspath(w)

    return None


__all__ = [
    "IS_WINDOWS",
    "_ACTIVE_PREVIEW_PROC",
    "_PreviewJsApi",
    "terminate_active_preview_proc",
    "_launch_webview_subprocess",
    "_find_chromeless_browser",
]
