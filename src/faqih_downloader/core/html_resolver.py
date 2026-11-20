"""
Backward-compatibility shim for html_resolver.
All candidate discovery, web scraping parser, and redirect resolution logic
has been decomposed into faqih_downloader.core.resolver.
"""
from .candidate_extractor import (
    _HtmlCandidateExtractor,
    resolve_all_download_candidates,
)
from .resolver.host_guard import (
    _is_private_or_loopback_host,
    _path_filename,
)
from .resolver.html_parser import _HtmlLinkCandidateParser
from .resolver.probe_cache import (
    _PROBE_CACHE_LOCK,
    _PROBE_CACHE,
    _PROBE_CACHE_TTL,
    clear_probe_cache,
    _store_probe_cache,
)
from .resolver.url_resolver import resolve_real_download_url
from .resolver.refresh_validator import validate_refresh_url

__all__ = [
    "_HtmlCandidateExtractor",
    "resolve_all_download_candidates",
    "_is_private_or_loopback_host",
    "_path_filename",
    "_HtmlLinkCandidateParser",
    "_PROBE_CACHE_LOCK",
    "_PROBE_CACHE",
    "_PROBE_CACHE_TTL",
    "clear_probe_cache",
    "_store_probe_cache",
    "resolve_real_download_url",
    "validate_refresh_url",
]
