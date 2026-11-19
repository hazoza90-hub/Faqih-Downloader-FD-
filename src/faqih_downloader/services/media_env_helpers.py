"""
media_env_helpers.py: Thin backward-compatibility shim re-exporting symbols from services.media_env.
"""
from .media_env import (
    detect_installed_cookie_browsers,
    _resolve_cookie_browser,
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
    find_ffmpeg_bin,
    has_ffmpeg,
    probe_media_file_duration,
    probe_media_duration,
    recover_audio_stream_fallback,
    ensure_complete_audio_file,
    run_ffmpeg_with_progress,
)

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
