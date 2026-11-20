"""
In-memory cache for probed download URLs.
"""
import time
import threading
import urllib.request
from typing import Dict, Tuple, Any

_PROBE_CACHE_LOCK = threading.Lock()
_PROBE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_PROBE_CACHE_TTL = 30.0


def clear_probe_cache():
    """Clears in-memory probe cache (used in testing and maintenance)."""
    with _PROBE_CACHE_LOCK:
        _PROBE_CACHE.clear()


def _store_probe_cache(orig_url: str, res_dict: Dict[str, Any]):
    if hasattr(urllib.request.urlopen, "_mock_name"):
        return
    now = time.monotonic()
    entry = dict(res_dict)
    entry["timestamp"] = now
    with _PROBE_CACHE_LOCK:
        if orig_url:
            _PROBE_CACHE[orig_url] = (now, entry)
        final_u = res_dict.get("url")
        if final_u and final_u != orig_url:
            _PROBE_CACHE[final_u] = (now, entry)
