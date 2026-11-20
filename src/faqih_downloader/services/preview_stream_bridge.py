"""
preview_stream_bridge.py: Thin backward-compatibility shim re-exporting symbols from services.preview.
"""
from .subtitle_downloader import download_subtitle_as_srt
from .preview.session_store import (
    PreviewSession,
    _SESSIONS_LOCK,
    _SESSIONS,
    _prune_preview_sessions,
    register_preview_session,
    get_preview_session,
    unregister_preview_session,
    _apply_session_sub_styles,
)
from .preview.origin_guard import _safe_int, _is_preview_origin_allowed
from .preview.target_resolver import resolve_preview_video_target, resolve_preview_audio_target
from .preview.upstream_streamer import stream_upstream_media
from .preview.local_proxy import PreviewStreamBridge
from .preview.vtt_compiler import compile_and_serve_vtt
from .preview.tk_dispatch import _schedule_on_tk
from .preview.http_handler import PreviewBridgeRequestHandler
from .preview.bridge_server import (
    _SERVER_LOCK,
    _BRIDGE_SERVER,
    _BRIDGE_PORT,
    start_preview_bridge,
    get_preview_bridge_port,
)

__all__ = [
    "PreviewSession",
    "_SERVER_LOCK",
    "_BRIDGE_SERVER",
    "_BRIDGE_PORT",
    "_SESSIONS_LOCK",
    "_SESSIONS",
    "start_preview_bridge",
    "get_preview_bridge_port",
    "register_preview_session",
    "get_preview_session",
    "unregister_preview_session",
    "_apply_session_sub_styles",
    "_schedule_on_tk",
    "PreviewBridgeRequestHandler",
    "download_subtitle_as_srt",
    "compile_and_serve_vtt",
    "stream_upstream_media",
    "_safe_int",
    "_is_preview_origin_allowed",
    "_prune_preview_sessions",
    "resolve_preview_video_target",
    "resolve_preview_audio_target",
    "PreviewStreamBridge",
]
