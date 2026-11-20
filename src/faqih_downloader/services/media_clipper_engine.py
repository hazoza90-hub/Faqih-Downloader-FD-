"""
media_clipper_engine.py: Thin backward-compatibility shim re-exporting symbols from services.clipper.
"""
from typing import Optional, Callable, Any

from .media_env.ffmpeg_probe import probe_media_duration
from .clipper.cue_ops import (
    apply_custom_cue_edits,
    clone_clean_subtitle_track,
    filter_and_shift_cues_for_clip,
    merge_bilingual_cues,
    export_cues_to_srt,
)
from .clipper.state_sync import (
    sync_clipper_state_from_body,
    enrich_stream_info_with_clip,
    estimate_clip_total_bytes,
)
from .clipper.trimmer import trim_media_file as _clipper_trim_media_file
from .clipper.post_pipeline import (
    prepare_post_download_subtitles,
    process_post_download_clip_and_subtitles as _clipper_process_post_download_clip_and_subtitles,
)
from .clipper.process_control import _set_process_suspended
from .clipper.direct_downloader import (
    _format_ffmpeg_headers,
    download_clipped_stream_direct as _clipper_download_clipped_stream_direct,
)


def trim_media_file(
    file_path: str, clip_start: float, clip_end: float,
    ffmpeg_bin: Optional[str] = None, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None, audio_boost: bool = False,
    total_duration: float = 0.0, on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """Delegates to clipper.trimmer forwarding live module-level probe_media_duration."""
    return _clipper_trim_media_file(
        file_path, clip_start, clip_end,
        ffmpeg_bin=ffmpeg_bin, on_log=on_log, cancel_event=cancel_event,
        audio_boost=audio_boost, total_duration=total_duration,
        on_progress_pct=on_progress_pct, probe_duration_fn=probe_media_duration,
    )


def process_post_download_clip_and_subtitles(
    stream_info: Any, target_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    on_stage_progress: Optional[Callable[[str, float, str], None]] = None,
) -> str:
    """Delegates to clipper.post_pipeline forwarding live module-level trim and probe patch targets."""
    return _clipper_process_post_download_clip_and_subtitles(
        stream_info, target_path,
        on_log=on_log, cancel_event=cancel_event,
        on_stage_progress=on_stage_progress,
        trim_fn=trim_media_file, probe_duration_fn=probe_media_duration,
    )


def download_clipped_stream_direct(coordinator: Any) -> bool:
    """Delegates to clipper.direct_downloader forwarding live module-level _set_process_suspended."""
    return _clipper_download_clipped_stream_direct(
        coordinator, set_suspended_fn=_set_process_suspended,
    )


__all__ = [
    "apply_custom_cue_edits",
    "clone_clean_subtitle_track",
    "filter_and_shift_cues_for_clip",
    "merge_bilingual_cues",
    "probe_media_duration",
    "export_cues_to_srt",
    "trim_media_file",
    "prepare_post_download_subtitles",
    "process_post_download_clip_and_subtitles",
    "sync_clipper_state_from_body",
    "enrich_stream_info_with_clip",
    "estimate_clip_total_bytes",
    "_format_ffmpeg_headers",
    "_set_process_suspended",
    "download_clipped_stream_direct",
]
