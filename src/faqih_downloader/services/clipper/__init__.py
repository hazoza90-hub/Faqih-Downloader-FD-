"""
clipper package: Subtitle cue ops, clip state sync, media trimming, post-download pipeline, process control, and direct clip downloading.
"""
from .cue_ops import (
    apply_custom_cue_edits,
    clone_clean_subtitle_track,
    filter_and_shift_cues_for_clip,
    merge_bilingual_cues,
    export_cues_to_srt,
)
from .state_sync import (
    sync_clipper_state_from_body,
    enrich_stream_info_with_clip,
    estimate_clip_total_bytes,
)
from .trimmer import trim_media_file
from .post_pipeline import (
    prepare_post_download_subtitles,
    process_post_download_clip_and_subtitles,
)
from .process_control import _set_process_suspended
from .direct_downloader import (
    _format_ffmpeg_headers,
    download_clipped_stream_direct,
)

__all__ = [
    "apply_custom_cue_edits",
    "clone_clean_subtitle_track",
    "filter_and_shift_cues_for_clip",
    "merge_bilingual_cues",
    "export_cues_to_srt",
    "sync_clipper_state_from_body",
    "enrich_stream_info_with_clip",
    "estimate_clip_total_bytes",
    "trim_media_file",
    "prepare_post_download_subtitles",
    "process_post_download_clip_and_subtitles",
    "_set_process_suspended",
    "_format_ffmpeg_headers",
    "download_clipped_stream_direct",
]
