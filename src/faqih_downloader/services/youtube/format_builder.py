"""
YouTubeFormatBuilderMixin composition mixin combining format options and stream info builders.
"""
from .format_options_builder import YouTubeFormatOptionsBuilderMixin
from .stream_info_builder import YouTubeStreamInfoBuilderMixin


class YouTubeFormatBuilderMixin(YouTubeFormatOptionsBuilderMixin, YouTubeStreamInfoBuilderMixin):
    """Composition mixin uniting format options building and stream info resolution."""
    pass
