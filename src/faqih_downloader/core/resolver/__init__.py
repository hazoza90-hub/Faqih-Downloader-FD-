"""
Resolver subpackage: Host validation, HTML candidate parsing, probe caching,
URL resolution, and refresh link validation.
"""
from .host_guard import (
    _is_private_or_loopback_host,
    _path_filename,
)
from .html_parser import _HtmlLinkCandidateParser
from .probe_cache import (
    _PROBE_CACHE_LOCK,
    _PROBE_CACHE,
    _PROBE_CACHE_TTL,
    clear_probe_cache,
    _store_probe_cache,
)
from .url_resolver import resolve_real_download_url
from .refresh_validator import validate_refresh_url

__all__ = [
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
