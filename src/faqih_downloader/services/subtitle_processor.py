"""
subtitle_processor.py: Thin backward-compatibility shim re-exporting symbols from services.subtitles.
"""
import subprocess
from typing import Dict, Optional, Callable, Any

from .media_env_helpers import (
    find_ffmpeg_bin,
    detect_installed_cookie_browsers,
    run_ffmpeg_with_progress,
)
from .subtitle_downloader import (
    _format_srt_timestamp,
    _format_seconds_to_srt,
    _parse_timestamp_or_seconds,
    _parse_xml_subtitles_to_srt,
    _parse_json_subtitles_to_srt,
    convert_vtt_to_srt,
    download_subtitle_as_srt,
    _translate_srt_cues_via_gtx,
)
from .external_subtitle_service import (
    get_valid_ext_tracks,
    get_protected_ext_langs,
    is_protected_external_srt,
    submit_external_prefetches,
    prepare_srt_once,
    process_external_subtitle_tracks,
    rename_sidecar_srts_on_video_rename,
)
from .subtitles.ffmpeg_exec import (
    IS_WINDOWS,
    run_cancellable_ffmpeg as _exec_run_cancellable_ffmpeg,
    _is_ascii_writable_dir,
    _get_ascii_safe_temp_dir,
)
from .subtitles.muxer import (
    ISO_639_2,
    embed_subtitle_into_mp4 as _muxer_embed_subtitle_into_mp4,
    burn_subtitle_into_video as _muxer_burn_subtitle_into_video,
)
from .subtitles.prefetch import (
    start_subtitle_prefetch as _prefetch_start_subtitle_prefetch,
)
from .subtitles.post_processor import (
    strip_burn_tag_from_filename,
    _strip_burn_with_srts,
    handle_subtitles_post_download as _post_handle_subtitles_post_download,
)


def run_cancellable_ffmpeg(
    cmd,
    cancel_event=None,
    creationflags=0,
    timeout=1800,
    subprocess_mod=None,
    total_duration=0.0,
    on_progress_pct=None,
):
    """Delegates to subtitles.ffmpeg_exec forwarding live module-level subprocess and progress runner."""
    return _exec_run_cancellable_ffmpeg(
        cmd,
        cancel_event=cancel_event,
        creationflags=creationflags,
        timeout=timeout,
        subprocess_mod=(subprocess_mod or subprocess),
        total_duration=total_duration,
        on_progress_pct=on_progress_pct,
        run_ffmpeg_fn=run_ffmpeg_with_progress,
    )


def embed_subtitle_into_mp4(
    video_path: str, srt_path: str, lang_code: str, ffmpeg_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """Delegates to subtitles.muxer forwarding live module-level subprocess and progress runner."""
    return _muxer_embed_subtitle_into_mp4(
        video_path,
        srt_path,
        lang_code,
        ffmpeg_path,
        on_log=on_log,
        cancel_event=cancel_event,
        total_duration=total_duration,
        on_progress_pct=on_progress_pct,
        subprocess_mod=subprocess,
        run_ffmpeg_fn=run_ffmpeg_with_progress,
    )


def burn_subtitle_into_video(
    video_path: str, srt_path: str, ffmpeg_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    subtitle_position: str = "bottom",
    style_config: Optional[Dict[str, Any]] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """Delegates to subtitles.muxer forwarding live module-level subprocess and progress runner."""
    return _muxer_burn_subtitle_into_video(
        video_path,
        srt_path,
        ffmpeg_path,
        on_log=on_log,
        cancel_event=cancel_event,
        subtitle_position=subtitle_position,
        style_config=style_config,
        total_duration=total_duration,
        on_progress_pct=on_progress_pct,
        subprocess_mod=subprocess,
        run_ffmpeg_fn=run_ffmpeg_with_progress,
    )


def start_subtitle_prefetch(stream_info: Any, output_path: str):
    """Delegates to subtitles.prefetch forwarding live module-level download_subtitle_as_srt."""
    return _prefetch_start_subtitle_prefetch(
        stream_info,
        output_path,
        download_fn=download_subtitle_as_srt,
    )


def handle_subtitles_post_download(
    stream_info: Any, output_path: str, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> str:
    """Delegates to subtitles.post_processor forwarding live module-level patch targets."""
    return _post_handle_subtitles_post_download(
        stream_info,
        output_path,
        on_log=on_log,
        cancel_event=cancel_event,
        total_duration=total_duration,
        on_progress_pct=on_progress_pct,
        download_fn=download_subtitle_as_srt,
        find_ffmpeg_fn=find_ffmpeg_bin,
        embed_fn=embed_subtitle_into_mp4,
        burn_fn=burn_subtitle_into_video,
    )


__all__ = [
    "IS_WINDOWS",
    "ISO_639_2",
    "find_ffmpeg_bin",
    "detect_installed_cookie_browsers",
    "run_ffmpeg_with_progress",
    "_format_srt_timestamp",
    "_format_seconds_to_srt",
    "_parse_timestamp_or_seconds",
    "_parse_xml_subtitles_to_srt",
    "_parse_json_subtitles_to_srt",
    "convert_vtt_to_srt",
    "download_subtitle_as_srt",
    "_translate_srt_cues_via_gtx",
    "get_valid_ext_tracks",
    "get_protected_ext_langs",
    "is_protected_external_srt",
    "submit_external_prefetches",
    "prepare_srt_once",
    "process_external_subtitle_tracks",
    "rename_sidecar_srts_on_video_rename",
    "run_cancellable_ffmpeg",
    "_is_ascii_writable_dir",
    "_get_ascii_safe_temp_dir",
    "embed_subtitle_into_mp4",
    "burn_subtitle_into_video",
    "strip_burn_tag_from_filename",
    "_strip_burn_with_srts",
    "start_subtitle_prefetch",
    "handle_subtitles_post_download",
]
