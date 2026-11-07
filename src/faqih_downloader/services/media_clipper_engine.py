"""
Media Clipper Engine (media_clipper_engine.py).
Provides live video/audio clipping, temporal subtitle shifting, custom cue editing,
bilingual subtitle merging, and frame-accurate post-download media trimming via FFmpeg.
"""
from __future__ import annotations
import os, time, subprocess, shutil
from typing import Dict, List, Optional, Tuple, Any, Callable

def apply_custom_cue_edits(cues: list, custom_edits: Optional[Dict[str, Any]]) -> list:
    """Applies user-edited subtitle texts from the preview studio to cue items."""
    if not cues or not custom_edits:
        return cues
    edits = {str(k).strip(): str(v).strip() for k, v in custom_edits.items()}
    updated = []
    for idx, item in enumerate(cues):
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict:
            s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            s, e, text = float(item[0]), float(item[1]), str(item[2])
        else:
            updated.append(item); continue

        matched_text = edits.get(str(idx)) or edits.get(f"{s:.2f}") or edits.get(f"{s:.3f}") or edits.get(text.strip())
        new_text = matched_text if matched_text is not None else text
        if is_dict:
            d = dict(item); d["text"] = new_text; updated.append(d)
        else:
            updated.append((s, e, new_text))
    return updated

def filter_and_shift_cues_for_clip(cues: list, clip_start: float, clip_end: float) -> list:
    """Filters cues overlapping [clip_start, clip_end] and shifts timestamps to start at 00:00."""
    if not cues or clip_end <= clip_start or clip_start < 0:
        return cues
    shifted = []
    for item in cues:
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict:
            s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            s, e, text = float(item[0]), float(item[1]), str(item[2])
        else:
            continue
        if e > clip_start and s < clip_end:
            new_s = max(0.0, round(s - clip_start, 3))
            new_e = min(round(clip_end - clip_start, 3), round(e - clip_start, 3))
            if new_e > new_s + 0.01:
                if is_dict:
                    d = dict(item); d["start"] = new_s; d["end"] = new_e; shifted.append(d)
                else:
                    shifted.append((new_s, new_e, text))
    return shifted

def merge_bilingual_cues(primary_cues: list, secondary_cues: list) -> list:
    """Merges secondary subtitle cues into primary cues with [[DUAL]] separator for bilingual display."""
    if not primary_cues: return []
    if not secondary_cues: return primary_cues

    sec_extracted: List[Tuple[float, float, str]] = []
    for item in secondary_cues:
        if isinstance(item, dict):
            sec_extracted.append((float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))))
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            sec_extracted.append((float(item[0]), float(item[1]), str(item[2])))

    merged = []
    for item in primary_cues:
        s1, e1, t1 = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict:
            s1, e1, t1 = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            s1, e1, t1 = float(item[0]), float(item[1]), str(item[2])
        else:
            merged.append(item); continue

        best_sec_text = ""
        best_overlap = 0.0
        for s2, e2, t2 in sec_extracted:
            overlap = max(0.0, min(e1, e2) - max(s1, s2))
            if overlap > 0.05 and overlap > best_overlap and t2.strip():
                best_overlap = overlap
                best_sec_text = t2.strip()

        combined_text = f"{t1.strip()}\n[[DUAL]]{best_sec_text}" if best_sec_text else t1.strip()
        if is_dict:
            d = dict(item); d["text"] = combined_text; merged.append(d)
        else:
            merged.append((s1, e1, combined_text))
    return merged

def trim_media_file(
    file_path: str, clip_start: float, clip_end: float,
    ffmpeg_bin: Optional[str] = None, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None
) -> bool:
    """Trims video or audio file to [clip_start, clip_end] in-place using FFmpeg fast stream copy or transcode."""
    if clip_end <= clip_start or clip_start < 0 or not os.path.isfile(file_path):
        return False
    if cancel_event and cancel_event.is_set():
        return False
    if not ffmpeg_bin:
        try:
            from .media_env_helpers import find_ffmpeg_bin
            ffmpeg_bin = find_ffmpeg_bin()
        except Exception:
            ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        if on_log: on_log("[CLIPPER] FFmpeg binary not found; skipping media trimming.")
        return False

    base, ext = os.path.splitext(file_path)
    temp_clip = f"{base}.sd_clip_{os.getpid()}_{int(time.time()*1000)}{ext}"
    from .subtitle_processor import run_cancellable_ffmpeg

    cmd_copy = [
        ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}",
        "-i", os.path.abspath(file_path), "-c", "copy", "-avoid_negative_ts", "make_zero", temp_clip
    ]
    res = run_cancellable_ffmpeg(cmd_copy, cancel_event=cancel_event)
    if res.returncode != 0 or not os.path.isfile(temp_clip) or os.path.getsize(temp_clip) == 0:
        if os.path.exists(temp_clip):
            try: os.remove(temp_clip)
            except Exception: pass
        is_audio = ext.lower() in (".mp3", ".m4a", ".aac", ".wav", ".opus", ".flac")
        if is_audio:
            ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"
            cmd_rec = [
                ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}",
                "-i", os.path.abspath(file_path), "-c:a", ac, "-b:a", "192k", temp_clip
            ]
        else:
            cmd_rec = [
                ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}",
                "-i", os.path.abspath(file_path), "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "22", "-c:a", "aac", "-b:a", "192k", temp_clip
            ]
        res = run_cancellable_ffmpeg(cmd_rec, cancel_event=cancel_event)

    if res.returncode == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
        for _ in range(4):
            try:
                os.replace(temp_clip, file_path)
                break
            except Exception:
                time.sleep(0.08)
        if on_log: on_log(f"[CLIPPER] Successfully trimmed media: {clip_start:.1f}s -> {clip_end:.1f}s")
        return True
    if os.path.exists(temp_clip):
        try: os.remove(temp_clip)
        except Exception: pass
    if on_log and getattr(res, "stderr", None):
        on_log(f"[CLIPPER] Trimming failed: {res.stderr[-180:].strip()}")
    return False

def process_post_download_clip_and_subtitles(
    stream_info: Any, target_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None
) -> str:
    """Unified coordinator step handling subtitle embedding/burning and clip trimming."""
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_sub = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")))
    clip_start = float(getattr(stream_info, "clip_start_sec", 0.0) or 0.0)
    clip_end = float(getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
    has_clip = (clip_end > clip_start >= 0.0)
    mode = getattr(stream_info, "subtitle_embed_mode", "hard_burn")

    if has_sub:
        sc = getattr(stream_info, "style_config", None) or {}
        sc["clip_start"], sc["clip_end"] = clip_start, clip_end
        sc["custom_edits"] = getattr(stream_info, "subtitle_custom_edits", {})
        sc["dual_sub"] = getattr(stream_info, "dual_subtitle_enabled", False)
        sc["secondary_track"] = getattr(stream_info, "secondary_subtitle_track", None)
        setattr(stream_info, "style_config", sc)
        if isinstance(sub, dict):
            sub.setdefault("style_config", {}).update(sc)
        from .subtitle_processor import handle_subtitles_post_download
        f_path = handle_subtitles_post_download(stream_info, target_path, on_log=on_log, cancel_event=cancel_event)
        if f_path and os.path.isfile(f_path):
            target_path = f_path
        if has_clip and mode != "hard_burn":
            trim_media_file(target_path, clip_start, clip_end, on_log=on_log, cancel_event=cancel_event)
    elif has_clip:
        trim_media_file(target_path, clip_start, clip_end, on_log=on_log, cancel_event=cancel_event)

    if has_clip and os.path.isfile(target_path):
        d_dir, f_name = os.path.split(target_path)
        if "[Clip]" not in f_name:
            stem, ext = os.path.splitext(f_name)
            new_path = os.path.join(d_dir, f"{stem} [Clip]{ext}")
            try:
                os.replace(target_path, new_path)
                target_path = new_path
            except Exception: pass
    return target_path

def sync_clipper_state_from_body(session: Any, body: Dict[str, Any], opt: Any = None) -> None:
    """Helper for preview_stream_bridge to sync live clipper, text edits, and dual subs."""
    c_start = float(body.get("clip_start", getattr(session, "clip_start", 0.0) or 0.0))
    c_end = float(body.get("clip_end", getattr(session, "clip_end", 0.0) or 0.0))
    edits = dict(body.get("sub_custom_edits", getattr(session, "sub_custom_edits", {}) or {}))
    dual = bool(body.get("dual_sub", getattr(session, "dual_sub", False)))
    s_idx = int(body.get("sec_s_idx", getattr(session, "sec_s_idx", -1)))

    session.clip_start, session.clip_end = c_start, c_end
    session.sub_custom_edits, session.dual_sub, session.sec_s_idx = edits, dual, s_idx

    if opt:
        opt.clip_start_sec, opt.clip_end_sec = c_start, c_end
        opt.subtitle_custom_edits, opt.dual_subtitle_enabled = edits, dual
        if dual and session.subtitle_tracks:
            if 0 <= s_idx < len(session.subtitle_tracks):
                opt.secondary_subtitle_track = session.subtitle_tracks[s_idx]
            else:
                for idx, trk in enumerate(session.subtitle_tracks):
                    if idx > 0 and (not session.selected_sub_track or trk != session.selected_sub_track):
                        opt.secondary_subtitle_track = trk; break
        st = getattr(opt, "selected_subtitle_track", None)
        if st and isinstance(st, dict):
            sc = st.setdefault("style_config", {})
            sc["clip_start"], sc["clip_end"], sc["custom_edits"] = c_start, c_end, edits
            sc["dual_sub"], sc["secondary_track"] = dual, getattr(opt, "secondary_subtitle_track", None)

    m = getattr(session, "modal_ref", None)
    if m and hasattr(m, "selected_option") and m.selected_option:
        m.selected_option.clip_start_sec = c_start
        m.selected_option.clip_end_sec = c_end
        m.selected_option.subtitle_custom_edits = edits
        m.selected_option.dual_subtitle_enabled = dual
        if opt: m.selected_option.secondary_subtitle_track = getattr(opt, "secondary_subtitle_track", None)

def enrich_stream_info_with_clip(stream_info: Any, opt: Any) -> Any:
    """Enriches YouTubeStreamInfo instance with clip range and dual subtitle configuration."""
    if opt and stream_info:
        stream_info.clip_start_sec = float(getattr(opt, "clip_start_sec", 0.0) or 0.0)
        stream_info.clip_end_sec = float(getattr(opt, "clip_end_sec", 0.0) or 0.0)
        stream_info.subtitle_custom_edits = dict(getattr(opt, "subtitle_custom_edits", {}) or {})
        stream_info.dual_subtitle_enabled = bool(getattr(opt, "dual_subtitle_enabled", False))
        stream_info.secondary_subtitle_track = getattr(opt, "secondary_subtitle_track", None)
    return stream_info
