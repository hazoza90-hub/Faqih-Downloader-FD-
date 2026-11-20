"""
Backward-compatibility shim for YouTubeFormatBuilderMixin.
Re-exports functionality from faqih_downloader.services.youtube.*
"""
from .youtube_models import (
    VideoFormatOption,
    YouTubeStreamInfo,
    has_ffmpeg,
    extract_media_platform,
    extract_youtube_id,
    extract_media_id,
    sanitize_filename,
)
from .youtube import (
    get_format_client_tier,
    YouTubeFormatOptionsBuilderMixin,
    YouTubeStreamInfoBuilderMixin,
    YouTubeFormatBuilderMixin,
)

__all__ = [
    "get_format_client_tier",
    "YouTubeFormatOptionsBuilderMixin",
    "YouTubeStreamInfoBuilderMixin",
    "YouTubeFormatBuilderMixin",
    "has_ffmpeg",
    "VideoFormatOption",
    "YouTubeStreamInfo",
    "extract_media_platform",
    "extract_youtube_id",
    "extract_media_id",
    "sanitize_filename",
]
