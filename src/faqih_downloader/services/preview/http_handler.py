"""
http_handler.py: HTTP request handler routing player HTML, media streams, subtitles, and JSON APIs.
"""
from __future__ import annotations

import http.server
import json
import urllib.parse
from typing import Any, Dict, Optional

from .api_actions import PreviewActionApiMixin
from .api_files import PreviewFileApiMixin
from .api_state import PreviewStateApiMixin
from .origin_guard import _is_preview_origin_allowed, _safe_int
from .session_store import PreviewSession, get_preview_session
from .target_resolver import resolve_preview_audio_target, resolve_preview_video_target
from .upstream_streamer import stream_upstream_media
from .vtt_compiler import compile_and_serve_vtt


class PreviewBridgeRequestHandler(
    PreviewFileApiMixin,
    PreviewActionApiMixin,
    PreviewStateApiMixin,
    http.server.BaseHTTPRequestHandler,
):
    """Handles HTTP requests for player UI, media streaming proxy, subtitles, and control APIs."""
    timeout = 10.0

    def log_message(self, format, *args):
        """Silences standard HTTP server console logging to avoid test and UI noise."""
        pass

    def do_OPTIONS(self):
        """Responds to CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_HEAD(self):
        """Handles HEAD probe requests for media stream duration and byte range headers."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        sid = params.get("sid", [""])[0]
        session = get_preview_session(sid)
        if not session:
            self.send_response(404)
            self.end_headers()
            return

        if parsed.path == "/stream_video":
            q_idx = _safe_int(params.get("q_idx", ["0"])[0]) if params.get("q_idx") else 0
            a_idx = _safe_int(params.get("a_idx", ["0"])[0]) if params.get("a_idx") else None
            target_url, target_headers = self._resolve_video_target(session, q_idx, a_idx=a_idx)
            stream_upstream_media(self, target_url, target_headers, is_head=True)
        elif parsed.path == "/stream_audio":
            a_idx = _safe_int(params.get("a_idx", ["0"])[0]) if params.get("a_idx") else 0
            q_idx = _safe_int(params.get("q_idx", ["0"])[0]) if params.get("q_idx") else None
            target_url, target_headers = self._resolve_audio_target(session, a_idx, q_idx=q_idx)
            stream_upstream_media(self, target_url, target_headers, is_head=True)
        else:
            self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()

    def do_GET(self):
        """Dispatches GET requests for player HTML, video stream, audio stream, or subtitles."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        sid = params.get("sid", [""])[0]
        session = get_preview_session(sid)

        if not session:
            self.send_response(404); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
            self.wfile.write(b"404 Session Not Found or Expired")
            return

        if parsed.path == "/player": self._handle_player(session)
        elif parsed.path == "/stream_video":
            q_idx = _safe_int(params.get("q_idx", ["0"])[0]) if params.get("q_idx") else 0
            a_idx = _safe_int(params.get("a_idx", ["0"])[0]) if params.get("a_idx") else None
            t_url, t_hdrs = self._resolve_video_target(session, q_idx, a_idx=a_idx)
            stream_upstream_media(self, t_url, t_hdrs, is_head=False)
        elif parsed.path == "/stream_audio":
            a_idx = _safe_int(params.get("a_idx", ["0"])[0]) if params.get("a_idx") else 0
            q_idx = _safe_int(params.get("q_idx", ["0"])[0]) if params.get("q_idx") else None
            t_url, t_hdrs = self._resolve_audio_target(session, a_idx, q_idx=q_idx)
            stream_upstream_media(self, t_url, t_hdrs, is_head=False)
        elif parsed.path == "/subtitle.vtt":
            s_idx = _safe_int(params.get("s_idx", ["0"])[0]) if params.get("s_idx") else 0
            self._handle_subtitle(session, s_idx)
        else: self.send_response(404); self.end_headers()

    def _send_json(self, data: Dict[str, Any], code: int = 200) -> None:
        """Sends JSON HTTP response with CORS headers."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        """Dispatches JSON POST API calls for dynamic filename tagging or confirmed action."""
        if not _is_preview_origin_allowed(self.headers.get("Origin", "")):
            self.send_response(403); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
            self.wfile.write(b'{"ok": false, "error": "Forbidden: Untrusted Origin"}'); return

        parsed = urllib.parse.urlparse(self.path); params = urllib.parse.parse_qs(parsed.query)
        session = get_preview_session(params.get("sid", [""])[0])
        if not session: self.send_response(404); self.end_headers(); return
        content_len = _safe_int(self.headers.get("Content-Length", 0))
        if content_len > 65536: self._send_json({"ok": False, "error": "Payload too large"}, code=413); return
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try: body = json.loads(raw_body)
        except Exception: body = {}

        if parsed.path == "/api/update_filename": self._handle_api_update_filename(session, body)
        elif parsed.path == "/api/action": self._handle_api_action(session, body)
        elif parsed.path == "/api/sync_state": self._handle_api_sync_state(session, body)
        elif parsed.path == "/api/browse": self._handle_api_browse(session, body, params)
        else: self.send_response(404); self.end_headers()

    def _resolve_video_target(self, session: PreviewSession, q_idx: int, a_idx: Optional[int] = None) -> tuple[str, Dict[str, str]]:
        return resolve_preview_video_target(session, q_idx, a_idx=a_idx)

    def _resolve_audio_target(self, session: PreviewSession, a_idx: int, q_idx: Optional[int] = None) -> tuple[str, Dict[str, str]]:
        """Finds the dedicated audio stream URL and headers for dubbed or fallback audio playback."""
        return resolve_preview_audio_target(session, a_idx, q_idx=q_idx)

    def _handle_player(self, session: PreviewSession) -> None:
        """Renders and serves the complete unified VidMate-style preview and settings HTML page."""
        from ...ui.modals.preview_html_builder import generate_preview_html
        from . import bridge_server
        idx = session.selected_q_idx if 0 <= session.selected_q_idx < len(session.options) else 0
        opt = session.options[idx] if session.options else None
        q_label = getattr(opt, "resolution_label", "MP4 Stream") if opt else "MP4 Stream"
        stream_proxy_url = f"/stream_video?sid={session.sid}&q_idx={idx}"
        initial_dub_url = None
        if session.selected_audio_track and session.selected_audio_track.get("track_id") not in (None, "original"):
            a_idx = 0
            if session.audio_tracks:
                for i, trk in enumerate(session.audio_tracks):
                    if trk == session.selected_audio_track or (trk.get("track_id") and trk.get("track_id") == session.selected_audio_track.get("track_id")):
                        a_idx = i; break
            initial_dub_url = f"/stream_audio?sid={session.sid}&a_idx={a_idx}&q_idx={idx}"
        else:
            fallback_audio, _ = self._resolve_audio_target(session, 0, q_idx=idx)
            if fallback_audio:
                initial_dub_url = f"/stream_audio?sid={session.sid}&a_idx=0&q_idx={idx}"
        html_code = generate_preview_html(
            url=session.url, video_title=session.video_title, stream_url=stream_proxy_url,
            quality_label=q_label, options=session.options, audio_tracks=session.audio_tracks,
            subtitle_tracks=session.subtitle_tracks, default_dest_path=session.default_dest_path,
            sid=session.sid, bridge_port=bridge_server._BRIDGE_PORT, selected_audio_track=session.selected_audio_track,
            selected_sub_track=session.selected_sub_track, subtitle_embed_mode=session.subtitle_embed_mode,
            selected_q_idx=idx, subtitle_position=session.subtitle_position, dub_audio_url=initial_dub_url,
            subtitle_preset=session.subtitle_preset, subtitle_font_scale=session.subtitle_font_scale,
            subtitle_text_color=session.subtitle_text_color, subtitle_bg_mode=session.subtitle_bg_mode,
            subtitle_pos_x=session.subtitle_pos_x, subtitle_pos_y=session.subtitle_pos_y,
            clip_start=session.clip_start, clip_end=session.clip_end, dual_sub=session.dual_sub,
            audio_boost=getattr(session, "audio_boost", False), chapters=getattr(session, "chapters", None),
            chapter_title=getattr(session, "chapter_title", ""), external_subtitle_tracks=getattr(session, "external_subtitle_tracks", []),
        )
        data = html_code.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _handle_subtitle(self, session: PreviewSession, s_idx: int) -> None:
        """Asynchronously compiles and serves WebVTT subtitles on the background HTTP worker thread."""
        compile_and_serve_vtt(self, session, s_idx)


__all__ = ["PreviewBridgeRequestHandler"]
