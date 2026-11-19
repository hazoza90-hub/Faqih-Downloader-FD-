"""
subtitles package: Subtitle parsing, translation, fetching, caching, downloading, FFmpeg muxing, and prefetching.
"""
from .parser import (
    _format_srt_timestamp,
    _format_seconds_to_srt,
    _parse_timestamp_or_seconds,
    _parse_xml_subtitles_to_srt,
    _parse_json_subtitles_to_srt,
    _parse_xml_to_cues,
    _parse_json_to_cues,
    _parse_vtt_to_cues,
    _parse_timedtext_to_cues,
    _format_cues_to_srt,
    convert_vtt_to_srt,
    _strip_tlang_param,
)
from .translator import _translate_srt_cues_via_gtx
from .fetcher import (
    _fetch_url_direct,
    _fetch_urls_with_cookies,
    _fetch_via_ytdlp,
)
from .cache import (
    _BASE_TIMEDTEXT_LOCK,
    _BASE_TIMEDTEXT_INFLIGHT,
    _BASE_TIMEDTEXT_CACHE,
    _base_cache_key,
    _get_cached_base_cues,
)
from .downloader import download_subtitle_as_srt
from .ffmpeg_exec import (
    IS_WINDOWS,
    run_cancellable_ffmpeg,
    _is_ascii_writable_dir,
    _get_ascii_safe_temp_dir,
)
from .muxer import (
    ISO_639_2,
    embed_subtitle_into_mp4,
    burn_subtitle_into_video,
)
from .prefetch import start_subtitle_prefetch
from .post_processor import (
    strip_burn_tag_from_filename,
    _strip_burn_with_srts,
    handle_subtitles_post_download,
)

__all__ = [
    "_format_srt_timestamp",
    "_format_seconds_to_srt",
    "_parse_timestamp_or_seconds",
    "_parse_xml_subtitles_to_srt",
    "_parse_json_subtitles_to_srt",
    "_parse_xml_to_cues",
    "_parse_json_to_cues",
    "_parse_vtt_to_cues",
    "_parse_timedtext_to_cues",
    "_format_cues_to_srt",
    "convert_vtt_to_srt",
    "_strip_tlang_param",
    "_translate_srt_cues_via_gtx",
    "_fetch_url_direct",
    "_fetch_urls_with_cookies",
    "_fetch_via_ytdlp",
    "_BASE_TIMEDTEXT_LOCK",
    "_BASE_TIMEDTEXT_INFLIGHT",
    "_BASE_TIMEDTEXT_CACHE",
    "_base_cache_key",
    "_get_cached_base_cues",
    "download_subtitle_as_srt",
    "IS_WINDOWS",
    "run_cancellable_ffmpeg",
    "_is_ascii_writable_dir",
    "_get_ascii_safe_temp_dir",
    "ISO_639_2",
    "embed_subtitle_into_mp4",
    "burn_subtitle_into_video",
    "start_subtitle_prefetch",
    "strip_burn_tag_from_filename",
    "_strip_burn_with_srts",
    "handle_subtitles_post_download",
]
