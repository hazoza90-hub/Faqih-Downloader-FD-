"""
ffmpeg_exec.py: Cancellable FFmpeg execution wrapper and ASCII-safe temporary directory resolution.
"""
import os
import sys
import time
import subprocess
from typing import Optional, Callable, Any, Tuple

from ..media_env.ffmpeg_runner import run_ffmpeg_with_progress

IS_WINDOWS = sys.platform.startswith("win")


def run_cancellable_ffmpeg(
    cmd,
    cancel_event=None,
    creationflags=0,
    timeout=1800,
    subprocess_mod=None,
    total_duration=0.0,
    on_progress_pct=None,
    run_ffmpeg_fn: Optional[Callable[..., Tuple[int, str]]] = None,
):
    """
    Executes an FFmpeg command with cancellation event polling, progress tracking,
    and returns subprocess.CompletedProcess for 100% backward compatibility.
    """
    sp_mod = sys.modules.get("faqih_downloader.services.subtitle_processor")
    sp = subprocess_mod or (getattr(sp_mod, "subprocess", subprocess) if sp_mod else subprocess)
    eff_run_ffmpeg = run_ffmpeg_fn or (getattr(sp_mod, "run_ffmpeg_with_progress", run_ffmpeg_with_progress) if sp_mod else run_ffmpeg_with_progress)

    if cancel_event and cancel_event.is_set():
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="Cancelled before execution")
    rc, err = eff_run_ffmpeg(
        cmd, cancel_event=cancel_event, creationflags=creationflags,
        total_duration=total_duration, on_progress_pct=on_progress_pct,
        subprocess_mod=sp
    )
    return subprocess.CompletedProcess(cmd, returncode=(-1 if rc == -999 else rc), stdout="", stderr=err)


def _is_ascii_writable_dir(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    abs_path = os.path.abspath(path)
    if not all(ord(c) < 128 for c in abs_path):
        return False
    test_file = os.path.join(abs_path, f"_sd_test_{os.getpid()}_{int(time.time()*1000)}.tmp")
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False


def _get_ascii_safe_temp_dir(fallback_dir: str) -> str:
    """Returns the first existing writable 100% ASCII directory for libass safe fopen on Windows."""
    if fallback_dir and _is_ascii_writable_dir(fallback_dir):
        return os.path.abspath(fallback_dir)
    import tempfile
    candidates = [
        tempfile.gettempdir(),
        r"C:\Users\Public",
        r"C:\Users\Public\Documents",
        r"C:\Users\Public\Downloads",
        r"C:\Temp",
        r"C:\Windows\Temp",
    ]
    for cand in candidates:
        try:
            if not os.path.isdir(cand) and cand == r"C:\Temp":
                try:
                    os.makedirs(cand, exist_ok=True)
                except Exception:
                    pass
            if _is_ascii_writable_dir(cand):
                return os.path.abspath(cand)
        except Exception:
            pass
    return os.path.abspath(fallback_dir) if fallback_dir else os.getcwd()


__all__ = [
    "IS_WINDOWS",
    "run_cancellable_ffmpeg",
    "_is_ascii_writable_dir",
    "_get_ascii_safe_temp_dir",
]
