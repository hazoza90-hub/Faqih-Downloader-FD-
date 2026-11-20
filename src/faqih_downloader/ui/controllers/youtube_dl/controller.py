"""
YouTubeDownloadControllerMixin: Composite mixin combining format extraction flow and stream launcher.
"""
from .extraction_flow import YouTubeExtractionFlowMixin
from .stream_launcher import YouTubeStreamLauncherMixin


class YouTubeDownloadControllerMixin(YouTubeExtractionFlowMixin, YouTubeStreamLauncherMixin):
    """Handles YouTube & social media stream format analysis, quality dialogs, and stream coordinators."""
    pass


__all__ = ["YouTubeDownloadControllerMixin"]
