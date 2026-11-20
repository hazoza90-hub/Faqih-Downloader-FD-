"""
Backward-compatibility shim for youtube_models.
All YouTube/media constants, URL matchers, and stream models now live in faqih_downloader.services.youtube.
"""
from ..config import is_test_environment
from .updates.ytdlp_manager import YtDlpAutoUpdater
from .media_env_helpers import (
    detect_installed_cookie_browsers,
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
    find_ffmpeg_bin,
    has_ffmpeg,
)
from .youtube.constants import (
    YOUTUBE_URL_REGEX,
    SOCIAL_MEDIA_PATTERNS,
    INVALID_FILENAME_CHARS,
    SUPPORTED_COOKIE_BROWSERS,
    PLATFORM_DISPLAY_NAMES,
)
from .youtube.url_matcher import (
    _CACHED_YTDLP_EXTRACTORS,
    _YTDLP_EXTRACTORS_CACHE,
    is_youtube_url,
    is_social_media_url,
    _is_direct_download_url,
    is_ytdlp_extractor_supported,
    is_media_url,
    extract_media_platform,
    extract_media_id,
    extract_youtube_id,
)
from .youtube.models import (
    sanitize_filename,
    VideoFormatOption,
    format_filesize,
    YouTubeStreamInfo,
    MediaStreamInfo,
    resolve_preferred_option_index,
)

__all__ = [
    "is_test_environment",
    "YtDlpAutoUpdater",
    "YOUTUBE_URL_REGEX",
    "SOCIAL_MEDIA_PATTERNS",
    "INVALID_FILENAME_CHARS",
    "SUPPORTED_COOKIE_BROWSERS",
    "PLATFORM_DISPLAY_NAMES",
    "detect_installed_cookie_browsers",
    "is_ytdlp_available",
    "get_ytdlp_version",
    "update_ytdlp_engine",
    "find_ffmpeg_bin",
    "has_ffmpeg",
    "_CACHED_YTDLP_EXTRACTORS",
    "_YTDLP_EXTRACTORS_CACHE",
    "is_youtube_url",
    "is_social_media_url",
    "_is_direct_download_url",
    "is_ytdlp_extractor_supported",
    "is_media_url",
    "extract_media_platform",
    "extract_media_id",
    "extract_youtube_id",
    "sanitize_filename",
    "VideoFormatOption",
    "format_filesize",
    "YouTubeStreamInfo",
    "MediaStreamInfo",
    "resolve_preferred_option_index",
]
