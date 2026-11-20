"""
YouTube package: constants, URL matchers, stream models, extractors, format builders, and resolver.
"""
from .constants import (
    YOUTUBE_URL_REGEX,
    SOCIAL_MEDIA_PATTERNS,
    INVALID_FILENAME_CHARS,
    SUPPORTED_COOKIE_BROWSERS,
    PLATFORM_DISPLAY_NAMES,
)
from .url_matcher import (
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
from .models import (
    sanitize_filename,
    VideoFormatOption,
    format_filesize,
    YouTubeStreamInfo,
    MediaStreamInfo,
    resolve_preferred_option_index,
)
from .client_tier import get_format_client_tier
from .format_options_builder import YouTubeFormatOptionsBuilderMixin
from .stream_info_builder import YouTubeStreamInfoBuilderMixin
from .format_builder import YouTubeFormatBuilderMixin
from .tiktok_fallback import TikTokFallbackMixin
from .format_extractor import YouTubeFormatExtractorMixin
from .merger import YouTubeStreamMergerMixin


def __getattr__(name: str):
    if name in ("YouTubeResolver", "MediaResolver"):
        from .resolver import YouTubeResolver, MediaResolver
        globals()["YouTubeResolver"] = YouTubeResolver
        globals()["MediaResolver"] = MediaResolver
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals().keys()) | {"YouTubeResolver", "MediaResolver"})

__all__ = [
    "YOUTUBE_URL_REGEX",
    "SOCIAL_MEDIA_PATTERNS",
    "INVALID_FILENAME_CHARS",
    "SUPPORTED_COOKIE_BROWSERS",
    "PLATFORM_DISPLAY_NAMES",
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
    "get_format_client_tier",
    "YouTubeFormatOptionsBuilderMixin",
    "YouTubeStreamInfoBuilderMixin",
    "YouTubeFormatBuilderMixin",
    "TikTokFallbackMixin",
    "YouTubeFormatExtractorMixin",
    "YouTubeStreamMergerMixin",
    "YouTubeResolver",
    "MediaResolver",
]
