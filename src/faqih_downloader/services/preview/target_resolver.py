"""
target_resolver.py: Resolves upstream video and audio stream targets and headers for preview playback.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


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


__all__ = [
    "resolve_preview_video_target",
    "resolve_preview_audio_target",
]
