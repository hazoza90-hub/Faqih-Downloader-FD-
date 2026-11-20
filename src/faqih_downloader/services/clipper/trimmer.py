"""
trimmer.py: Local FFmpeg media file trimming in-place with duration verification.
"""
from __future__ import annotations
import os
import sys
import time
import shutil
from typing import Optional, Callable, Any

from ..media_env.ffmpeg_probe import probe_media_duration


def trim_media_file(
    file_path: str, clip_start: float, clip_end: float,
    ffmpeg_bin: Optional[str] = None, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None, audio_boost: bool = False,
    total_duration: float = 0.0, on_progress_pct: Optional[Callable[[float, str], None]] = None,
    probe_duration_fn: Optional[Callable[[str, str], float]] = None,
) -> bool:
    """Trims video or audio file to [clip_start, clip_end] in-place with frame-accurate verification."""
    if clip_end <= clip_start or clip_start < 0 or not os.path.isfile(file_path): return False
    if cancel_event and cancel_event.is_set(): return False
    if not ffmpeg_bin:
        try: from ..media_env_helpers import find_ffmpeg_bin; ffmpeg_bin = find_ffmpeg_bin()
        except Exception: ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        if on_log: on_log("[CLIPPER] FFmpeg binary not found; skipping media trimming.")
        return False

    mce = sys.modules.get("faqih_downloader.services.media_clipper_engine")
    eff_probe = probe_duration_fn or (getattr(mce, "probe_media_duration", None) if mce else None) or probe_media_duration

    base, ext = os.path.splitext(file_path)
    temp_clip = f"{base}.sd_clip_{os.getpid()}_{int(time.time()*1000)}{ext}"
    from ..media_env_helpers import run_ffmpeg_with_progress
    exp_dur = clip_end - clip_start
    copy_ok, is_audio, rc, err = False, ext.lower() in (".mp3", ".m4a", ".aac", ".wav", ".opus", ".flac"), -1, ""
    from ..audio_and_chapters_engine import get_studio_audio_boost_filter
    af_filt = get_studio_audio_boost_filter() if audio_boost else ""
    ac = "libmp3lame" if ext.lower() == ".mp3" else "aac"

    if not audio_boost:
        cmd_copy = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path), "-c", "copy", "-avoid_negative_ts", "make_zero", temp_clip]
        rc, err = run_ffmpeg_with_progress(cmd_copy, cancel_event=cancel_event, total_duration=exp_dur, on_progress_pct=on_progress_pct)
        if rc == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
            actual_dur = eff_probe(temp_clip, ffmpeg_bin)
            if actual_dur > 0 and abs(actual_dur - exp_dur) <= 0.6: copy_ok = True
    else:
        cmd_boost = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path)] + (["-af", af_filt, "-c:a", ac, "-b:a", "192k"] if is_audio else ["-c:v", "copy", "-af", af_filt, "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero"]) + [temp_clip]
        rc, err = run_ffmpeg_with_progress(cmd_boost, cancel_event=cancel_event, total_duration=exp_dur, on_progress_pct=on_progress_pct)
        if rc == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
            actual_dur = eff_probe(temp_clip, ffmpeg_bin)
            if actual_dur > 0 and abs(actual_dur - exp_dur) <= 0.6: copy_ok = True

    if not copy_ok:
        if os.path.exists(temp_clip):
            try: os.remove(temp_clip)
            except Exception: pass
        af_args = ["-af", af_filt] if audio_boost else []
        cmd_rec = [ffmpeg_bin, "-y", "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}", "-i", os.path.abspath(file_path)] + ([*af_args, "-c:a", ac, "-b:a", "192k"] if is_audio else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", *af_args, "-c:a", "aac", "-b:a", "192k"]) + [temp_clip]
        rc, err = run_ffmpeg_with_progress(cmd_rec, cancel_event=cancel_event, total_duration=exp_dur, on_progress_pct=on_progress_pct)

    if rc == 0 and os.path.isfile(temp_clip) and os.path.getsize(temp_clip) > 0:
        for _ in range(4):
            try: os.replace(temp_clip, file_path); break
            except Exception: time.sleep(0.08)
        if on_log: on_log(f"[CLIPPER] Successfully trimmed media: {clip_start:.1f}s -> {clip_end:.1f}s")
        return True
    if os.path.exists(temp_clip):
        try: os.remove(temp_clip)
        except Exception: pass
    if on_log and err: on_log(f"[CLIPPER] Trimming failed: {err[-180:].strip()}")
    return False


__all__ = [
    "trim_media_file",
]
