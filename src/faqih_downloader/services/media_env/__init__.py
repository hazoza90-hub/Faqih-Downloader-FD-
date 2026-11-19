"""
media_env package: System media environment, browser cookies, yt-dlp, FFmpeg, and audio recovery helpers.
"""
from .browser_cookies import (
    detect_installed_cookie_browsers,
    _resolve_cookie_browser,
)
from .ytdlp_env import (
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
)
from .ffmpeg_probe import (
    find_ffmpeg_bin,
    has_ffmpeg,
    probe_media_file_duration,
    probe_media_duration,
)
from .ffmpeg_runner import run_ffmpeg_with_progress
from .audio_recovery import (
    ensure_complete_audio_file,
    recover_audio_stream_fallback,
)

__all__ = [
    "detect_installed_cookie_browsers",
    "_resolve_cookie_browser",
    "is_ytdlp_available",
    "get_ytdlp_version",
    "update_ytdlp_engine",
    "find_ffmpeg_bin",
    "has_ffmpeg",
    "probe_media_file_duration",
    "probe_media_duration",
    "run_ffmpeg_with_progress",
    "ensure_complete_audio_file",
    "recover_audio_stream_fallback",
]
