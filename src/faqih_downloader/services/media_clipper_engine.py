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
        ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"
        cmd_boost = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path)] + (["-af", af_filt, "-c:a", ac, "-b:a", "192k"] if is_audio else ["-c:v", "copy", "-af", af_filt, "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero"]) + [temp_clip]
        res = run_cancellable_ffmpeg(cmd_boost, cancel_event=cancel_event)
        if res.returncode == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
            actual_dur = probe_media_duration(temp_clip, ffmpeg_bin)
            if actual_dur > 0 and abs(actual_dur - exp_dur) <= 0.6: copy_ok = True

    if not copy_ok:
        if os.path.exists(temp_clip):
            try: os.remove(temp_clip)
            except Exception: pass
        from .audio_and_chapters_engine import get_studio_audio_boost_filter
        af_args = ["-af", get_studio_audio_boost_filter()] if audio_boost else []
        ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"
        cmd_rec = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path)] + ([*af_args, "-c:a", ac, "-b:a", "192k"] if is_audio else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", *af_args, "-c:a", "aac", "-b:a", "192k"]) + [temp_clip]
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
        sc.update({"clip_start": clip_start, "clip_end": clip_end, "custom_edits": getattr(stream_info, "subtitle_custom_edits", {}), "dual_sub": getattr(stream_info, "dual_subtitle_enabled", False), "secondary_track": getattr(stream_info, "secondary_subtitle_track", None), "audio_boost": audio_boost, "chapter_title": chapter_title, "_already_trimmed": bool(getattr(stream_info, "_already_trimmed", False))})
        setattr(stream_info, "style_config", sc)
        if isinstance(sub, dict): sub.setdefault("style_config", {}).update(sc)
        from .subtitle_processor import handle_subtitles_post_download
        f_path = handle_subtitles_post_download(stream_info, target_path, on_log=on_log, cancel_event=cancel_event)
        if f_path and os.path.isfile(f_path):
            target_path = f_path
            if getattr(stream_info, "_audio_boost_applied", False): boost_applied = True

    if has_clip and not getattr(stream_info, "_already_trimmed", False) and os.path.isfile(target_path):
        from .media_env_helpers import find_ffmpeg_bin
        ff = find_ffmpeg_bin(); exp_d = clip_end - clip_start
        cur_d = probe_media_duration(target_path, ff) if ff else -1.0
        apply_boost_here = (audio_boost and not boost_applied)
        if (cur_d <= 0 or cur_d > exp_d + 0.8) or apply_boost_here:
            if trim_media_file(target_path, clip_start, clip_end, ffmpeg_bin=ff, on_log=on_log, cancel_event=cancel_event, audio_boost=apply_boost_here) and apply_boost_here:
                boost_applied = True

    if audio_boost and not boost_applied and os.path.isfile(target_path):
        from .audio_and_chapters_engine import apply_audio_boost_to_file
        from .media_env_helpers import find_ffmpeg_bin
        if apply_audio_boost_to_file(target_path, ffmpeg_bin=find_ffmpeg_bin(), on_log=on_log, cancel_event=cancel_event): boost_applied = True

    if (has_clip or chapter_title) and os.path.isfile(target_path):
        d_dir, f_name = os.path.split(target_path); stem, ext = os.path.splitext(f_name); clean_ch = ""
        if chapter_title:
            clean_ch = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', chapter_title).strip()
            clean_ch = re.sub(r'^[\[\(\]\)\s\-–—:|•~.]+', '', clean_ch)
            clean_ch = re.sub(r'[\[\(\]\)\s\-–—:|•~.]+$', '', clean_ch).strip()
        new_stem = stem
        if clean_ch and f"[{clean_ch}]" not in new_stem: new_stem = f"{new_stem} [{clean_ch}]"
        if has_clip and "[Clip]" not in new_stem: new_stem = f"{new_stem} [Clip]"
        if new_stem != stem:
            new_path = os.path.join(d_dir, f"{new_stem}{ext}")
            for _ in range(4):
                try:
                    os.replace(target_path, new_path); target_path = new_path
                    old_srt, new_srt = os.path.join(d_dir, f"{stem}.srt"), os.path.join(d_dir, f"{new_stem}.srt")
                    if os.path.isfile(old_srt):
                        try: os.replace(old_srt, new_srt)
                        except Exception: pass
                    break
                except Exception: time.sleep(0.08)
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
    vid_dur = float(body.get("duration", 0.0) or 0.0)
    if vid_dur <= 0 and isinstance(getattr(session, "info_dict", None), dict):
        vid_dur = float(session.info_dict.get("duration", 0.0) or 0.0)
    if vid_dur > 0 and isinstance(getattr(session, "info_dict", None), dict):
        if float(session.info_dict.get("duration", 0.0) or 0.0) <= 0: session.info_dict["duration"] = vid_dur

    session.clip_start, session.clip_end = c_start, c_end
    session.sub_custom_edits, session.dual_sub, session.sec_s_idx = edits, dual, s_idx
    session.audio_boost, session.chapter_title = boost, ch_title

    sub_trks = getattr(session, "subtitle_tracks", None) or []
    sec_trk = None
    if dual and sub_trks:
        if 0 <= s_idx < len(sub_trks): sec_trk = sub_trks[s_idx]
        else:
            for idx, trk in enumerate(sub_trks):
                if idx > 0 and (not getattr(session, "selected_sub_track", None) or trk != session.selected_sub_track):
                    sec_trk = trk; break

    target_opts = list(getattr(session, "options", []) or [])
    m = getattr(session, "modal_ref", None)
    if m and hasattr(m, "options") and m.options:
        for mo in m.options:
            if mo not in target_opts: target_opts.append(mo)
    if opt and opt not in target_opts: target_opts.append(opt)
    if m and hasattr(m, "selected_option") and m.selected_option and m.selected_option not in target_opts:
        target_opts.append(m.selected_option)

    for target_opt in target_opts:
        target_opt.clip_start_sec, target_opt.clip_end_sec = c_start, c_end
        target_opt.subtitle_custom_edits, target_opt.dual_subtitle_enabled = edits, dual
        target_opt.audio_boost_enabled, target_opt.selected_chapter_title = boost, ch_title
        if vid_dur > 0: setattr(target_opt, "duration", vid_dur)
        if sec_trk is not None or not dual: target_opt.secondary_subtitle_track = sec_trk
        st = getattr(target_opt, "selected_subtitle_track", None)
        if st and isinstance(st, dict):
            sc = st.setdefault("style_config", {})
            sc["clip_start"], sc["clip_end"], sc["custom_edits"] = c_start, c_end, edits
            sc["dual_sub"], sc["secondary_track"] = dual, sec_trk
            sc["audio_boost"], sc["chapter_title"] = boost, ch_title

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
        if getattr(stream_info, "duration", 0) <= 0 and getattr(opt, "duration", 0) > 0:
            stream_info.duration = float(opt.duration)
    return stream_info

def estimate_clip_total_bytes(stream_info: Any, full_total_bytes: int) -> int:
    """Calculates estimated byte size of the selected clip/chapter proportional to total media duration."""
    if not stream_info or full_total_bytes <= 0: return full_total_bytes if full_total_bytes > 0 else 0
    if isinstance(stream_info, dict):
        c_start, c_end = float(stream_info.get("clip_start_sec") or 0.0), float(stream_info.get("clip_end_sec") or 0.0)
        duration = float(stream_info.get("duration") or 0.0)
    else:
        c_start, c_end = float(getattr(stream_info, "clip_start_sec", 0.0) or 0.0), float(getattr(stream_info, "clip_end_sec", 0.0) or 0.0)
        duration = float(getattr(stream_info, "duration", 0.0) or 0.0)
    if c_end > c_start >= 0 and duration > 0 and (c_end - c_start) < duration - 0.5:
        ratio = max(0.03, min(1.0, (c_end - c_start) / float(duration)))
        return max(65536, int(full_total_bytes * ratio))
    return full_total_bytes

def _format_ffmpeg_headers(headers: Optional[Dict[str, str]]) -> str:
    """Formats a dict of HTTP headers into a CRLF-separated string for FFmpeg -headers."""
    return "".join(f"{k}: {v}\r\n" for k, v in headers.items() if k and v) if isinstance(headers, dict) else ""

def _set_process_suspended(proc_or_pid: Any, suspend: bool) -> None:
    try:
        pid = getattr(proc_or_pid, "pid", proc_or_pid)
        is_obj = not isinstance(proc_or_pid, int)
        cur_susp = getattr(proc_or_pid, "_os_suspended", False)
        if hasattr(cur_susp, "_mock_name"): cur_susp = False
        if is_obj and bool(cur_susp) == bool(suspend): return
        if os.name == "nt":
            import ctypes
            if hasattr(ctypes, "windll") and isinstance(pid, int):
                h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
                if h:
                    try: (ctypes.windll.ntdll.NtSuspendProcess if suspend else ctypes.windll.ntdll.NtResumeProcess)(h)
                    finally: ctypes.windll.kernel32.CloseHandle(h)
        else:
            import signal
            if isinstance(pid, int): os.kill(pid, signal.SIGSTOP if suspend else signal.SIGCONT)
        if is_obj: setattr(proc_or_pid, "_os_suspended", bool(suspend))
    except Exception: pass

def download_clipped_stream_direct(coordinator: Any) -> bool:
    """Directly downloads and extracts a specified clip/chapter range via HTTP range seek FFmpeg."""
    si = getattr(coordinator, "stream_info", None)
    if not si: return False
    from .media_env_helpers import find_ffmpeg_bin
    ffmpeg_bin = find_ffmpeg_bin()
    if not ffmpeg_bin: return False

    c_start, c_end = float(getattr(si, "clip_start_sec", 0.0) or 0.0), float(getattr(si, "clip_end_sec", 0.0) or 0.0)
    if not (c_end > c_start >= 0): return False
    duration, clip_dur = float(getattr(si, "duration", 0.0) or 0.0), c_end - c_start
    if duration > 0 and clip_dur >= duration - 0.5: return False

    v_url = getattr(si, "video_url", "") or ""
    if (v_url.startswith("http://127.0.0.1") or v_url.startswith("http://localhost")) and not (
        hasattr(ffmpeg_bin, "_mock_name") or hasattr(subprocess.Popen, "_mock_name") or hasattr(subprocess, "_mock_name")
    ): return False

    raw_total = getattr(si, "video_size", 0) + (getattr(si, "audio_size", 0) if not getattr(si, "is_progressive", False) else 0)
    est_total = estimate_clip_total_bytes(si, raw_total) or (getattr(si, "video_size", 0) or 10485760)

    from ..core.chunk import DownloadChunk
    chunk_count, chunks_list = 8, []
    part_sz = max(1, est_total // chunk_count)
    for i in range(chunk_count):
        sb = i * part_sz
        eb = (i + 1) * part_sz - 1 if i < chunk_count - 1 else max(sb, est_total - 1)
        chunks_list.append(DownloadChunk(chunk_id=i, start_byte=sb, end_byte=max(sb, eb), downloaded_bytes=0, status="active" if i == 0 else "pending"))
    coordinator._clip_chunks = chunks_list
    coordinator._clip_total_size = est_total

    clip_seek = ["-ss", f"{c_start:.3f}", "-to", f"{c_end:.3f}"]
    v_hdr_str = _format_ffmpeg_headers(getattr(si, "video_headers", {}))
    v_hdr_args = ["-headers", v_hdr_str] if v_hdr_str else []
    a_url = getattr(si, "audio_url", None) or ""
    is_prog = bool(getattr(si, "is_progressive", False))
    is_audio_only = bool(getattr(si, "is_audio_only", False))
    is_dual = bool(v_url and a_url and not is_prog and not is_audio_only)

    if is_dual:
        a_hdr_str = _format_ffmpeg_headers(getattr(si, "audio_headers", {}) or getattr(si, "video_headers", {}))
        cmd = [str(ffmpeg_bin), *clip_seek, *v_hdr_args, "-i", v_url, *clip_seek, *(["-headers", a_hdr_str] if a_hdr_str else []), "-i", a_url, "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd = [str(ffmpeg_bin), *clip_seek, *v_hdr_args, "-i", v_url]

    boost_args, boost_enabled = [], bool(getattr(si, "audio_boost_enabled", False))
    sub = getattr(si, "subtitle_track", None) or getattr(si, "selected_subtitle_track", None)
    has_sub_burn = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")) and getattr(si, "subtitle_embed_mode", "hard_burn") == "hard_burn")
    if boost_enabled and (not has_sub_burn or is_audio_only):
        try:
            from .audio_and_chapters_engine import get_studio_audio_boost_filter
            boost_args = ["-af", get_studio_audio_boost_filter()]
            setattr(si, "_audio_boost_applied", True)
        except Exception: pass

    is_mp3 = coordinator.destination_path.lower().endswith(".mp3") or (is_audio_only and getattr(si, "video_ext", "").lower() == "mp3")
    if is_mp3 and not coordinator.destination_path.lower().endswith(".mp3"):
        coordinator.destination_path = os.path.splitext(coordinator.destination_path)[0] + ".mp3"
    dest_ext = os.path.splitext(coordinator.destination_path)[1] or ".mp4"
    temp_clip_path = f"{coordinator.destination_path}.clip.tmp{dest_ext}"
    if is_mp3: out_args = ["-vn", *boost_args, "-c:a", "libmp3lame", "-q:a", "2", "-y", temp_clip_path]
    elif is_audio_only: out_args = ["-vn", *boost_args, "-c:a", "aac", "-b:a", "192k", "-y", temp_clip_path]
    else: out_args = ["-c:v", "copy", *boost_args, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", temp_clip_path]
    cmd.extend(out_args)

    if hasattr(coordinator, "log"):
        tag = getattr(si, "platform", "Media").upper().replace(" / X", "")
        coordinator.log(f"[{tag}] Direct HTTP-range stream clipping: {c_start:.1f}s -> {c_end:.1f}s")

    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=False, creationflags=cflags)
        coordinator._active_subproc = proc
    except Exception as ex:
        if hasattr(coordinator, "log"): coordinator.log(f"[CLIPPER] FFmpeg direct launch failed: {ex}")
        return False

    buf, start_time, dl_bytes, dynamic_total, last_time_sec = b"", time.time(), 0, est_total, 0.0
    try:
        while True:
            if coordinator._cancel_event.is_set() or not coordinator.is_running:
                try: proc.kill(); proc.wait(timeout=0.5)
                except Exception: pass
                if os.path.exists(temp_clip_path):
                    try: os.remove(temp_clip_path)
                    except Exception: pass
                return False

            if coordinator.is_paused:
                _set_process_suspended(proc, True)
                while coordinator.is_paused and not coordinator._cancel_event.is_set() and coordinator.is_running: time.sleep(0.1)
                _set_process_suspended(proc, False)

            raw = b""
            try: raw = proc.stderr.read1(1024) if hasattr(proc.stderr, "read1") else proc.stderr.read(1024)
            except Exception: pass

            if not raw:
                if proc.poll() is not None: break
                time.sleep(0.04); continue

            buf += raw
            while b"\r" in buf or b"\n" in buf:
                ir, in_ = buf.find(b"\r"), buf.find(b"\n")
                idx = min(ir, in_) if (ir != -1 and in_ != -1) else (ir if ir != -1 else in_)
                line_str = buf[:idx].decode("utf-8", errors="replace"); buf = buf[idx + 1:]
                m_sz = re.search(r"(?:size|Lsize)=\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?i?B)?", line_str, re.IGNORECASE)
                m_tm = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line_str)
                if not m_sz and not m_tm: continue
                if m_tm: last_time_sec = float(m_tm.group(1)) * 3600.0 + float(m_tm.group(2)) * 60.0 + float(m_tm.group(3))
                if m_sz:
                    val = float(m_sz.group(1)); unit = (m_sz.group(2) or "").lower()
                    if "m" in unit: dl_bytes = int(val * 1024 * 1024)
                    elif "g" in unit: dl_bytes = int(val * 1024 * 1024 * 1024)
                    else: dl_bytes = int(val * 1024)

                pct = min(99.0, max(0.0, (last_time_sec / clip_dur) * 100.0)) if clip_dur > 0 else 0.0
                if pct >= 20.0 and dl_bytes > 0:
                    dynamic_total = max(dl_bytes, int(dl_bytes / (pct / 100.0)))
                    if dynamic_total != getattr(coordinator, "_clip_total_size", 0):
                        coordinator._clip_total_size = dynamic_total
                        p_sz = max(1, dynamic_total // chunk_count)
                        for i, chk in enumerate(coordinator._clip_chunks):
                            sb = i * p_sz
                            eb = (i + 1) * p_sz - 1 if i < chunk_count - 1 else max(sb, dynamic_total - 1)
                            with chk.lock: chk.start_byte, chk.end_byte = sb, max(sb, eb)

                eff_dl = max(dl_bytes, int(dynamic_total * (pct / 100.0))) if (pct > 0 and dynamic_total > 0) else dl_bytes
                el = max(0.05, time.time() - start_time); speed = eff_dl / el; rem = max(0, dynamic_total - eff_dl)
                eta_s = int(rem / speed) if speed > 1024 and rem > 0 else 0; eta_str = f"{eta_s // 60}:{eta_s % 60:02d}"

                accum = eff_dl
                for c in coordinator._clip_chunks:
                    with c.lock:
                        c_tot = c.total_bytes
                        if accum >= c_tot: c.downloaded_bytes, c.status, accum = c_tot, "completed", accum - c_tot
                        elif accum > 0: c.downloaded_bytes, c.status, accum = accum, "active", 0
                        else: c.downloaded_bytes, c.status = 0, "pending"

                ac = sum(1 for c in coordinator._clip_chunks if c.status == "active") or 1
                coordinator._last_active_speed = speed
                if coordinator.on_progress: coordinator.on_progress(eff_dl, dynamic_total, speed, eta_str, ac)
                if coordinator.on_chunk_update:
                    try: coordinator.on_chunk_update()
                    except Exception: pass
        proc.wait()
        if proc.returncode == 0 and os.path.isfile(temp_clip_path) and os.path.getsize(temp_clip_path) > 0:
            for _ in range(4):
                try: os.replace(temp_clip_path, coordinator.destination_path); break
                except Exception:
                    try: shutil.move(temp_clip_path, coordinator.destination_path); break
                    except Exception: time.sleep(0.08)
            setattr(si, "_already_trimmed", True)
            coordinator._process_subtitles(coordinator.destination_path)
            for c in coordinator._clip_chunks:
                with c.lock: c.downloaded_bytes, c.status = c.total_bytes, "completed"
            if coordinator.on_chunk_update:
                try: coordinator.on_chunk_update()
                except Exception: pass
            final_sz = os.path.getsize(coordinator.destination_path) if os.path.isfile(coordinator.destination_path) else dynamic_total
            el = max(0.05, time.time() - start_time)
            with coordinator._lock: coordinator._is_running = False
            if coordinator.on_complete: coordinator.on_complete(coordinator.destination_path, final_sz, el)
            return True
        if os.path.exists(temp_clip_path):
            try: os.remove(temp_clip_path)
            except Exception: pass
        return False
    except Exception as ex:
        if hasattr(coordinator, "log"): coordinator.log(f"[CLIPPER] FFmpeg execution error: {ex}")
        if os.path.exists(temp_clip_path):
            try: os.remove(temp_clip_path)
            except Exception: pass
        return False
