"""
post_pipeline.py: Post-download subtitle preparation and clip/subtitle/audio-boost orchestration.
"""
from __future__ import annotations
import os
import re
import sys
import time
from typing import Optional, Callable, Any

from .cue_ops import (
    apply_custom_cue_edits,
    clone_clean_subtitle_track,
    filter_and_shift_cues_for_clip,
    merge_bilingual_cues,
    export_cues_to_srt,
)
from .trimmer import trim_media_file
from ..media_env.ffmpeg_probe import probe_media_duration


def prepare_post_download_subtitles(stream_info: Any, srt_path: str, orig_stem: str) -> None:
    """Pre-processes downloaded SRT file with custom edits, dual subs, and clip shifts."""
    if not srt_path or not os.path.isfile(srt_path): return
    try:
        from ..subtitle_style_engine import _parse_srt_text_to_cues, normalize_and_dedupe_cues
        with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f: cues = _parse_srt_text_to_cues(f.read())
        if not cues: return
        cues = normalize_and_dedupe_cues(cues)
        edits = getattr(stream_info, "subtitle_custom_edits", None) or {}
        if edits: cues = apply_custom_cue_edits(cues, edits)

        sec_trk = getattr(stream_info, "secondary_subtitle_track", None)
        dual_sub = getattr(stream_info, "dual_subtitle_enabled", False)
        if dual_sub and sec_trk and isinstance(sec_trk, dict) and (sec_trk.get("url") or sec_trk.get("base_url")):
            from ..subtitle_downloader import download_subtitle_as_srt
            sec_srt = download_subtitle_as_srt(sec_trk, f"{orig_stem}.sec.srt")
            if sec_srt and os.path.isfile(sec_srt):
                with open(sec_srt, "r", encoding="utf-8-sig", errors="replace") as sf: sec_cues = _parse_srt_text_to_cues(sf.read())
                if sec_cues:
                    sec_cues = normalize_and_dedupe_cues(sec_cues)
                    cues = merge_bilingual_cues(cues, sec_cues)

        c_start, c_end = float(getattr(stream_info, "clip_start_sec", 0.0) or 0.0), float(getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
        if c_end > c_start >= 0.0: cues = filter_and_shift_cues_for_clip(cues, c_start, c_end)
        export_cues_to_srt(cues, srt_path)
    except Exception: pass


def process_post_download_clip_and_subtitles(
    stream_info: Any, target_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    on_stage_progress: Optional[Callable[[str, float, str], None]] = None,
    trim_fn: Optional[Callable[..., bool]] = None,
    probe_duration_fn: Optional[Callable[[str, str], float]] = None,
) -> str:
    """Unified coordinator step handling subtitle embedding/burning, audio boost, and clip trimming."""
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_sub = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")))
    clip_start, clip_end = float(getattr(stream_info, "clip_start_sec", 0.0) or 0.0), float(getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
    has_clip, audio_boost = (clip_end > clip_start >= 0.0), bool(getattr(stream_info, "audio_boost_enabled", False))
    chapter_title, boost_applied = str(getattr(stream_info, "selected_chapter_title", "") or "").strip(), bool(getattr(stream_info, "_audio_boost_applied", False))

    mce = sys.modules.get("faqih_downloader.services.media_clipper_engine")
    eff_trim = trim_fn or (getattr(mce, "trim_media_file", None) if mce else None) or trim_media_file
    eff_probe = probe_duration_fn or (getattr(mce, "probe_media_duration", None) if mce else None) or probe_media_duration

    from ..external_subtitle_service import get_valid_ext_tracks, rename_sidecar_srts_on_video_rename
    has_ext_sub = bool(get_valid_ext_tracks(stream_info))

    if has_sub or has_ext_sub:
        sc = getattr(stream_info, "style_config", None) or {}
        sc.update({"clip_start": clip_start, "clip_end": clip_end, "custom_edits": getattr(stream_info, "subtitle_custom_edits", {}), "dual_sub": getattr(stream_info, "dual_subtitle_enabled", False), "secondary_track": clone_clean_subtitle_track(getattr(stream_info, "secondary_subtitle_track", None)), "audio_boost": audio_boost, "chapter_title": chapter_title, "_already_trimmed": bool(getattr(stream_info, "_already_trimmed", False))})
        setattr(stream_info, "style_config", sc)
        if isinstance(sub, dict):
            sub = clone_clean_subtitle_track(sub); sub["style_config"] = sc
            for attr in ("subtitle_track", "selected_subtitle_track"): setattr(stream_info, attr, sub)
        from ..subtitle_processor import handle_subtitles_post_download
        s_mode = getattr(stream_info, "subtitle_embed_mode", "hard_burn")
        sub_stage = "Burning Subtitles" if s_mode == "hard_burn" else "Embedding Subtitles"
        dur = float(getattr(stream_info, "duration", 0.0) or 0.0)
        _sub_cb = (lambda p, eta: on_stage_progress(sub_stage, p, eta)) if (on_stage_progress and has_sub) else None
        f_path = handle_subtitles_post_download(stream_info, target_path, on_log=on_log, cancel_event=cancel_event, total_duration=dur, on_progress_pct=_sub_cb)
        if f_path and os.path.isfile(f_path):
            target_path = f_path
            if getattr(stream_info, "_audio_boost_applied", False): boost_applied = True

    if has_clip and not getattr(stream_info, "_already_trimmed", False) and os.path.isfile(target_path):
        from ..media_env_helpers import find_ffmpeg_bin
        ff = find_ffmpeg_bin(); exp_d = clip_end - clip_start
        cur_d = eff_probe(target_path, ff) if ff else -1.0
        apply_boost_here = (audio_boost and not boost_applied)
        _clip_cb = (lambda p, eta: on_stage_progress("Clipping", p, eta)) if on_stage_progress else None
        if (cur_d <= 0 or cur_d > exp_d + 0.8) or apply_boost_here:
            if eff_trim(target_path, clip_start, clip_end, ffmpeg_bin=ff, on_log=on_log, cancel_event=cancel_event, audio_boost=apply_boost_here, total_duration=exp_d, on_progress_pct=_clip_cb) and apply_boost_here:
                boost_applied = True

    boost_already_done = boost_applied or bool(getattr(stream_info, "_audio_boost_applied", False))
    if audio_boost and not boost_already_done and os.path.isfile(target_path):
        from ..audio_and_chapters_engine import apply_audio_boost_to_file
        from ..media_env_helpers import find_ffmpeg_bin
        boost_dur = (clip_end - clip_start) if (clip_end > clip_start >= 0.0) else float(getattr(stream_info, "duration", 0.0) or 0.0)
        _boost_cb = (lambda p, eta: on_stage_progress("Audio Boost", p, eta)) if on_stage_progress else None
        if apply_audio_boost_to_file(target_path, ffmpeg_bin=find_ffmpeg_bin(), on_log=on_log, cancel_event=cancel_event, total_duration=boost_dur, on_progress_pct=_boost_cb):
            boost_applied = True
            setattr(stream_info, "_audio_boost_applied", True)

    if (has_clip or chapter_title) and os.path.isfile(target_path):
        d_dir, f_name = os.path.split(target_path); stem, ext = os.path.splitext(f_name)
        clean_ch = re.sub(r'[\[\(\]\)\s\-–—:|•~.]+$', '', re.sub(r'^[\[\(\]\)\s\-–—:|•~.]+', '', re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', chapter_title).strip())).strip() if chapter_title else ""
        new_stem = f"{stem}{f' [{clean_ch}]' if (clean_ch and f'[{clean_ch}]' not in stem) else ''}{' [Clip]' if (has_clip and '[Clip]' not in stem) else ''}"
        if new_stem != stem:
            new_path = os.path.join(d_dir, f"{new_stem}{ext}")
            for _ in range(4):
                try:
                    os.replace(target_path, new_path); target_path = new_path
                    rename_sidecar_srts_on_video_rename(d_dir, stem, new_stem)
                    break
                except Exception: time.sleep(0.08)
    return target_path


__all__ = [
    "prepare_post_download_subtitles",
    "process_post_download_clip_and_subtitles",
]
