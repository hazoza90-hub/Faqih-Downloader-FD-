"""
YouTubeResolver (alias MediaResolver): orchestrator class composing extraction,
TikTok fallback, format building, and FFmpeg stream merging.
"""
from typing import Optional, Callable, Any

from .format_extractor import YouTubeFormatExtractorMixin
from .tiktok_fallback import TikTokFallbackMixin
from .merger import YouTubeStreamMergerMixin
from ..youtube_format_builder import YouTubeFormatBuilderMixin


class YouTubeResolver(
    YouTubeFormatExtractorMixin,
    TikTokFallbackMixin,
    YouTubeStreamMergerMixin,
    YouTubeFormatBuilderMixin,
):
    """
    High-level resolver that communicates with yt-dlp to extract high-speed direct
    stream URLs, extracts all available video qualities/formats, and orchestrates
    video + audio merging with FFmpeg for YouTube and social media platforms.
    """

    def __init__(
        self, on_log: Optional[Callable[[str], None]] = None, socket_timeout: int = 12,
        auto_update_on_failure: bool = True, cookies_from_browser: Optional[str] = "auto",
        cookies_file: Optional[str] = None
    ):
        self.on_log = on_log
        self.socket_timeout = max(1, int(socket_timeout))
        self.auto_update_on_failure = bool(auto_update_on_failure)
        self.cookies_from_browser, self.cookies_file = cookies_from_browser, cookies_file

    def log(self, message: str):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass

    def extract_stream_info(self, url: str) -> Any:
        return self.resolve(url)

    def extract_info(self, url: str) -> Any:
        return self.resolve(url)


# Backward-compatible alias for universal media resolution
MediaResolver = YouTubeResolver
