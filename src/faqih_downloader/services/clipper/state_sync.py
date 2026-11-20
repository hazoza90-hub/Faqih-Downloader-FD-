"""
state_sync.py: Preview/clipper state synchronization onto stream_info and clipped byte estimation.
"""
from __future__ import annotations
from typing import Dict, Any

from .cue_ops import clone_clean_subtitle_track


def sync_clipper_state_from_body(session: Any, body: Dict[str, Any], opt: Any = None) -> None:
    """Helper for preview_stream_bridge to sync live clipper, text edits, dual subs, audio boost, and chapters."""
    c_start, c_end = float(body.get("clip_start", getattr(session, "clip_start", 0.0) or 0.0)), float(body.get("clip_end", getattr(session, "clip_end", 0.0) or 0.0))
    edits, dual = dict(body.get("sub_custom_edits", getattr(session, "sub_custom_edits", {}) or {})), bool(body.get("dual_sub", getattr(session, "dual_sub", False)))
    s_idx, boost = int(body.get("sec_s_idx", getattr(session, "sec_s_idx", -1))), bool(body.get("audio_boost", getattr(session, "audio_boost", False)))
    ch_title, vid_dur = str(body.get("chapter_title", getattr(session, "chapter_title", "")) or "").strip(), float(body.get("duration", 0.0) or 0.0)
    if vid_dur <= 0 and isinstance(getattr(session, "info_dict", None), dict): vid_dur = float(session.info_dict.get("duration", 0.0) or 0.0)
    if vid_dur > 0 and isinstance(getattr(session, "info_dict", None), dict) and float(session.info_dict.get("duration", 0.0) or 0.0) <= 0: session.info_dict["duration"] = vid_dur

    session.clip_start, session.clip_end, session.sub_custom_edits = c_start, c_end, edits
    session.dual_sub, session.sec_s_idx, session.audio_boost, session.chapter_title = dual, s_idx, boost, ch_title

    sub_trks = getattr(session, "subtitle_tracks", None)
    if isinstance(sub_trks, list):
        for idx in range(len(sub_trks)):
            if isinstance(sub_trks[idx], dict): sub_trks[idx] = clone_clean_subtitle_track(sub_trks[idx])
    else: sub_trks = []
    sec_trk = None
    if dual and sub_trks:
        if 0 <= s_idx < len(sub_trks): sec_trk = clone_clean_subtitle_track(sub_trks[s_idx])
        else:
            for idx, trk in enumerate(sub_trks):
                if idx > 0 and (not getattr(session, "selected_sub_track", None) or trk != session.selected_sub_track):
                    sec_trk = clone_clean_subtitle_track(trk); break

    target_opts = list(getattr(session, "options", []) or [])
    m = getattr(session, "modal_ref", None)
    for cand in ([*(getattr(m, "options", []) or []), opt, getattr(m, "selected_option", None)] if m else [opt]):
        if cand and cand not in target_opts: target_opts.append(cand)
    from ..external_subtitle_service import sync_preview_external_subtitles
    sync_preview_external_subtitles(session, body, target_opts)

    for target_opt in target_opts:
        target_opt.clip_start_sec, target_opt.clip_end_sec = c_start, c_end
        target_opt.subtitle_custom_edits, target_opt.dual_subtitle_enabled = edits, dual
        target_opt.audio_boost_enabled, target_opt.selected_chapter_title = boost, ch_title
        if vid_dur > 0: setattr(target_opt, "duration", vid_dur)
        if sec_trk is not None or not dual: target_opt.secondary_subtitle_track = sec_trk
        st = getattr(target_opt, "selected_subtitle_track", None)
        if st and isinstance(st, dict):
            ex_st = dict(st.get("style_config", {})) if isinstance(st.get("style_config"), dict) else {}
            st = clone_clean_subtitle_track(st); target_opt.selected_subtitle_track = st
            sc = st.setdefault("style_config", ex_st)
            sc.update({"clip_start": c_start, "clip_end": c_end, "custom_edits": edits, "dual_sub": dual, "secondary_track": clone_clean_subtitle_track(sec_trk) if (dual and sec_trk) else None, "audio_boost": boost, "chapter_title": ch_title})
            if isinstance(sub_trks, list):
                tid = st.get("sub_id")
                for i, trk in enumerate(sub_trks):
                    if isinstance(trk, dict) and tid and trk.get("sub_id") == tid: sub_trks[i] = st; break


def enrich_stream_info_with_clip(stream_info: Any, opt: Any) -> Any:
    """Enriches YouTubeStreamInfo instance with clip range, dual subtitle, and audio boost configuration."""
    if opt and stream_info:
        for a, dv in (("clip_start_sec", 0.0), ("clip_end_sec", 0.0), ("subtitle_custom_edits", {}), ("dual_subtitle_enabled", False), ("secondary_subtitle_track", None), ("audio_boost_enabled", False), ("selected_chapter_title", "")):
            setattr(stream_info, a, getattr(opt, a, dv))
        setattr(stream_info, "external_subtitle_tracks", [clone_clean_subtitle_track(t) or t for t in (getattr(opt, "external_subtitle_tracks", None) or []) if isinstance(t, dict)])
        if getattr(stream_info, "duration", 0) <= 0 and getattr(opt, "duration", 0) > 0:
            stream_info.duration = float(opt.duration)
    return stream_info


def estimate_clip_total_bytes(stream_info: Any, full_total_bytes: int) -> int:
    """Calculates estimated byte size of the selected clip/chapter proportional to total media duration."""
    if not stream_info or full_total_bytes <= 0: return max(0, full_total_bytes)
    cs = float(stream_info.get("clip_start_sec", 0.0) if isinstance(stream_info, dict) else getattr(stream_info, "clip_start_sec", 0.0) or 0.0)
    ce = float(stream_info.get("clip_end_sec", 0.0) if isinstance(stream_info, dict) else getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
    dur = float(stream_info.get("duration", 0.0) if isinstance(stream_info, dict) else getattr(stream_info, "duration", 0.0) or 0.0)
    if ce > cs >= 0 and dur > 0 and (ce - cs) < dur - 0.5:
        return max(65536, int(full_total_bytes * max(0.03, min(1.0, (ce - cs) / dur))))
    return full_total_bytes


__all__ = [
    "sync_clipper_state_from_body",
    "enrich_stream_info_with_clip",
    "estimate_clip_total_bytes",
]
