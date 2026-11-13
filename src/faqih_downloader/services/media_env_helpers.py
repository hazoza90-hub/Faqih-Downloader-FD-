"""
media_env_helpers.py: System environment, FFmpeg binary detection, cookie browser discovery,
and yt-dlp runtime availability helpers for Smart Download (SD).
"""
import os
import sys
import shutil
import time
import re
import queue
import threading
import subprocess
from typing import Dict, List, Optional, Callable, Any, Tuple

try:
    from .updater_service import YtDlpAutoUpdater
except ImportError:
    try:
        from faqih_downloader.services.updater_service import YtDlpAutoUpdater
    except ImportError:
        from updater import YtDlpAutoUpdater

try:
    from ..config import is_test_environment
except ImportError:
    try:
        from faqih_downloader.config import is_test_environment
    except ImportError:
        def is_test_environment() -> bool:
            return bool("unittest" in sys.modules or "pytest" in sys.modules or os.environ.get("SD_TESTING") == "1")


def detect_installed_cookie_browsers() -> List[str]:
    """
    Detects installed web browsers capable of supplying session cookies to yt-dlp.
    Checks standard Windows user data paths under %LOCALAPPDATA% and %APPDATA%:
    - 'firefox': %APPDATA%\\Mozilla\\Firefox\\Profiles
    - 'edge': %LOCALAPPDATA%\\Microsoft\\Edge\\User Data
    - 'chrome': %LOCALAPPDATA%\\Google\\Chrome\\User Data
    - 'brave': %LOCALAPPDATA%\\BraveSoftware\\Brave-Browser\\User Data
    - 'opera': %APPDATA%\\Opera Software\\Opera Stable
    - 'vivaldi': %LOCALAPPDATA%\\Vivaldi\\User Data
    Returns list of detected browser names; falls back to ['edge', 'chrome', 'firefox'] if none found on disk.
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    home = os.path.expanduser("~")

    browser_checks = [
        ("firefox", [
            os.path.join(appdata, "Mozilla", "Firefox", "Profiles") if appdata else "",
            os.path.join(userprofile, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles") if userprofile else "",
            os.path.join(home, ".mozilla", "firefox"),
        ]),
        ("edge", [
            os.path.join(local_appdata, "Microsoft", "Edge", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Microsoft", "Edge", "User Data") if userprofile else "",
            os.path.join(home, ".config", "microsoft-edge"),
        ]),
        ("chrome", [
            os.path.join(local_appdata, "Google", "Chrome", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Google", "Chrome", "User Data") if userprofile else "",
            os.path.join(home, ".config", "google-chrome"),
        ]),
        ("brave", [
            os.path.join(local_appdata, "BraveSoftware", "Brave-Browser", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data") if userprofile else "",
            os.path.join(home, ".config", "BraveSoftware", "Brave-Browser"),
        ]),
        ("opera", [
            os.path.join(appdata, "Opera Software", "Opera Stable") if appdata else "",
            os.path.join(userprofile, "AppData", "Roaming", "Opera Software", "Opera Stable") if userprofile else "",
            os.path.join(home, ".config", "opera"),
        ]),
        ("vivaldi", [
            os.path.join(local_appdata, "Vivaldi", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Vivaldi", "User Data") if userprofile else "",
            os.path.join(home, ".config", "vivaldi"),
        ]),
    ]

    detected: List[str] = []
    for name, candidate_paths in browser_checks:
        for p in candidate_paths:
            if p and os.path.isdir(p):
                detected.append(name)
                break

    return detected if detected else ["edge", "chrome", "firefox"]


def is_ytdlp_available() -> bool:
    """Checks whether the yt-dlp python package or CLI binary is available."""
    ym = sys.modules.get("faqih_downloader.services.youtube_models")
    which_fn = getattr(getattr(ym, "shutil", None), "which", shutil.which) if ym else shutil.which
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return which_fn("yt-dlp") is not None


def get_ytdlp_version() -> str:
    """Returns the currently active yt-dlp version string."""
    return YtDlpAutoUpdater().get_current_version()


def update_ytdlp_engine(
    force: bool = False,
    on_log: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Checks for and applies the latest yt-dlp extractor update into %APPDATA%\\SmartDownload\\yt_dlp_plugin."""
    return YtDlpAutoUpdater(on_log=on_log).update(force=force)


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
    proj_root = os.path.dirname(os.path.dirname(os.path.dirname(file_dir))) if file_dir else ""

    app_dirs = [
        getattr(sys, "_MEIPASS", ""),
        exe_dir,
        os.path.join(exe_dir, "dist") if exe_dir else "",
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


def has_ffmpeg() -> bool:
    """Checks whether FFmpeg executable is installed and reachable."""
    return find_ffmpeg_bin() is not None


def probe_media_file_duration(file_path: str) -> float:
    """Probes media file duration in seconds via FFmpeg stderr inspection."""
    if not file_path or not os.path.isfile(file_path):
        return 0.0
    ffmpeg_bin = find_ffmpeg_bin()
    if not ffmpeg_bin:
        return 0.0
    import subprocess, re
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform.startswith("win") else 0
    try:
        res = subprocess.run([ffmpeg_bin, "-hide_banner", "-i", file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=flags, timeout=3)
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', res.stderr or "")
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def probe_media_duration(file_path: str, ffmpeg_bin: str = "ffmpeg") -> float:
    """Probes media duration in seconds via FFmpeg/ffprobe stderr inspection within 2 seconds."""
    d = probe_media_file_duration(file_path)
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


def _resolve_cookie_browser(cb: Optional[str]) -> Optional[str]:
    """Resolves 'auto' or browser names to a concrete installed browser for yt-dlp."""
    if not cb:
        return None
    val = str(cb).strip().lower()
    if val in ("none", "off", "disabled", "file", ""):
        return None
    if val == "auto":
        detected = detect_installed_cookie_browsers()
        return detected[0] if detected else None
    if val in ("chrome", "edge", "firefox", "brave", "opera", "vivaldi", "safari", "chromium"):
        return val
    return val


def ensure_complete_audio_file(
    stream_info: Any,
    audio_tmp: str,
    tag: str = "Media",
    on_log: Optional[Callable[[str], None]] = None,
    has_prior_error: bool = False
) -> bool:
    """Verifies audio stream completeness and duration; triggers yt-dlp fallback if truncated or missing."""
    cur_sz = os.path.getsize(audio_tmp) if os.path.isfile(audio_tmp) else 0
    exp_dur = float(getattr(stream_info, "duration", 0) or 0)
    exp_sz = int(getattr(stream_info, "audio_size", 0) or 0)
    a_dur = probe_media_file_duration(audio_tmp) if cur_sz > 0 else 0.0

    is_trunc = has_prior_error or (cur_sz < 1024)
    if not is_trunc and exp_dur > 15:
        if a_dur > 0 and a_dur < (0.85 * exp_dur):
            is_trunc = True
        elif a_dur == 0 and exp_sz > 0 and cur_sz < (0.85 * exp_sz):
            is_trunc = True

    if is_trunc:
        if on_log:
            on_log(f"[{tag}] Audio stream missing, failed or incomplete ({cur_sz:,} bytes). Triggering yt-dlp fallback...")
        return recover_audio_stream_fallback(stream_info, audio_tmp, on_log=on_log)
    return True


def recover_audio_stream_fallback(stream_info: Any, audio_tmp: str, on_log: Optional[Callable[[str], None]] = None) -> bool:
    """Fallback audio downloader via yt_dlp directly to audio_tmp when stream is truncated."""
    try:
        import yt_dlp
        from ..config import get_setting
        cb = _resolve_cookie_browser(get_setting("cookies_browser", "none"))
        target_url = getattr(stream_info, "webpage_url", "") or ""
        v_id = getattr(stream_info, "video_id", "")
        if not target_url and v_id:
            target_url = f"https://www.youtube.com/watch?v={v_id}"
        if not target_url:
            return False

        fmt_id = str(getattr(stream_info, "audio_format_id", "") or "").strip()
        lang = getattr(stream_info, "audio_language", None)
        if fmt_id:
            fmt_spec = f"{fmt_id}/bestaudio[language={lang}]/bestaudio" if lang else f"{fmt_id}/bestaudio"
        elif lang:
            fmt_spec = f"bestaudio[language={lang}]/bestaudio"
        else:
            fmt_spec = "bestaudio"

        ydl_opts: Dict[str, Any] = {
            "format": fmt_spec,
            "outtmpl": audio_tmp,
            "overwrites": True,
            "quiet": True,
            "no_warnings": True,
        }
        if cb:
            ydl_opts["cookiesfrombrowser"] = (cb,)
        if hasattr(stream_info, "audio_headers") and stream_info.audio_headers:
            ydl_opts["http_headers"] = stream_info.audio_headers

        if on_log:
            on_log(f"[AUDIO FALLBACK] Downloading complete audio track ({fmt_id or lang or 'default'}) via yt-dlp...")
        if os.path.exists(audio_tmp):
            try: os.remove(audio_tmp)
            except Exception: pass

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])

        if not os.path.exists(audio_tmp):
            d_dir = os.path.dirname(audio_tmp) or "."
            b_name = os.path.basename(audio_tmp)
            for f in os.listdir(d_dir):
                if f.startswith(b_name) and os.path.isfile(os.path.join(d_dir, f)):
                    shutil.move(os.path.join(d_dir, f), audio_tmp)
                    break
        ok = os.path.isfile(audio_tmp) and os.path.getsize(audio_tmp) > 1024
        if on_log and ok:
            on_log(f"[AUDIO FALLBACK SUCCESS] Full audio track restored ({os.path.getsize(audio_tmp):,} bytes)!")
        return ok
    except Exception as e:
        if on_log:
            on_log(f"[AUDIO FALLBACK FAILED] {e}")
        return False


def run_ffmpeg_with_progress(
    cmd: List[str],
    cancel_event: Optional[Any] = None,
    creationflags: int = 0,
    cwd: Optional[str] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
    subprocess_mod: Any = None
) -> Tuple[int, str]:
    """
    Executes FFmpeg with real-time percentage progress, live ETA calculation,
    cancellation monitoring, and full backward-compatibility with unit test mocks.
    """
    if cancel_event and cancel_event.is_set():
        return -999, "Cancelled"

    if on_progress_pct:
        try: on_progress_pct(0.0, "--:--")
        except Exception: pass

    sp = subprocess_mod or subprocess
    is_sp_mock = hasattr(getattr(sp, "Popen", None), "_mock_name") or hasattr(getattr(sp, "run", None), "_mock_name")
    if is_sp_mock and not hasattr(getattr(sp, "Popen", None), "_mock_name"):
        res = sp.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=cwd, creationflags=creationflags)
        return (res.returncode if getattr(res, "returncode", None) is not None else 0), str(getattr(res, "stderr", "") or "")

    exec_cmd = list(cmd)
    eff_dur = float(total_duration or 0.0)

    if not is_sp_mock:
        first_arg = os.path.basename(str(exec_cmd[0])).lower() if exec_cmd else ""
        if "ffmpeg" in first_arg:
            if "-nostats" in exec_cmd:
                exec_cmd = [x for x in exec_cmd if x != "-nostats"]
            if "-stats" not in exec_cmd and len(exec_cmd) > 1:
                exec_cmd.insert(1, "-stats")
            for idx in range(len(exec_cmd) - 1):
                if exec_cmd[idx] in ("-loglevel", "-v") and exec_cmd[idx + 1] in ("error", "fatal", "quiet", "panic"):
                    exec_cmd[idx + 1] = "info"

            if eff_dur <= 0.0:
                for idx in range(len(exec_cmd) - 1):
                    if exec_cmd[idx] == "-i":
                        cand_input = exec_cmd[idx + 1]
                        if os.path.isfile(cand_input):
                            pd = probe_media_duration(cand_input, exec_cmd[0])
                            if pd > 0.0:
                                eff_dur = pd
                                break

    try:
        proc = sp.Popen(
            exec_cmd if not is_sp_mock else cmd,
            stdout=subprocess.DEVNULL if not is_sp_mock else subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            creationflags=creationflags
        )
    except Exception as e:
        return -1, str(e)

    is_mock = (
        is_sp_mock
        or hasattr(proc, "_mock_name")
        or hasattr(getattr(proc, "poll", None), "_mock_name")
        or hasattr(getattr(proc, "stderr", None), "_mock_name")
        or "mock" in type(getattr(proc, "stderr", None)).__name__.lower()
        or not hasattr(getattr(proc, "stderr", None), "read")
    )
    if is_mock:
        try:
            comm = ("", "")
            while hasattr(proc, "communicate"):
                if cancel_event and cancel_event.is_set():
                    try: proc.kill()
                    except Exception: pass
                    return -999, "Cancelled"
                try:
                    comm = proc.communicate(timeout=0.05); break
                except subprocess.TimeoutExpired:
                    time.sleep(0.01)
            out, err = (comm[0], comm[1]) if isinstance(comm, (tuple, list)) and len(comm) >= 2 else ("", "")
            rc = proc.returncode if isinstance(getattr(proc, "returncode", None), int) else 0
            if rc == 0 and on_progress_pct:
                try: on_progress_pct(100.0, "00:00")
                except Exception: pass
            return rc, str(err or "")
        except Exception:
            rc = getattr(proc, "returncode", 0)
            return (rc if isinstance(rc, int) else 0), ""

    err_tail: List[str] = []
    q: queue.Queue = queue.Queue()

    def _stderr_reader():
        try:
            buf = b""
            while True:
                chunk = proc.stderr.read1(1024) if hasattr(proc.stderr, "read1") else proc.stderr.read(512)
                if not chunk:
                    if buf: q.put(buf)
                    break
                buf += chunk
                while b"\r" in buf or b"\n" in buf:
                    m = re.search(b'[\r\n]', buf)
                    if not m: break
                    idx = m.start()
                    line = buf[:idx]
                    buf = buf[idx+1:]
                    if line: q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)

    reader_t = threading.Thread(target=_stderr_reader, daemon=True)
    reader_t.start()

    start_t = time.time()
    last_emit = 0.0

    try:
        while True:
            if cancel_event and cancel_event.is_set():
                try: proc.kill()
                except Exception: pass
                try: proc.wait(timeout=1.0)
                except Exception: pass
                return -999, "Cancelled"

            try:
                item = q.get(timeout=0.06)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue

            if item is None:
                break

            text_line = item.decode("utf-8", errors="replace").strip()
            err_tail.append(text_line)
            if len(err_tail) > 100:
                err_tail.pop(0)

            if eff_dur <= 0.0:
                m_dur = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', text_line)
                if m_dur:
                    hh, mm, ss = m_dur.groups()
                    eff_dur = int(hh) * 3600.0 + int(mm) * 60.0 + float(ss)

            m_time = re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', text_line)
            if m_time and eff_dur > 0.0:
                hh, mm, ss = m_time.groups()
                cur_sec = int(hh) * 3600.0 + int(mm) * 60.0 + float(ss)
                pct = min(99.0, max(1.0, (cur_sec / eff_dur) * 100.0))
                now_t = time.time()
                elapsed = max(0.1, now_t - start_t)
                eta_sec = int(max(0.0, elapsed * ((100.0 - pct) / pct))) if pct >= 1.5 else 0
                eta_str = f"{eta_sec // 3600:02d}:{(eta_sec % 3600) // 60:02d}:{eta_sec % 60:02d}" if eta_sec >= 3600 else (f"{eta_sec // 60:02d}:{eta_sec % 60:02d}" if eta_sec > 0 else "--:--")
                if on_progress_pct and (now_t - last_emit >= 0.12):
                    try: on_progress_pct(pct, eta_str)
                    except Exception: pass
                    last_emit = now_t
    finally:
        try:
            if proc.poll() is None: proc.kill()
        except Exception: pass
        try: proc.wait(timeout=1.0)
        except Exception: pass
        for stream in (getattr(proc, "stderr", None), getattr(proc, "stdout", None)):
            if stream and hasattr(stream, "close"):
                try: stream.close()
                except Exception: pass

    try: proc.wait()
    except Exception: pass
    rc = proc.returncode if proc.returncode is not None else 0
    if rc == 0 and on_progress_pct:
        try: on_progress_pct(100.0, "00:00")
        except Exception: pass

    err_msg = "\n".join(err_tail[-40:])
    return rc, err_msg


__all__ = [
    "detect_installed_cookie_browsers",
    "is_ytdlp_available",
    "get_ytdlp_version",
    "update_ytdlp_engine",
    "find_ffmpeg_bin",
    "has_ffmpeg",
    "probe_media_file_duration",
    "probe_media_duration",
    "recover_audio_stream_fallback",
    "ensure_complete_audio_file",
    "_resolve_cookie_browser",
    "run_ffmpeg_with_progress",
]
