"""
dual_merger.py: Dual-stream audio completeness recovery, FFmpeg video+audio merge, and completion emission.
"""
import os
import time
from typing import Any, List

from .dual_stream import _drain_engine_workers


def merge_dual_streams(
    coordinator: Any,
    video_tmp: str,
    audio_tmp: str,
    tag: str,
    plat: str,
    a_error: List[str],
    v_engine: Any = None,
    a_engine: Any = None,
) -> None:
    """Validates/recovers audio stream, merges video+audio via FFmpeg, and runs post-download subtitle/clip steps."""
    from ...services.media_env_helpers import ensure_complete_audio_file
    if not ensure_complete_audio_file(coordinator.stream_info, audio_tmp, tag, coordinator.log, has_prior_error=bool(a_error)):
        if v_engine is not None:
            v_engine.cancel()
        _drain_engine_workers(v_engine, a_engine)
        err_msg = a_error[0] if a_error else "Audio stream is incomplete or missing and recovery failed"
        raise RuntimeError(f"Audio stream download error: {err_msg}")

    # 3. Merge Phase via FFmpeg
    coordinator._active_phase = 3
    with coordinator._lock: coordinator._active_engines.clear()
    combined_total = max(1, coordinator._v_total_size + coordinator._a_total_size)
    coordinator.log(f"[{tag}] Phase 2/2: Merging video and audio streams into final container...")
    def _merge_prog(pct: float, eta_str: str): coordinator._emit_stage_progress("Merging", pct, eta_str)
    from ...services.youtube_service import YouTubeResolver
    v_dur = float(getattr(coordinator.stream_info, "duration", 0.0) or 0.0)
    boost_on = bool(getattr(coordinator.stream_info, "audio_boost_enabled", False))
    YouTubeResolver.merge_video_audio(
        video_tmp, audio_tmp, coordinator.destination_path,
        on_log=coordinator.log, cancel_event=coordinator._cancel_event,
        total_duration=v_dur, on_progress_pct=_merge_prog, audio_boost=boost_on,
    )
    if boost_on: setattr(coordinator.stream_info, "_audio_boost_applied", True)
    coordinator._process_subtitles(coordinator.destination_path)

    elapsed = max(0.01, time.time() - coordinator.start_time)
    final_size = os.path.getsize(coordinator.destination_path) if os.path.isfile(coordinator.destination_path) else combined_total
    coordinator.log(f"[SUCCESS] {plat} media assembled & merged successfully ({final_size:,} bytes in {elapsed:.1f}s)!")
    with coordinator._lock: coordinator._is_running = False
    if coordinator.on_complete:
        coordinator.on_complete(coordinator.destination_path, final_size, elapsed)


__all__ = ["merge_dual_streams"]
