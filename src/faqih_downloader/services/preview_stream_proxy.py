"""
Smart Download — Preview Stream Proxy & VTT Subtitle Compiler
Handles upstream media byte-range proxying and WebVTT subtitle delivery.
"""

from __future__ import annotations

import http.server
import os
import re
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict

from ..core.chunk import get_permissive_ssl_context
from .subtitle_downloader import download_subtitle_as_srt


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely converts value to int, returning default on ValueError or TypeError."""
    try:
        if val is None:
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _is_preview_origin_allowed(origin: str) -> bool:
    """Validates that origin is empty (non-browser) or local (127.0.0.1 or localhost)."""
    if not origin:
        return True
    origin = origin.strip().lower()
    if origin.startswith(("http://", "https://")):
        return (
            origin.startswith("http://127.0.0.1")
            or origin.startswith("https://127.0.0.1")
            or origin.startswith("http://localhost")
            or origin.startswith("https://localhost")
        )
    return False


def _prune_preview_sessions(sessions: dict, max_sessions: int = 15) -> None:
    """Prunes oldest preview sessions to keep memory usage strictly bounded."""
    if not isinstance(sessions, dict):
        return
    while len(sessions) > max_sessions:
        try:
            oldest_key = next(iter(sessions))
            del sessions[oldest_key]
        except (StopIteration, KeyError):
            break


def resolve_preview_video_target(session: Any, q_idx: int, a_idx: Optional[int] = None) -> tuple[str, Dict[str, str]]:
    """Resolves the video stream URL and headers for preview playback."""
    opt = session.options[q_idx] if 0 <= q_idx < len(session.options) else (session.options[0] if session.options else None)
    if opt and getattr(opt, "is_audio_only", False):
        aud_u = getattr(opt, "audio_url", None) or getattr(opt, "video_url", None)
        if aud_u:
            aud_h = getattr(opt, "audio_headers", None) or getattr(opt, "video_headers", None) or {}
            return str(aud_u), dict(aud_h or {})

    dub_active = (a_idx > 0) if a_idx is not None else bool(session.selected_audio_track and session.selected_audio_track.get("track_id") not in (None, "original") and session.selected_audio_track.get("url"))
    if a_idx is not None and session.audio_tracks and 0 <= a_idx < len(session.audio_tracks):
        cur_aud = session.audio_tracks[a_idx]
        dub_active = bool(cur_aud and cur_aud.get("track_id") not in (None, "original") and cur_aud.get("url"))

    formats = session.info_dict.get("formats") or []
    prog_formats = [f for f in formats if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none" and str(f.get("ext") or "").lower() == "mp4"]

    if opt and getattr(opt, "is_progressive", False) and getattr(opt, "video_url", None):
        return str(opt.video_url), dict(getattr(opt, "video_headers", {}) or {})

    if opt and getattr(opt, "video_url", None) and (dub_active or getattr(opt, "audio_url", None)):
        return str(opt.video_url), dict(getattr(opt, "video_headers", {}) or {})

    target_h = int(getattr(opt, "height", 0) or 720) if opt else 720
    if prog_formats and not dub_active:
        chosen = min(prog_formats, key=lambda f: abs(int(f.get("height") or 0) - target_h))
        headers = dict(chosen.get("http_headers") or {})
        if "Referer" not in headers and session.url: headers["Referer"] = session.url
        return str(chosen.get("url") or ""), headers

    if opt and getattr(opt, "video_url", None):
        return str(opt.video_url), dict(getattr(opt, "video_headers", {}) or {})

    headers = dict(session.info_dict.get("http_headers") or {})
    if "Referer" not in headers and session.url: headers["Referer"] = session.url
    return session.url, headers


def resolve_preview_audio_target(session: Any, a_idx: int, q_idx: Optional[int] = None) -> tuple[str, Dict[str, str]]:
    """Finds the dedicated audio stream URL and headers for dubbed or fallback audio playback."""
    track = session.audio_tracks[a_idx] if 0 <= a_idx < len(session.audio_tracks) else None
    if not track or not track.get("url") or track.get("track_id") == "original":
        idx = q_idx if (q_idx is not None and 0 <= q_idx < len(session.options)) else (session.selected_q_idx if 0 <= session.selected_q_idx < len(session.options) else 0)
        opt = session.options[idx] if session.options else None
        if opt and not getattr(opt, "is_progressive", False):
            cand_url = getattr(opt, "audio_url", None) or (track.get("url") if track else "")
            if cand_url:
                headers = dict(getattr(opt, "audio_headers", {}) or {})
                if not headers and track: headers = dict(track.get("http_headers") or {})
                if not headers: headers = dict(session.info_dict.get("http_headers") or {})
                if "Referer" not in headers and session.url: headers["Referer"] = session.url
                return str(cand_url), headers
        return "", {}
    headers = dict(track.get("http_headers") or {})
    if not headers: headers = dict(session.info_dict.get("http_headers") or {})
    if "Referer" not in headers and session.url: headers["Referer"] = session.url
    return str(track.get("url") or ""), headers


def stream_upstream_media(
    handler: http.server.BaseHTTPRequestHandler,
    target_url: str,
    custom_headers: Dict[str, str],
    is_head: bool = False,
) -> None:
    """
    Forwards Range requests and essential HTTP headers upstream,
    proxying chunks back to the browser with 206 Partial Content / 200 OK.
    """
    if not target_url or not target_url.startswith("http"):
        handler.send_response(404)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return

    req = urllib.request.Request(target_url)
    ua = (
        custom_headers.get("User-Agent")
        or custom_headers.get("user-agent")
        or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    req.add_header("User-Agent", ua)
    for k, v in custom_headers.items():
        if k.lower() not in ("host", "user-agent", "range"):
            req.add_header(k, str(v))

    client_range = handler.headers.get("Range")
    if client_range:
        req.add_header("Range", client_range)

    ctx = get_permissive_ssl_context()
    try:
        upstream = urllib.request.urlopen(req, timeout=18, context=ctx)
        code = upstream.getcode() or 200
    except urllib.error.HTTPError as err:
        handler.send_response(err.code)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return
    except Exception:
        handler.send_response(502)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return

    try:
        handler.send_response(code)
        headers = [
            ("Content-Type", upstream.headers.get("Content-Type", "video/mp4")),
            ("Content-Length", upstream.headers.get("Content-Length")),
            ("Content-Range", upstream.headers.get("Content-Range")),
            ("Accept-Ranges", "bytes"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "*"),
            ("Cache-Control", "no-cache"),
        ]
        for h, v in headers:
            if v:
                handler.send_header(h, v)
        handler.end_headers()
        if is_head:
            return

        chunk_size = 64 * 1024
        while True:
            chunk = upstream.read(chunk_size)
            if not chunk:
                break
            handler.wfile.write(chunk)
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
        pass
    finally:
        try:
            upstream.close()
        except Exception:
            pass


def compile_and_serve_vtt(handler: http.server.BaseHTTPRequestHandler, session: Any, s_idx: int) -> None:
    """Asynchronously compiles and serves WebVTT subtitles on the background HTTP worker thread."""
    if s_idx in session.cached_subtitles:
        vtt_content = session.cached_subtitles[s_idx]
    else:
        track = session.subtitle_tracks[s_idx] if 0 <= s_idx < len(session.subtitle_tracks) else None
        if not track or track.get("sub_id") in (None, "none"):
            vtt_content = "WEBVTT\n\n"
        else:
            temp_stem = os.path.join(tempfile.gettempdir(), f"_sd_prev_{session.sid}_{s_idx}_{os.getpid()}")
            import sys
            bridge_mod = sys.modules.get("faqih_downloader.services.preview_stream_bridge")
            dl_fn = getattr(bridge_mod, "download_subtitle_as_srt", download_subtitle_as_srt) if bridge_mod else download_subtitle_as_srt
            srt_path = dl_fn(track, f"{temp_stem}.mp4")
            if srt_path and os.path.isfile(srt_path):
                with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as sf:
                    srt_text = sf.read()
                for f_p in (srt_path, f"{temp_stem}.srt"):
                    try:
                        if os.path.exists(f_p):
                            os.remove(f_p)
                    except Exception:
                        pass
                vtt_body = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_text.strip())
                if not vtt_body.startswith("WEBVTT"):
                    vtt_body = "WEBVTT\n\n" + vtt_body
                vtt_content = vtt_body
            else:
                vtt_content = "WEBVTT\n\n"
        session.cached_subtitles[s_idx] = vtt_content

    data = vtt_content.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/vtt; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(data)
