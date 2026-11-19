"""
subtitle_downloader.py: Thin backward-compatibility shim re-exporting symbols from services.subtitles.
"""
from typing import Dict, List, Optional, Tuple, Any

from .media_env import detect_installed_cookie_browsers, _resolve_cookie_browser
from .subtitles.parser import (
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
from .subtitles.translator import _translate_srt_cues_via_gtx
from .subtitles.fetcher import (
    _fetch_url_direct,
    _fetch_urls_with_cookies,
    _fetch_via_ytdlp,
)
from .subtitles.cache import (
    _BASE_TIMEDTEXT_LOCK,
    _BASE_TIMEDTEXT_INFLIGHT,
    _BASE_TIMEDTEXT_CACHE,
    _base_cache_key,
    _get_cached_base_cues as _cache_get_cached_base_cues,
)
from .subtitles.downloader import (
    download_subtitle_as_srt as _dl_download_subtitle_as_srt,
)


def _get_cached_base_cues(
    base_cand_url: str,
    sub_track: Dict[str, Any],
    headers: Dict[str, str],
) -> List[Tuple[float, float, str]]:
    """Delegates to subtitles.cache while forwarding live module-level fetcher references."""
    return _cache_get_cached_base_cues(
        base_cand_url,
        sub_track,
        headers,
        fetch_direct_fn=_fetch_url_direct,
        fetch_cookies_fn=_fetch_urls_with_cookies,
        fetch_ytdlp_fn=_fetch_via_ytdlp,
    )


def download_subtitle_as_srt(sub_track: Dict[str, Any], video_filepath: str) -> Optional[str]:
    """Delegates to subtitles.downloader while forwarding live module-level patch targets."""
    return _dl_download_subtitle_as_srt(
        sub_track,
        video_filepath,
        fetch_direct_fn=_fetch_url_direct,
        translate_fn=_translate_srt_cues_via_gtx,
        get_base_cues_fn=_get_cached_base_cues,
        fetch_cookies_fn=_fetch_urls_with_cookies,
        fetch_ytdlp_fn=_fetch_via_ytdlp,
    )


__all__ = [
    "detect_installed_cookie_browsers",
    "_resolve_cookie_browser",
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
]
