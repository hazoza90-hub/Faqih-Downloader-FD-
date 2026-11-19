"""
ffmpeg_probe.py: FFmpeg binary discovery and media duration probing.
"""
import os
import sys
import shutil
import re
import subprocess
from typing import Optional, Callable

try:
    from ...config import is_test_environment
except ImportError:
    try:
        from faqih_downloader.config import is_test_environment
    except ImportError:
        def is_test_environment() -> bool:
            return bool("unittest" in sys.modules or "pytest" in sys.modules or os.environ.get("SD_TESTING") == "1")


def find_ffmpeg_bin() -> Optional[str]:
    """
    Finds FFmpeg executable in bundled dirs, PATH, imageio_ffmpeg, WinGet, Scoop, or Chocolatey.
    Searches in order:
    1. Bundled PyInstaller directory (sys._MEIPASS and os.path.dirname(sys.executable)).
    2. shutil.which("ffmpeg").
    3. imageio_ffmpeg.get_ffmpeg_exe().
    4. Windows WinGet, Scoop, Chocolatey, and standard install paths.
    """
    ym = sys.modules.get("faqih_downloader.services.youtube_models")
    which_fn = getattr(getattr(ym, "shutil", None), "which", shutil.which) if ym else shutil.which

    is_win = sys.platform.startswith("win")
    exe_name = "ffmpeg.exe" if is_win else "ffmpeg"

    # 1. Bundled PyInstaller directory and runtime paths
    exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if hasattr(sys, "executable") else ""
    cwd = os.getcwd()
    file_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
    services_dir = os.path.dirname(file_dir) if file_dir else ""
    proj_root = os.path.dirname(os.path.dirname(os.path.dirname(services_dir))) if services_dir else ""

    app_dirs = [
        getattr(sys, "_MEIPASS", ""),
        exe_dir,
        os.path.join(exe_dir, "dist") if exe_dir else "",
        services_dir,
        file_dir,
    ]
    if not is_test_environment():
        app_dirs.extend([
            cwd,
            os.path.join(cwd, "dist"),
            proj_root,
            os.path.join(proj_root, "dist") if proj_root else "",
        ])
    for d in app_dirs:
        if d:
            candidate = os.path.join(d, exe_name)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

    # 2. PATH
    bin_path = which_fn("ffmpeg") or which_fn(exe_name)
    if bin_path and os.path.isfile(bin_path):
        return os.path.abspath(bin_path)

    # 3. imageio_ffmpeg
    try:
        import imageio_ffmpeg
        img_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if img_exe and os.path.isfile(img_exe):
            return os.path.abspath(img_exe)
    except Exception:
        pass

    # 4. Windows WinGet, Scoop, and Chocolatey install paths
    if is_win:
        user_prof = os.environ.get("USERPROFILE", "")
        local_app = os.environ.get("LOCALAPPDATA", "")
        fixed_cands = [
            os.path.join(local_app, "Programs", "FaqihDownloader", "ffmpeg.exe") if local_app else "",
            os.path.join(local_app, "Programs", "SmartDownload", "ffmpeg.exe") if local_app else "",
            os.path.join(proj_root, "installer_payload", "ffmpeg.exe") if proj_root else "",
            os.path.join(proj_root, "dist", "ffmpeg.exe") if proj_root else "",
            os.path.join(user_prof, "scoop", "apps", "ffmpeg", "current", "bin", "ffmpeg.exe"),
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.join(local_app, "Programs", "ffmpeg", "bin", "ffmpeg.exe"),
        ]
        for cand in fixed_cands:
            if cand and os.path.isfile(cand):
                return os.path.abspath(cand)

        winget_pkgs = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(winget_pkgs):
            try:
                for root, _, files in os.walk(winget_pkgs):
                    if "ffmpeg.exe" in files:
                        p = os.path.join(root, "ffmpeg.exe")
                        if os.path.isfile(p):
                            return os.path.abspath(p)
            except Exception:
                pass

    return None


def _resolve_find_ffmpeg(find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None) -> Callable[[], Optional[str]]:
    """Resolves find_ffmpeg_bin preserving patches on media_env_helpers if present."""
    if find_ffmpeg_fn is not None:
        return find_ffmpeg_fn
    meh = sys.modules.get("faqih_downloader.services.media_env_helpers")
    return getattr(meh, "find_ffmpeg_bin", find_ffmpeg_bin) if meh else find_ffmpeg_bin


def has_ffmpeg(find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None) -> bool:
    """Checks whether FFmpeg executable is installed and reachable."""
    return _resolve_find_ffmpeg(find_ffmpeg_fn)() is not None


def probe_media_file_duration(
    file_path: str,
    find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None,
) -> float:
    """Probes media file duration in seconds via FFmpeg stderr inspection."""
    if not file_path or not os.path.isfile(file_path):
        return 0.0
    ffmpeg_bin = _resolve_find_ffmpeg(find_ffmpeg_fn)()
    if not ffmpeg_bin:
        return 0.0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform.startswith("win") else 0
    try:
        res = subprocess.run([ffmpeg_bin, "-hide_banner", "-i", file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=flags, timeout=3)
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', res.stderr or "")
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def probe_media_duration(
    file_path: str,
    ffmpeg_bin: str = "ffmpeg",
    find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None,
) -> float:
    """Probes media duration in seconds via FFmpeg/ffprobe stderr inspection within 2 seconds."""
    d = probe_media_file_duration(file_path, find_ffmpeg_fn=find_ffmpeg_fn)
    if d > 0:
        return d
    if ffmpeg_bin and file_path and os.path.isfile(file_path):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform.startswith("win") else 0
        try:
            res = subprocess.run([ffmpeg_bin, "-hide_banner", "-i", os.path.abspath(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=flags, timeout=2)
            m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', res.stderr or "")
            if m:
                return float(m.group(1)) * 3600.0 + float(m.group(2)) * 60.0 + float(m.group(3))
        except Exception:
            pass
    return -1.0


__all__ = [
    "find_ffmpeg_bin",
    "has_ffmpeg",
    "probe_media_file_duration",
    "probe_media_duration",
]
