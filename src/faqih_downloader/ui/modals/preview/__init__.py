"""
preview package: Video preview launcher, process management, stream selector, clipper studio, and subtitle studio assets.
"""
from .process_launcher import (
    IS_WINDOWS,
    _ACTIVE_PREVIEW_PROC,
    _PreviewJsApi,
    terminate_active_preview_proc,
    _launch_webview_subprocess,
    _find_chromeless_browser,
)
from .stream_selector import (
    _find_progressive_mp4_url,
    _convert_srt_to_vtt_data_uri,
)
from .launcher import open_video_preview
from .clipper_css import get_clipper_css
from .clipper_html import get_clipper_toolbar_html
from .clipper_js import get_clipper_js
from .subtitle_studio_css import get_studio_css
from .subtitle_studio_html import get_studio_toolbar_html
from .subtitle_studio_js import get_studio_js

__all__ = [
    "IS_WINDOWS",
    "_ACTIVE_PREVIEW_PROC",
    "_PreviewJsApi",
    "terminate_active_preview_proc",
    "_launch_webview_subprocess",
    "_find_chromeless_browser",
    "_find_progressive_mp4_url",
    "_convert_srt_to_vtt_data_uri",
    "open_video_preview",
    "get_clipper_css",
    "get_clipper_toolbar_html",
    "get_clipper_js",
    "get_studio_css",
    "get_studio_toolbar_html",
    "get_studio_js",
]
