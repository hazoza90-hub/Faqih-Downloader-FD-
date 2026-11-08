"""
Smart Chapters Selector & Studio Audio Booster Engine (audio_and_chapters_engine.py).
Extracts video chapters from official metadata or description timestamps, and provides
studio-grade voice normalization and audio boosting filters via FFmpeg.
"""
from __future__ import annotations

import os
import re
import time
import shutil
from typing import Dict, List, Optional, Any, Callable


def _parse_timestamp_to_seconds(ts_str: str) -> Optional[float]:
    """Parses 'HH:MM:SS' or 'MM:SS' timestamp string to seconds."""
    if not ts_str:
        return None
    parts = ts_str.strip().split(":")
    try:
        if len(parts) == 2:
            m, s = int(parts[0]), float(parts[1])
            if m < 0 or s < 0 or s >= 60:
                return None
            return m * 60.0 + s
        elif len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            if h < 0 or m < 0 or m >= 60 or s < 0 or s >= 60:
                return None
            return h * 3600.0 + m * 60.0 + s
    except (ValueError, TypeError):
        return None
    return None


def extract_video_chapters(info_dict: Optional[Dict[str, Any]], total_duration: float = 0.0) -> List[Dict[str, Any]]:
    """
    Extracts video chapters as [{"title": str, "start_time": float, "end_time": float}, ...].
    1. Inspects official info_dict.get('chapters') if present and valid.
    2. Smart fallback: regex parses timestamps from description text (e.g. '00:00 Intro', '[03:45] Chapter 1').
    """
    if not info_dict or not isinstance(info_dict, dict):
        return []

    # 1. Official chapters
    raw_chapters = info_dict.get("chapters")
    if isinstance(raw_chapters, list) and len(raw_chapters) > 0:
        cleaned: List[Dict[str, Any]] = []
        for idx, ch in enumerate(raw_chapters):
            if not isinstance(ch, dict):
                continue
            title = str(ch.get("title", f"Chapter {idx + 1}") or f"Chapter {idx + 1}").strip()
            s_t = max(0.0, float(ch.get("start_time", 0.0) or 0.0))
            e_t = float(ch.get("end_time", 0.0) or 0.0)
            cleaned.append({"title": title, "start_time": round(s_t, 2), "end_time": round(e_t, 2)})

        if cleaned:
            # Fix any missing or zero end_time
            for i in range(len(cleaned)):
                if cleaned[i]["end_time"] <= cleaned[i]["start_time"]:
                    if i + 1 < len(cleaned):
                        cleaned[i]["end_time"] = cleaned[i + 1]["start_time"]
                    elif total_duration > cleaned[i]["start_time"]:
                        cleaned[i]["end_time"] = round(total_duration, 2)
                    else:
                        cleaned[i]["end_time"] = round(cleaned[i]["start_time"] + 60.0, 2)
            return cleaned

    # 2. Smart fallback from description
    desc = str(info_dict.get("description", "") or "").strip()
    if not desc:
        return []

    ts_pattern = re.compile(r'(?:^|[\s\[\(])(\d{1,2}:\d{2}(?::\d{2})?)(?:[\s\]\)]|$)')
    candidates: List[tuple[float, str]] = []

    for line in desc.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        m = ts_pattern.search(line_s)
        if not m:
            continue
        ts_str = m.group(1)
        sec = _parse_timestamp_to_seconds(ts_str)
        if sec is None or sec < 0:
            continue

        raw_title = line_s[:m.start(1)] + line_s[m.end(1):]
        title = re.sub(r'^[\[\(\]\)\s\-–—:|•~]+', '', raw_title)
        title = re.sub(r'[\[\(\]\)\s\-–—:|•~]+$', '', title).strip()
        if not title:
            title = f"Chapter {ts_str}"
        candidates.append((sec, title))

    if not candidates:
        return []

    # Sort by start_time
    candidates.sort(key=lambda x: x[0])

    # Deduplicate consecutive timestamps and build chapters
    unique: List[tuple[float, str]] = []
    for sec, title in candidates:
        if not unique or abs(sec - unique[-1][0]) > 0.5:
            unique.append((sec, title))

    if len(unique) < 2 and (not unique or unique[0][0] != 0.0):
        if not unique or total_duration <= 0:
            return []

    chapters_result: List[Dict[str, Any]] = []
    tot = float(total_duration or 0.0)

    for i, (s_t, title) in enumerate(unique):
        if i + 1 < len(unique):
            e_t = unique[i + 1][0]
        elif tot > s_t:
            e_t = tot
        else:
            e_t = s_t + 60.0
        chapters_result.append({
            "title": title,
            "start_time": round(s_t, 2),
            "end_time": round(max(s_t + 1.0, e_t), 2),
        })

    return chapters_result


def get_studio_audio_boost_filter(preset: str = "boost") -> str:
    """
    Returns standard studio audio normalization & vocal boost FFmpeg audio filter string.
    Supported across all standard FFmpeg releases without external plugins.
    """
    return "highpass=f=75,acompressor=threshold=-18dB:ratio=2.8:attack=15:release=150:makeup=2.2,volume=1.45"


def apply_audio_boost_to_file(
    file_path: str,
    ffmpeg_bin: Optional[str] = None,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
) -> bool:
    """
    Applies the studio vocal boost and normalizer filter to an existing video or audio file.
    For video files (.mp4/.mkv), video stream is copied (-c:v copy) to avoid video re-encoding.
    Replaces original file in-place atomically.
    """
    if cancel_event and cancel_event.is_set():
        return False
    if not file_path or not os.path.isfile(file_path):
        return False

    if not ffmpeg_bin:
        try:
            from .media_env_helpers import find_ffmpeg_bin
            ffmpeg_bin = find_ffmpeg_bin()
        except Exception:
            ffmpeg_bin = shutil.which("ffmpeg")

    if not ffmpeg_bin:
        if on_log:
            on_log("[AUDIO-BOOST] FFmpeg binary not found; skipping audio boost.")
        return False

    base, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()
    temp_out = f"{base}.sd_boost_{os.getpid()}_{int(time.time() * 1000)}{ext}"
    af_filter = get_studio_audio_boost_filter()
    is_audio = ext_lower in (".mp3", ".m4a", ".aac", ".wav", ".opus", ".flac", ".ogg")

    if is_audio:
        acodec = "libmp3lame" if ext_lower == ".mp3" else ("flac" if ext_lower == ".flac" else "aac")
        cmd = [
            ffmpeg_bin, "-y", "-i", os.path.abspath(file_path),
            "-af", af_filter, "-c:a", acodec,
        ]
        if acodec not in ("flac",):
            cmd.extend(["-b:a", "192k"])
        cmd.append(temp_out)
    else:
        cmd = [
            ffmpeg_bin, "-y", "-i", os.path.abspath(file_path),
            "-c:v", "copy",
            "-af", af_filter,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            temp_out
        ]

    try:
        from .subtitle_processor import run_cancellable_ffmpeg
        res = run_cancellable_ffmpeg(cmd, cancel_event=cancel_event)
    except Exception as exc:
        if on_log:
            on_log(f"[AUDIO-BOOST] FFmpeg execution error: {exc}")
        if os.path.exists(temp_out):
            try:
                os.remove(temp_out)
            except Exception:
                pass
        return False

    if res.returncode == 0 and os.path.isfile(temp_out) and os.path.getsize(temp_out) > 0:
        for _ in range(5):
            try:
                os.replace(temp_out, file_path)
                if on_log:
                    on_log(f"[AUDIO-BOOST] Successfully applied studio voice normalizer & boost to {os.path.basename(file_path)}")
                return True
            except Exception:
                time.sleep(0.08)

    if os.path.exists(temp_out):
        try:
            os.remove(temp_out)
        except Exception:
            pass
    if on_log and getattr(res, "stderr", None):
        on_log(f"[AUDIO-BOOST] Audio boost failed: {res.stderr[-180:].strip()}")
    return False
