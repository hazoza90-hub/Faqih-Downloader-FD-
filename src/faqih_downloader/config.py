"""
Application configuration, paths, constants, and settings management for Smart Download.
"""
import os
import sys
import json
import shutil
import tempfile
import threading
from typing import Dict, Any, Optional, Tuple

APP_NAME = "Faqih Downloader (FD)"
APP_TITLE = "Faqih Downloader (FD)"
APP_ID = "SmartDownload"
APP_VERSION = "2.0.2"
APP_AUTHOR = "Faqih Downloader Team"
GITHUB_REPO_OWNER = "hazoza90-hub"
GITHUB_REPO_NAME = "Faqih-Downloader-FD-"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

IS_WINDOWS = sys.platform.startswith("win")

# Dynamic chunking engine defaults
CHUNK_SIZE_KB = 1024
MAX_CONCURRENT_CHUNKS = 32
DEFAULT_CHUNKS = 8
MIN_CHUNK_BYTES = 512 * 1024
BUFFER_SIZE = 64 * 1024

DEFAULT_SNIFFER_PLATFORMS: Dict[str, bool] = {
    "youtube": True,
    "tiktok": True,
    "instagram": True,
    "facebook": True,
    "twitter": True,
    "reddit": True,
    "vimeo": True,
    "dailymotion": True,
    "pinterest": True,
    "threads": True,
    "snapchat": True,
    "twitch": True,
    "rumble": True,
    "direct_files": True,
}

def get_resource_path(relative_path: str) -> str:
    """Resolve absolute path for bundled assets across PyInstaller, executable dir, cwd, and source tree."""
    if not relative_path:
        return ""
    if os.path.isabs(relative_path) and os.path.exists(relative_path):
        return relative_path

    # 1. sys._MEIPASS (direct and inside assets/)
    if hasattr(sys, "_MEIPASS") and sys._MEIPASS:
        for cand in (
            os.path.join(sys._MEIPASS, relative_path),
            os.path.join(sys._MEIPASS, "assets", relative_path),
        ):
            if os.path.exists(cand):
                return cand

    # 2. Executable directory (direct and inside assets/)
    if hasattr(sys, "executable") and sys.executable:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        for cand in (
            os.path.join(exe_dir, relative_path),
            os.path.join(exe_dir, "assets", relative_path),
        ):
            if os.path.exists(cand):
                return cand

    # 3. Current working directory (direct and inside assets/)
    try:
        cwd = os.getcwd()
        for cand in (
            os.path.join(cwd, relative_path),
            os.path.join(cwd, "assets", relative_path),
        ):
            if os.path.exists(cand):
                return cand
    except Exception:
        pass

    # 4. Relative to __file__ going up to 4 levels
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        for cand in (
            os.path.join(curr, relative_path),
            os.path.join(curr, "assets", relative_path),
        ):
            if os.path.exists(cand):
                return cand
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", relative_path)
    return fallback if os.path.exists(fallback) else os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def is_test_environment() -> bool:
    """Returns True ONLY when running inside an automated test suite."""
    if getattr(sys, "frozen", False):
        return False
    if os.environ.get("SD_TESTING") == "1":
        return True
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return True
    args = [arg.lower() for arg in sys.argv[:3]] if hasattr(sys, "argv") and sys.argv else []
    return any(
        arg.endswith(("pytest", "unittest"))
        or "unittest" in arg
        or "pytest" in arg
        or "test" in os.path.basename(arg)
        for arg in args
    )


def get_config_dir() -> str:
    """Returns persistent application configuration directory path."""
    cfg_override = os.environ.get("SD_CONFIG_DIR")
    if cfg_override:
        try:
            os.makedirs(cfg_override, exist_ok=True)
        except Exception:
            pass
        return cfg_override
    if is_test_environment():
        test_cfg = os.path.join(tempfile.gettempdir(), "sd_test_isolated_cfg")
        try:
            os.makedirs(test_cfg, exist_ok=True)
        except Exception:
            pass
        return test_cfg
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            cfg = os.path.join(appdata, "SmartDownload")
            legacy_cfg = os.path.join(appdata, "TurboDownloader")
            if os.path.isdir(legacy_cfg) and not os.path.exists(cfg):
                try:
                    shutil.copytree(legacy_cfg, cfg)
                except Exception:
                    pass
        else:
            cfg = os.path.join(os.path.expanduser("~"), ".smartdownload")
    else:
        cfg = os.path.join(os.path.expanduser("~"), ".smartdownload")
    try:
        os.makedirs(cfg, exist_ok=True)
    except Exception:
        pass
    return cfg

get_app_config_dir = get_config_dir

def get_settings_file_path() -> str:
    """Returns absolute path to persistent settings.json."""
    return os.path.join(get_config_dir(), "settings.json")

import threading

_settings_lock = threading.RLock()
_cached_settings_data: Optional[Dict[str, Any]] = None
_cached_stat_key: Optional[Tuple[str, int, int]] = None

def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """Atomically writes JSON dictionary to file path using a thread/process-unique temp file and os.replace."""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    tmp_path = f"{path}.tmp_{os.getpid()}_{threading.get_ident()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        try:
            os.replace(tmp_path, path)
        except Exception:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def _clear_settings_cache():
    """Explicitly invalidates the in-memory settings cache (useful during unit tests)."""
    global _cached_settings_data, _cached_stat_key
    with _settings_lock:
        _cached_settings_data = None
        _cached_stat_key = None

def load_settings() -> Dict[str, Any]:
    """Loads user configuration dictionary from settings.json with mtime-based in-memory caching."""
    path = get_settings_file_path()
    defaults = {
        "minimize_to_tray": True,
        "auto_categorize_folders": True,
        "language": "ar",
        "auto_unpack_archives": False,
        "max_connections": 8,
        "speed_limit_preset": "Unlimited",
        "custom_speed_limit_kbps": 0,
        "clipboard_sniffer_active": True,
        "startup_enabled": False,
        "last_download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "preferred_video_height": 0,
        "preferred_audio_lang": "original",
        "preferred_subtitle_lang": "none",
        "subtitle_embed_mode": "hard_burn",
        "subtitle_position": "bottom",
        "window_alpha": 0.92,
        "window_opacity": 0.92,
        "sniffer_platforms": dict(DEFAULT_SNIFFER_PLATFORMS),
    }

    with _settings_lock:
        global _cached_settings_data, _cached_stat_key
        try:
            st = os.stat(path)
            stat_key = (path, st.st_mtime_ns, st.st_size)
        except OSError:
            stat_key = (path, -1, -1)

        if _cached_stat_key == stat_key and _cached_settings_data is not None:
            return dict(_cached_settings_data)

        cur = dict(defaults)
        if stat_key[1] != -1:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if isinstance(data.get("sniffer_platforms"), dict):
                            merged_platforms = dict(DEFAULT_SNIFFER_PLATFORMS)
                            merged_platforms.update(data["sniffer_platforms"])
                            data["sniffer_platforms"] = merged_platforms
                        elif "sniffer_platforms" in data:
                            data["sniffer_platforms"] = dict(DEFAULT_SNIFFER_PLATFORMS)
                        cur.update(data)
            except Exception:
                pass

        # Auto-migrate stuck window_alpha (<= 0.72) from previous build
        try:
            val = cur.get("window_alpha")
            if val is not None and not cur.get("window_alpha_migrated_v202", False):
                if float(val) <= 0.72:
                    cur["window_alpha"] = 0.95
                    cur["window_opacity"] = 0.95
                    cur["window_alpha_migrated_v202"] = True
                    if stat_key[1] != -1:
                        try:
                            _atomic_write_json(path, cur)
                        except Exception:
                            pass
        except Exception:
            pass

        _cached_settings_data = cur
        _cached_stat_key = stat_key
        return dict(_cached_settings_data)

def save_settings(settings_dict: Dict[str, Any]) -> bool:
    """Persists updated configuration dictionary to settings.json and refreshes memory cache."""
    path = get_settings_file_path()
    try:
        with _settings_lock:
            global _cached_settings_data, _cached_stat_key
            cur = load_settings()
            cur.update(settings_dict)
            _atomic_write_json(path, cur)
            try:
                st = os.stat(path)
                stat_key = (path, st.st_mtime_ns, st.st_size)
            except OSError:
                stat_key = (path, -1, -1)
            _cached_settings_data = dict(cur)
            _cached_stat_key = stat_key
            return True
    except Exception:
        return False

def get_setting(key: str, default: Any = None) -> Any:
    """Retrieves a single setting value with fallback default."""
    return load_settings().get(key, default)

def set_setting(key: str, value: Any) -> bool:
    """Sets and persists a single setting value."""
    return save_settings({key: value})


def get_base_downloads_dir() -> str:
    """Returns the user's saved base download directory or defaults to ~/Downloads."""
    saved_dir = str(get_setting("last_download_dir", "") or "").strip()
    if saved_dir and os.path.isdir(saved_dir):
        return saved_dir
    return os.path.join(os.path.expanduser("~"), "Downloads")


def parse_safe_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely extracts a positive integer from int or str, while rejecting booleans and Mocks."""
    if isinstance(v, (int, str)) and not isinstance(v, bool):
        try:
            s = str(v).strip()
            if s.isdigit() and int(s) > 0:
                return int(s)
        except Exception:
            pass
    return default


