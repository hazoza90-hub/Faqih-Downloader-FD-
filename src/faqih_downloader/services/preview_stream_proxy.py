"""
preview_stream_proxy.py: Thin backward-compatibility shim re-exporting symbols from services.preview.
"""
from .preview.origin_guard import _safe_int, _is_preview_origin_allowed
from .preview.session_store import _prune_preview_sessions
from .preview.target_resolver import resolve_preview_video_target, resolve_preview_audio_target
from .preview.upstream_streamer import _open_window_stream, stream_upstream_media
from .preview.local_proxy import PreviewStreamBridge
from .preview.vtt_compiler import compile_and_serve_vtt

__all__ = [
    "_safe_int",
    "_is_preview_origin_allowed",
    "_prune_preview_sessions",
    "resolve_preview_video_target",
    "resolve_preview_audio_target",
    "_open_window_stream",
    "stream_upstream_media",
    "PreviewStreamBridge",
    "compile_and_serve_vtt",
]
