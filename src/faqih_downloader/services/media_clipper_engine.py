"""
Media Clipper Engine (media_clipper_engine.py).
Provides live clipping, subtitle shifting/editing, dual subs merge, and frame-accurate media trimming.
"""
from __future__ import annotations
import os, time, subprocess, shutil, re
from typing import Dict, List, Optional, Tuple, Any, Callable

def apply_custom_cue_edits(cues: list, custom_edits: Optional[Dict[str, Any]]) -> list:
    """Applies user-edited subtitle texts from the preview studio to cue items."""
    if not cues or not custom_edits: return cues
    edits = {str(k).strip(): str(v) for k, v in custom_edits.items()}
    updated = []
    for idx, item in enumerate(cues):
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s, e, text = float(item[0]), float(item[1]), str(item[2])
        else: updated.append(item); continue
        matched = None
        for k in (str(idx), f"{s:.2f}", f"{s:.3f}", text.strip()):
            if k in edits: matched = edits[k]; break
        new_text = matched if matched is not None else text
        if is_dict: d = dict(item); d["text"] = new_text; updated.append(d)
        else: updated.append((s, e, new_text))
    return updated

def filter_and_shift_cues_for_clip(cues: list, clip_start: float, clip_end: float) -> list:
    """Filters cues overlapping [clip_start, clip_end] and shifts timestamps to start at 00:00."""
    if not cues or clip_end <= clip_start or clip_start < 0: return cues
    shifted = []
    for item in cues:
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s, e, text = float(item[0]), float(item[1]), str(item[2])
        else: continue
        if e > clip_start and s < clip_end:
            new_s = max(0.0, round(s - clip_start, 3))
            new_e = min(round(clip_end - clip_start, 3), round(e - clip_start, 3))
            if new_e > new_s + 0.01:
                if is_dict: d = dict(item); d["start"] = new_s; d["end"] = new_e; shifted.append(d)
                else: shifted.append((new_s, new_e, text))
    return shifted

def merge_bilingual_cues(primary_cues: list, secondary_cues: list) -> list:
    """Merges secondary subtitle cues into primary cues with [[DUAL]] separator for bilingual display."""
    if not primary_cues: return []
    if not secondary_cues: return primary_cues
    sec_extracted: List[Tuple[float, float, str]] = []
    for item in secondary_cues:
        if isinstance(item, dict): sec_extracted.append((float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: sec_extracted.append((float(item[0]), float(item[1]), str(item[2])))

    merged = []
    for item in primary_cues:
        s1, e1, t1 = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s1, e1, t1 = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s1, e1, t1 = float(item[0]), float(item[1]), str(item[2])
        else: merged.append(item); continue

        matching_sec, best_sec, best_ol = [], "", 0.0
        for s2, e2, t2 in sec_extracted:
            overlap = max(0.0, min(e1, e2) - max(s1, s2))
            sec_dur = max(0.1, e2 - s2)
            if (overlap > 0.2 and overlap / sec_dur > 0.25) or (overlap > 0.6):
                t2c = t2.strip()
                if t2c and t2c not in matching_sec: matching_sec.append(t2c)
            if overlap > 0.05 and overlap > best_ol and t2.strip():
                best_ol, best_sec = overlap, t2.strip()
        comb_sec = " ".join(matching_sec).strip() if matching_sec else best_sec
        comb = f"{t1.strip()}\n[[DUAL]]{comb_sec}" if comb_sec else t1.strip()
        if is_dict: d = dict(item); d["text"] = comb; merged.append(d)
        else: merged.append((s1, e1, comb))
    return merged

def probe_media_duration(file_path: str, ffmpeg_bin: str) -> float:
    """Probes media duration in seconds via FFmpeg banner stderr."""
    try:
        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        cmd = [ffmpeg_bin, "-hide_banner", "-i", os.path.abspath(file_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=cflags, timeout=6)
        m = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", res.stderr)
        if m: return float(m.group(1)) * 3600.0 + float(m.group(2)) * 60.0 + float(m.group(3))
    except Exception: pass
    return -1.0

def export_cues_to_srt(cues: list, output_srt_path: str) -> bool:
    """Exports cues list to UTF-8 SRT file with [[DUAL]] rendered as clean secondary line."""
    if not cues: return False
    try: from .subtitle_downloader import _format_seconds_to_srt
    except Exception:
        def _format_seconds_to_srt(sec: float) -> str:
            sec = max(0.0, float(sec)); h, m, s = int(sec // 3600), int((sec % 3600) // 60), int(sec % 60)
            ms = int(round((sec - int(sec)) * 1000))
            if ms >= 1000: s += 1; ms = 0
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines, idx = [], 1
    for item in cues:
        s, e, text = 0.0, 0.0, ""
        if isinstance(item, dict): s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s, e, text = float(item[0]), float(item[1]), str(item[2])
        else: continue
        clean = text.replace("\n[[DUAL]]", "\n").replace("[[DUAL]]", "\n").strip()
        if not clean or e <= s: continue
        lines.append(f"{idx}\n{_format_seconds_to_srt(s)} --> {_format_seconds_to_srt(e)}\n{clean}\n"); idx += 1
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_srt_path)), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f: f.write("\n".join(lines).strip() + "\n")
        return True
    except Exception: return False

def trim_media_file(
    file_path: str, clip_start: float, clip_end: float,
    ffmpeg_bin: Optional[str] = None, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None, audio_boost: bool = False
) -> bool:
    """Trims video or audio file to [clip_start, clip_end] in-place with frame-accurate verification."""
    if clip_end <= clip_start or clip_start < 0 or not os.path.isfile(file_path): return False
    if cancel_event and cancel_event.is_set(): return False
    if not ffmpeg_bin:
        try: from .media_env_helpers import find_ffmpeg_bin; ffmpeg_bin = find_ffmpeg_bin()
        except Exception: ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        if on_log: on_log("[CLIPPER] FFmpeg binary not found; skipping media trimming.")
        return False

    base, ext = os.path.splitext(file_path)
    temp_clip = f"{base}.sd_clip_{os.getpid()}_{int(time.time()*1000)}{ext}"
    from .subtitle_processor import run_cancellable_ffmpeg
    exp_dur = clip_end - clip_start
    copy_ok = False
    is_audio = ext.lower() in (".mp3", ".m4a", ".aac", ".wav", ".opus", ".flac")

    if not audio_boost:
        cmd_copy = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), "-c", "copy", "-avoid_negative_ts", "make_zero", temp_clip]
        res = run_cancellable_ffmpeg(cmd_copy, cancel_event=cancel_event)
        if res.returncode == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
            actual_dur = probe_media_duration(temp_clip, ffmpeg_bin)
            if actual_dur > 0 and abs(actual_dur - exp_dur) <= 0.6: copy_ok = True
    else:
        from .audio_and_chapters_engine import get_studio_audio_boost_filter
        af_filt = get_studio_audio_boost_filter()
        if is_audio:
            ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"
            cmd_boost = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), "-af", af_filt, "-c:a", ac, "-b:a", "192k", temp_clip]
        else:
            cmd_boost = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), "-c:v", "copy", "-af", af_filt, "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero", temp_clip]
        res = run_cancellable_ffmpeg(cmd_boost, cancel_event=cancel_event)
        if res.returncode == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
            actual_dur = probe_media_duration(temp_clip, ffmpeg_bin)
            if actual_dur > 0 and abs(actual_dur - exp_dur) <= 0.6: copy_ok = True

    if not copy_ok:
        if os.path.exists(temp_clip):
            try: os.remove(temp_clip)
            except Exception: pass
        af_args = []
        if audio_boost:
            from .audio_and_chapters_engine import get_studio_audio_boost_filter
            af_args = ["-af", get_studio_audio_boost_filter()]
        if is_audio:
            ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"
            cmd_rec = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), *af_args, "-c:a", ac, "-b:a", "192k", temp_clip]
        else:
            cmd_rec = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", *af_args, "-c:a", "aac", "-b:a", "192k", temp_clip]
        res = run_cancellable_ffmpeg(cmd_rec, cancel_event=cancel_event)

    if res.returncode == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
        for _ in range(4):
            try: os.replace(temp_clip, file_path); break
            except Exception: time.sleep(0.08)
        if on_log: on_log(f"[CLIPPER] Successfully trimmed media: {clip_start:.1f}s -> {clip_end:.1f}s")
        return True
    if os.path.exists(temp_clip):
        try: os.remove(temp_clip)
        except Exception: pass
    if on_log and getattr(res, "stderr", None): on_log(f"[CLIPPER] Trimming failed: {res.stderr[-180:].strip()}")
    return False

def prepare_post_download_subtitles(stream_info: Any, srt_path: str, orig_stem: str) -> None:
    """Pre-processes downloaded SRT file with custom edits, dual subs, and clip shifts."""
    if not srt_path or not os.path.isfile(srt_path): return
    try:
        from .subtitle_style_engine import _parse_srt_text_to_cues, normalize_and_dedupe_cues
        with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f: cues = _parse_srt_text_to_cues(f.read())
        if not cues: return
        cues = normalize_and_dedupe_cues(cues)
        edits = getattr(stream_info, "subtitle_custom_edits", None) or {}
        if edits: cues = apply_custom_cue_edits(cues, edits)

        sec_trk = getattr(stream_info, "secondary_subtitle_track", None)
        dual_sub = getattr(stream_info, "dual_subtitle_enabled", False)
        if dual_sub and sec_trk and isinstance(sec_trk, dict) and (sec_trk.get("url") or sec_trk.get("base_url")):
            from .subtitle_downloader import download_subtitle_as_srt
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
    cancel_event: Optional[Any] = None
) -> str:
    """Unified coordinator step handling subtitle embedding/burning, audio boost, and clip trimming."""
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_sub = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")))
    clip_start = float(getattr(stream_info, "clip_start_sec", 0.0) or 0.0)
    clip_end = float(getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
    has_clip = (clip_end > clip_start >= 0.0)
    audio_boost = bool(getattr(stream_info, "audio_boost_enabled", False))
    chapter_title = str(getattr(stream_info, "selected_chapter_title", "") or "").strip()
    boost_applied = bool(getattr(stream_info, "_audio_boost_applied", False))

    if has_sub:
        sc = getattr(stream_info, "style_config", None) or {}
        sc["clip_start"], sc["clip_end"] = clip_start, clip_end
        sc["custom_edits"] = getattr(stream_info, "subtitle_custom_edits", {})
        sc["dual_sub"] = getattr(stream_info, "dual_subtitle_enabled", False)
        sc["secondary_track"] = getattr(stream_info, "secondary_subtitle_track", None)
        sc["audio_boost"] = audio_boost
        sc["chapter_title"] = chapter_title
        setattr(stream_info, "style_config", sc)
        if isinstance(sub, dict): sub.setdefault("style_config", {}).update(sc)
        mode = getattr(stream_info, "subtitle_embed_mode", "hard_burn")
        from .subtitle_processor import handle_subtitles_post_download
        f_path = handle_subtitles_post_download(stream_info, target_path, on_log=on_log, cancel_event=cancel_event)
        if f_path and os.path.isfile(f_path):
            target_path = f_path
            if getattr(stream_info, "_audio_boost_applied", False):
                boost_applied = True

    if has_clip and os.path.isfile(target_path):
        from .media_env_helpers import find_ffmpeg_bin
        ff = find_ffmpeg_bin()
        exp_d = clip_end - clip_start
        cur_d = probe_media_duration(target_path, ff) if ff else -1.0
        need_trim = (cur_d <= 0 or cur_d > exp_d + 0.8)
        apply_boost_here = (audio_boost and not boost_applied)
        if need_trim or apply_boost_here:
            ok = trim_media_file(target_path, clip_start, clip_end, ffmpeg_bin=ff, on_log=on_log, cancel_event=cancel_event, audio_boost=apply_boost_here)
            if ok and apply_boost_here:
                boost_applied = True

    if audio_boost and not boost_applied and os.path.isfile(target_path):
        from .audio_and_chapters_engine import apply_audio_boost_to_file
        from .media_env_helpers import find_ffmpeg_bin
        if apply_audio_boost_to_file(target_path, ffmpeg_bin=find_ffmpeg_bin(), on_log=on_log, cancel_event=cancel_event):
            boost_applied = True

    if (has_clip or chapter_title) and os.path.isfile(target_path):
        d_dir, f_name = os.path.split(target_path)
        stem, ext = os.path.splitext(f_name)
        clean_ch = ""
        if chapter_title:
            clean_ch = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', chapter_title).strip()
            clean_ch = re.sub(r'^[\[\(\]\)\s\-–—:|•~.]+', '', clean_ch)
            clean_ch = re.sub(r'[\[\(\]\)\s\-–—:|•~.]+$', '', clean_ch).strip()
        new_stem = stem
        if clean_ch and f"[{clean_ch}]" not in new_stem:
            new_stem = f"{new_stem} [{clean_ch}]"
        if has_clip and "[Clip]" not in new_stem:
            new_stem = f"{new_stem} [Clip]"
        if new_stem != stem:
            new_path = os.path.join(d_dir, f"{new_stem}{ext}")
            for _ in range(4):
                try:
                    os.replace(target_path, new_path)
                    target_path = new_path
                    old_srt = os.path.join(d_dir, f"{stem}.srt")
                    new_srt = os.path.join(d_dir, f"{new_stem}.srt")
                    if os.path.isfile(old_srt):
                        try: os.replace(old_srt, new_srt)
                        except Exception: pass
                    break
                except Exception:
                    time.sleep(0.08)
    return target_path

def sync_clipper_state_from_body(session: Any, body: Dict[str, Any], opt: Any = None) -> None:
    """Helper for preview_stream_bridge to sync live clipper, text edits, dual subs, audio boost, and chapters."""
    c_start = float(body.get("clip_start", getattr(session, "clip_start", 0.0) or 0.0))
    c_end = float(body.get("clip_end", getattr(session, "clip_end", 0.0) or 0.0))
    edits = dict(body.get("sub_custom_edits", getattr(session, "sub_custom_edits", {}) or {}))
    dual = bool(body.get("dual_sub", getattr(session, "dual_sub", False)))
    s_idx = int(body.get("sec_s_idx", getattr(session, "sec_s_idx", -1)))
    boost = bool(body.get("audio_boost", getattr(session, "audio_boost", False)))
    ch_title = str(body.get("chapter_title", getattr(session, "chapter_title", "")) or "").strip()

    session.clip_start, session.clip_end = c_start, c_end
    session.sub_custom_edits, session.dual_sub, session.sec_s_idx = edits, dual, s_idx
    session.audio_boost, session.chapter_title = boost, ch_title

    if opt:
        opt.clip_start_sec, opt.clip_end_sec = c_start, c_end
        opt.subtitle_custom_edits, opt.dual_subtitle_enabled = edits, dual
        opt.audio_boost_enabled, opt.selected_chapter_title = boost, ch_title
        if dual and session.subtitle_tracks:
            if 0 <= s_idx < len(session.subtitle_tracks): opt.secondary_subtitle_track = session.subtitle_tracks[s_idx]
            else:
                for idx, trk in enumerate(session.subtitle_tracks):
                    if idx > 0 and (not session.selected_sub_track or trk != session.selected_sub_track):
                        opt.secondary_subtitle_track = trk; break
        st = getattr(opt, "selected_subtitle_track", None)
        if st and isinstance(st, dict):
            sc = st.setdefault("style_config", {})
            sc["clip_start"], sc["clip_end"], sc["custom_edits"] = c_start, c_end, edits
            sc["dual_sub"], sc["secondary_track"] = dual, getattr(opt, "secondary_subtitle_track", None)
            sc["audio_boost"], sc["chapter_title"] = boost, ch_title

    m = getattr(session, "modal_ref", None)
    if m and hasattr(m, "selected_option") and m.selected_option:
        m.selected_option.clip_start_sec = c_start
        m.selected_option.clip_end_sec = c_end
        m.selected_option.subtitle_custom_edits = edits
        m.selected_option.dual_subtitle_enabled = dual
        m.selected_option.audio_boost_enabled = boost
        m.selected_option.selected_chapter_title = ch_title
        if opt: m.selected_option.secondary_subtitle_track = getattr(opt, "secondary_subtitle_track", None)

def enrich_stream_info_with_clip(stream_info: Any, opt: Any) -> Any:
    """Enriches YouTubeStreamInfo instance with clip range, dual subtitle, and audio boost configuration."""
    if opt and stream_info:
        stream_info.clip_start_sec = float(getattr(opt, "clip_start_sec", 0.0) or 0.0)
        stream_info.clip_end_sec = float(getattr(opt, "clip_end_sec", 0.0) or 0.0)
        stream_info.subtitle_custom_edits = dict(getattr(opt, "subtitle_custom_edits", {}) or {})
        stream_info.dual_subtitle_enabled = bool(getattr(opt, "dual_subtitle_enabled", False))
        stream_info.secondary_subtitle_track = getattr(opt, "secondary_subtitle_track", None)
        stream_info.audio_boost_enabled = bool(getattr(opt, "audio_boost_enabled", False))
        stream_info.selected_chapter_title = str(getattr(opt, "selected_chapter_title", "") or "")
    return stream_info
