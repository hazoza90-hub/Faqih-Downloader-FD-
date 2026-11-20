"""
mp3_transcoder.py: FFmpeg MP3 audio transcoding post-step for audio-only MP3 downloads.
"""
import os
import sys
import subprocess
from typing import Optional, Callable, Any, Tuple

from ...config import IS_WINDOWS
from ...services.media_env_helpers import find_ffmpeg_bin, run_ffmpeg_with_progress


def transcode_audio_to_mp3(
    coordinator: Any,
    actual_dest: str,
    elapsed: float,
    find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None,
    run_ffmpeg_fn: Optional[Callable[..., Tuple[int, str]]] = None,
) -> None:
    """Transcodes downloaded temporary audio stream into final MP3 destination via FFmpeg."""
    sc_mod = sys.modules.get("faqih_downloader.core.stream_coordinator")
    eff_find_ffmpeg = find_ffmpeg_fn or (getattr(sc_mod, "find_ffmpeg_bin", None) if sc_mod else None) or find_ffmpeg_bin
    eff_run_ffmpeg = run_ffmpeg_fn or (getattr(sc_mod, "run_ffmpeg_with_progress", None) if sc_mod else None) or run_ffmpeg_with_progress

    coordinator.log("[FFMPEG] Transcoding downloaded audio stream to universal MP3...")
    try:
        ffmpeg_bin = eff_find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable not found.")
        cmd = [ffmpeg_bin, "-y", "-i", actual_dest, "-vn", "-c:a", "libmp3lame", "-q:a", "2", coordinator.destination_path]
        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0
        def _mp3_prog(pct: float, eta_str: str): coordinator._emit_stage_progress("Transcoding", pct, eta_str)
        v_dur = float(getattr(coordinator.stream_info, "duration", 0.0) or 0.0)
        rc, err = eff_run_ffmpeg(
            cmd, cancel_event=coordinator._cancel_event, creationflags=cflags,
            total_duration=v_dur, on_progress_pct=_mp3_prog, subprocess_mod=subprocess,
        )
        if rc != 0:
            raise RuntimeError(f"FFmpeg MP3 transcoding failed: {err.strip()}")
        coordinator._safe_remove_paths(actual_dest)
        final_sz = os.path.getsize(coordinator.destination_path)
        coordinator.log(f"[SUCCESS] Audio converted to MP3 successfully ({final_sz:,} bytes)!")
        with coordinator._lock: coordinator._is_running = False
        if coordinator.on_complete: coordinator.on_complete(coordinator.destination_path, final_sz, elapsed)
    except Exception as ex:
        coordinator._safe_remove_paths(actual_dest, coordinator.destination_path)
        with coordinator._lock: coordinator._is_running = False
        if coordinator.on_error: coordinator.on_error(f"MP3 transcoding error: {ex}")


__all__ = ["transcode_audio_to_mp3"]
