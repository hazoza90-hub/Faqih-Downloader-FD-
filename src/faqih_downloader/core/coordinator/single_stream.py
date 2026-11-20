"""
single_stream.py: Progressive and single-stream download execution.
"""
import os
import sys
import time
import threading
from typing import Optional, Callable, Dict, Any, Tuple

from ...services.media_env_helpers import has_ffmpeg
from .mp3_transcoder import transcode_audio_to_mp3


def run_single_stream_download(
    coordinator: Any,
    has_ffmpeg_fn: Optional[Callable[[], bool]] = None,
    transcode_fn: Optional[Callable[..., None]] = None,
    cleanup_ctx: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """Executes progressive/single-stream download with dynamic chunking and optional MP3 transcoding."""
    sc_mod = sys.modules.get("faqih_downloader.core.stream_coordinator")
    eff_has_ffmpeg = has_ffmpeg_fn or (getattr(sc_mod, "has_ffmpeg", None) if sc_mod else None) or has_ffmpeg
    eff_transcode = transcode_fn or transcode_audio_to_mp3

    src_audio_ext = (getattr(coordinator.stream_info, "audio_ext", "") or "").lower()
    is_mp3_request = (
        coordinator.stream_info.is_audio_only
        and (coordinator.destination_path.lower().endswith(".mp3") or coordinator.stream_info.video_ext.lower() == "mp3")
        and src_audio_ext != "mp3"
        and eff_has_ffmpeg()
    )
    if is_mp3_request and not coordinator.destination_path.lower().endswith(".mp3"):
        base, _ = os.path.splitext(coordinator.destination_path)
        coordinator.destination_path = base + ".mp3"
    actual_dest = coordinator.destination_path + ".audio.tmp" if is_mp3_request else coordinator.destination_path
    if cleanup_ctx is not None:
        cleanup_ctx["actual_dest"] = actual_dest
        cleanup_ctx["is_mp3_request"] = is_mp3_request

    plat = getattr(coordinator.stream_info, "platform", "Media")
    tag = plat.upper().replace(" / X", "")
    coordinator.log(f"[{tag}] Initializing dynamic multi-chunk download for: {os.path.basename(coordinator.destination_path)}")

    def _on_single_complete(path, size, elapsed):
        if is_mp3_request:
            eff_transcode(coordinator, actual_dest, elapsed)
        else:
            coordinator._process_subtitles(path)
            path = coordinator.destination_path if (coordinator.destination_path and os.path.isfile(coordinator.destination_path)) else path
            final_sz = os.path.getsize(path) if os.path.isfile(path) else size
            with coordinator._lock: coordinator._is_running = False
            if coordinator.on_complete: coordinator.on_complete(path, final_sz, elapsed)

    safe_conn = max(1, coordinator.max_connections)
    allow_split = (coordinator.max_connections > 1)

    def _on_single_prog(downloaded, total, speed, eta, active):
        if coordinator._is_paused:
            if getattr(engine, "is_running", False) and not getattr(engine, "is_paused", False):
                threading.Thread(target=engine.pause, daemon=True).start()
            coordinator._emit_progress(downloaded, total, 0.0, "Paused", 0); return
        if speed > 0:
            coordinator._last_active_speed = speed
        elif downloaded > 0 and coordinator._last_active_speed <= 0.0:
            st = coordinator.start_time
            el = (time.time() - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
            coordinator._last_active_speed = downloaded / max(0.05, el)
        coordinator._emit_progress(downloaded, total, speed, eta, active)

    def _on_single_error(err):
        with coordinator._lock: coordinator._is_running = False
        if coordinator.on_error: coordinator.on_error(err)

    engine = coordinator._make_engine(
        coordinator.stream_info.video_url, actual_dest, safe_conn, allow_split,
        coordinator.stream_info.video_headers, _on_single_prog, _on_single_complete, _on_single_error,
        getattr(coordinator.stream_info, "video_size", 0),
    )
    with coordinator._lock:
        coordinator.current_engine = engine; coordinator._active_engines = [engine]
    while coordinator._is_paused and not coordinator._cancel_event.is_set(): time.sleep(0.05)
    if not coordinator._cancel_event.is_set(): engine.start()

    while engine.is_running and not coordinator._cancel_event.is_set():
        time.sleep(0.1)
    return actual_dest, is_mp3_request


__all__ = ["run_single_stream_download"]
