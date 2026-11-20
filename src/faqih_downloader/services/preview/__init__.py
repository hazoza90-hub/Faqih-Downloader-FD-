"""
preview package: In-memory preview bridge, HTTP stream proxy, session store, VTT compiler, and API handlers.
"""
from .session_store import (
    PreviewSession,
    _SESSIONS_LOCK,
    _SESSIONS,
    _prune_preview_sessions,
    register_preview_session,
    get_preview_session,
    unregister_preview_session,
    _apply_session_sub_styles,
)
from .origin_guard import _safe_int, _is_preview_origin_allowed
from .target_resolver import resolve_preview_video_target, resolve_preview_audio_target
from .upstream_streamer import _open_window_stream, stream_upstream_media
from .local_proxy import PreviewStreamBridge
from .vtt_compiler import compile_and_serve_vtt
from .tk_dispatch import _schedule_on_tk
from .api_files import PreviewFileApiMixin
from .api_actions import PreviewActionApiMixin
from .api_state import PreviewStateApiMixin
from .http_handler import PreviewBridgeRequestHandler
from .bridge_server import (
    _SERVER_LOCK,
    _BRIDGE_SERVER,
    _BRIDGE_PORT,
    start_preview_bridge,
    get_preview_bridge_port,
)

__all__ = [
    "PreviewSession",
    "_SESSIONS_LOCK",
    "_SESSIONS",
    "_prune_preview_sessions",
    "register_preview_session",
    "get_preview_session",
    "unregister_preview_session",
    "_apply_session_sub_styles",
    "_safe_int",
    "_is_preview_origin_allowed",
    "resolve_preview_video_target",
    "resolve_preview_audio_target",
    "_open_window_stream",
    "stream_upstream_media",
    "PreviewStreamBridge",
    "compile_and_serve_vtt",
    "_schedule_on_tk",
    "PreviewFileApiMixin",
    "PreviewActionApiMixin",
    "PreviewStateApiMixin",
    "PreviewBridgeRequestHandler",
    "_SERVER_LOCK",
    "_BRIDGE_SERVER",
    "_BRIDGE_PORT",
    "start_preview_bridge",
    "get_preview_bridge_port",
]
