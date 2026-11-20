"""
vtt_compiler.py: Compiles SRT subtitles to WebVTT and serves them over HTTP for preview playback.
"""
from __future__ import annotations

import http.server
import os
import re
import sys
import tempfile
from typing import Any

from ..subtitle_downloader import download_subtitle_as_srt


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


__all__ = ["compile_and_serve_vtt"]
