"""
video_preview_modal.py: Thin backward-compatibility shim re-exporting symbols from ui.modals.preview.
"""
from .preview.process_launcher import (
    IS_WINDOWS,
    _ACTIVE_PREVIEW_PROC,
    _PreviewJsApi,
    terminate_active_preview_proc,
    _launch_webview_subprocess,
    _find_chromeless_browser,
)
from .preview.stream_selector import (
    _find_progressive_mp4_url,
    _convert_srt_to_vtt_data_uri,
)
from .preview.launcher import open_video_preview
from .preview_html_builder import generate_preview_html

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
    "generate_preview_html",
]
