"""
cache.py: Thread-safe timedtext base cue cache.
"""
import re
import sys
import threading
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any, Callable

from .parser import _parse_timedtext_to_cues
from .fetcher import _fetch_url_direct, _fetch_urls_with_cookies, _fetch_via_ytdlp

_BASE_TIMEDTEXT_LOCK = threading.Lock()
_BASE_TIMEDTEXT_INFLIGHT: Dict[str, threading.Lock] = {}
_BASE_TIMEDTEXT_CACHE: Dict[str, List[Tuple[float, float, str]]] = {}


def _base_cache_key(url: str) -> str:
    return re.sub(r'([?&])fmt=[^&]*(&|$)', r'\1', url).replace("?&", "?").rstrip("?&")


def _get_cached_base_cues(
    base_cand_url: str,
    sub_track: Dict[str, Any],
    headers: Dict[str, str],
    fetch_direct_fn: Optional[Callable[..., Optional[str]]] = None,
    fetch_cookies_fn: Optional[Callable[..., Any]] = None,
    fetch_ytdlp_fn: Optional[Callable[..., Any]] = None,
) -> List[Tuple[float, float, str]]:
    """Fetches untranslated base timedtext cues once per base URL and shares via thread-safe cache."""
    sd_mod = sys.modules.get("faqih_downloader.services.subtitle_downloader")
    eff_direct = fetch_direct_fn or (getattr(sd_mod, "_fetch_url_direct", None) if sd_mod else None) or _fetch_url_direct
    eff_cookies = fetch_cookies_fn or (getattr(sd_mod, "_fetch_urls_with_cookies", None) if sd_mod else None) or _fetch_urls_with_cookies
    eff_ytdlp = fetch_ytdlp_fn or (getattr(sd_mod, "_fetch_via_ytdlp", None) if sd_mod else None) or _fetch_via_ytdlp

    cache_key = _base_cache_key(base_cand_url)
    with _BASE_TIMEDTEXT_LOCK:
        if cache_key in _BASE_TIMEDTEXT_CACHE:
            return list(_BASE_TIMEDTEXT_CACHE[cache_key])
        key_lock = _BASE_TIMEDTEXT_INFLIGHT.setdefault(cache_key, threading.Lock())
    with key_lock:
        with _BASE_TIMEDTEXT_LOCK:
            if cache_key in _BASE_TIMEDTEXT_CACHE:
                return list(_BASE_TIMEDTEXT_CACHE[cache_key])
        fmt_urls = [
            re.sub(r'([?&]fmt=)[^&]+', rf'\g<1>{fmt}', base_cand_url) if "fmt=" in base_cand_url
            else f"{base_cand_url}{'&' if '?' in base_cand_url else '?'}fmt={fmt}"
            for fmt in ("vtt", "json3", "srv3", "ttml")
        ]
        _parse_ok = lambda txt: _parse_timedtext_to_cues(txt) if (txt and len(txt.strip()) > 10) else []
        clean_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
        parsed_cues: List[Tuple[float, float, str]] = []
        for test_url in fmt_urls:
            parsed_cues = _parse_ok(eff_direct(test_url, clean_headers, timeout=10) or "")
            if parsed_cues: break
        if not parsed_cues:
            parsed_cues = eff_cookies(fmt_urls, dict(headers), _parse_ok, timeout=10) or []
        if not parsed_cues and sub_track.get("webpage_url"):
            qs_lang = urllib.parse.parse_qs(urllib.parse.urlparse(base_cand_url).query).get("lang")
            orig_lang = qs_lang[0] if qs_lang else (sub_track.get("orig_language") or "en")
            parsed_cues = eff_ytdlp(sub_track["webpage_url"], str(orig_lang), sub_track.get("http_headers"), _parse_ok) or []
        if parsed_cues:
            with _BASE_TIMEDTEXT_LOCK:
                if len(_BASE_TIMEDTEXT_CACHE) >= 64:
                    _BASE_TIMEDTEXT_CACHE.clear()
                _BASE_TIMEDTEXT_CACHE[cache_key] = list(parsed_cues)
        return list(parsed_cues)


__all__ = [
    "_BASE_TIMEDTEXT_LOCK",
    "_BASE_TIMEDTEXT_INFLIGHT",
    "_BASE_TIMEDTEXT_CACHE",
    "_base_cache_key",
    "_get_cached_base_cues",
]
