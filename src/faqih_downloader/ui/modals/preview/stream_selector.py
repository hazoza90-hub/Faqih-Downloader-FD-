"""
stream_selector.py: Progressive MP4 preview stream selection and SRT-to-VTT data URI conversion.
"""
from __future__ import annotations

import base64
import re
from typing import Any, Dict, Optional


def _find_progressive_mp4_url(
    stream_info: Optional[Any],
    info_dict: Optional[Dict[str, Any]],
    source_url: str = ""
) -> Optional[str]:
    """Finds direct playable progressive MP4 stream (e.g. format 18/22 or direct URL)."""
    if stream_info is not None:
        url_val = getattr(stream_info, "video_url", None) or getattr(stream_info, "url", None)
        is_prog = getattr(stream_info, "is_progressive", False)
        ext_val = getattr(stream_info, "ext", getattr(stream_info, "video_ext", "mp4"))
        if url_val and is_prog and str(ext_val).lower() == "mp4":
            return str(url_val)

    if isinstance(info_dict, dict):
        formats = info_dict.get("formats") or []
        prog_formats = [
            f for f in formats
            if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
            and str(f.get("ext") or "").lower() == "mp4"
        ]
        if prog_formats:
            prog_formats.sort(key=lambda f: int(f.get("height") or 0), reverse=True)
            fast_candidates = [f for f in prog_formats if int(f.get("height") or 0) <= 720]
            chosen = fast_candidates[0] if fast_candidates else prog_formats[0]
            return str(chosen.get("url") or "")

    clean_u = (source_url or "").split("?")[0].lower()
    if clean_u.endswith((".mp4", ".m4v", ".webm")):
        return source_url

    return None


def _convert_srt_to_vtt_data_uri(srt_content: str) -> Optional[str]:
    """Converts raw SRT text into a base64 data:text/vtt URI for HTML5 <track>."""
    if not srt_content or "-->" not in srt_content:
        return None
    vtt_body = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_content.strip())
    if not vtt_body.startswith("WEBVTT"):
        vtt_body = "WEBVTT\n\n" + vtt_body
    b64 = base64.b64encode(vtt_body.encode("utf-8")).decode("ascii")
    return f"data:text/vtt;charset=utf-8;base64,{b64}"


__all__ = [
    "_find_progressive_mp4_url",
    "_convert_srt_to_vtt_data_uri",
]
