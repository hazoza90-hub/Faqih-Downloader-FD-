"""
Backward-compatibility shim for youtube_service.
All YouTube/media resolver logic now lives in faqih_downloader.services.youtube.
"""
from ..core.chunk import get_permissive_ssl_context
from .updater_service import APP_VERSION, YtDlpAutoUpdater, get_ytdlp_plugin_dir
from .media_env_helpers import run_ffmpeg_with_progress
from .youtube_models import (
    YOUTUBE_URL_REGEX,
    SOCIAL_MEDIA_PATTERNS,
    INVALID_FILENAME_CHARS,
    SUPPORTED_COOKIE_BROWSERS,
    PLATFORM_DISPLAY_NAMES,
    detect_installed_cookie_browsers,
    is_youtube_url,
    is_social_media_url,
    _is_direct_download_url,
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
    is_ytdlp_extractor_supported,
    is_media_url,
    extract_media_platform,
    extract_media_id,
    extract_youtube_id,
    find_ffmpeg_bin,
    has_ffmpeg,
    sanitize_filename,
    VideoFormatOption,
    format_filesize,
    YouTubeStreamInfo,
    MediaStreamInfo,
    resolve_preferred_option_index,
)
from .youtube_format_builder import YouTubeFormatBuilderMixin
from .youtube.resolver import YouTubeResolver, MediaResolver

__all__ = [
    "APP_VERSION",
    "YtDlpAutoUpdater",
    "get_ytdlp_plugin_dir",
    "get_permissive_ssl_context",
    "run_ffmpeg_with_progress",
    "YOUTUBE_URL_REGEX",
    "SOCIAL_MEDIA_PATTERNS",
    "INVALID_FILENAME_CHARS",
    "SUPPORTED_COOKIE_BROWSERS",
    "PLATFORM_DISPLAY_NAMES",
    "detect_installed_cookie_browsers",
    "is_youtube_url",
    "is_social_media_url",
    "_is_direct_download_url",
    "is_ytdlp_available",
    "get_ytdlp_version",
    "update_ytdlp_engine",
    "is_ytdlp_extractor_supported",
    "is_media_url",
    "extract_media_platform",
    "extract_media_id",
    "extract_youtube_id",
    "find_ffmpeg_bin",
    "has_ffmpeg",
    "sanitize_filename",
    "VideoFormatOption",
    "format_filesize",
    "YouTubeStreamInfo",
    "MediaStreamInfo",
    "resolve_preferred_option_index",
    "YouTubeFormatBuilderMixin",
    "YouTubeResolver",
    "MediaResolver",
]
