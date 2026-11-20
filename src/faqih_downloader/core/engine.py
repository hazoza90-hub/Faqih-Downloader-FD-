"""
TurboDownloadEngine: Multi-threaded dynamic chunking, resume, assembly, and throttling download engine.
"""
import os
import sys
import time
import urllib.request
import threading
import ssl
from collections import deque
from typing import List, Optional, Callable, Dict, Any, Tuple

from .rate_limiter import TokenBucketRateLimiter
from .chunk import DownloadChunk, get_permissive_ssl_context
from .engine_persistence import EnginePersistenceMixin
from .engine_workers import EngineWorkersMixin
from .engine_parts import (
    EngineLifecycleMixin,
    EngineProberMixin,
    EngineSupervisorMixin,
)


class TurboDownloadEngine(
    EngineLifecycleMixin,
    EngineProberMixin,
    EngineSupervisorMixin,
    EngineWorkersMixin,
    EnginePersistenceMixin
):
    """
    High-throughput download engine featuring dynamic chunking, streaming buffers, and rate limiting.
    """
    def __init__(
        self,
        url: str,
        destination_path: str,
        max_connections: int = 8,
        min_split_threshold: int = 128 * 1024,  # 128 KB minimum remaining to allow split
        rate_limit_bytes_per_sec: float = 0.0,
        ssl_context: Optional[ssl.SSLContext] = None,
        opener: Optional[urllib.request.OpenerDirector] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_dynamic_split: bool = True,
        on_progress: Optional[Callable] = None,
        on_chunk_update: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        pre_probed_info: Optional[Dict[str, Any]] = None
    ):
        self.url = url
        self.destination_path = destination_path
        self.max_connections = max(1, min(max_connections, 32))
        self.min_split_threshold = max(64 * 1024, min_split_threshold)
        self.rate_limiter = TokenBucketRateLimiter(rate_limit_bytes_per_sec)
        self.ssl_context = ssl_context if ssl_context is not None else get_permissive_ssl_context()
        self.opener = opener if opener is not None else urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.ssl_context))
        self.headers: Dict[str, str] = dict(headers) if headers else {}

        # YouTube googlevideo CDN detection
        self.is_googlevideo = self.is_googlevideo_url(self.url)
        self.allow_dynamic_split = bool(allow_dynamic_split)

        self.on_progress = on_progress
        self.on_chunk_update = on_chunk_update
        self.on_log = on_log
        self.on_complete = on_complete
        self.on_error = on_error

        self.total_size, self.supports_ranges = 0, False
        self.expected_sha256: Optional[str] = None
        self.expected_crc32: Optional[str] = None
        self.content_type: str = ""
        self.filename = os.path.basename(destination_path)
        self.temp_dir = destination_path + ".sd_parts"
        for leg in (destination_path + ".tdm_parts", destination_path + ".idm_parts"):
            if os.path.isdir(leg) and not os.path.exists(self.temp_dir):
                try:
                    os.replace(leg, self.temp_dir)
                    break
                except Exception:
                    pass

        self.pre_probed_info = dict(pre_probed_info) if pre_probed_info else None
        self._has_pre_probed = False
        if self.pre_probed_info:
            p_ts = self.pre_probed_info.get("timestamp")
            is_fresh = (p_ts is None) or ((time.monotonic() - float(p_ts)) < 30.0)
            p_url = self.pre_probed_info.get("url") or self.pre_probed_info.get("real_url")
            cand_url = p_url or self.url
            clen_sz = self._extract_googlevideo_clen(cand_url) if (self.is_googlevideo or "googlevideo.com" in str(cand_url).lower()) else 0
            p_size = clen_sz if clen_sz > 0 else (self.pre_probed_info.get("total_size") or self.pre_probed_info.get("size") or 0)
            if is_fresh and p_size > 0:
                if p_url:
                    self.url = p_url
                    if self.is_googlevideo_url(self.url):
                        self.is_googlevideo = True
                self.total_size = int(p_size)
                self.supports_ranges = bool(self.pre_probed_info.get("supports_ranges", True))
                self.content_type = str(self.pre_probed_info.get("content_type") or "")
                p_fn = self.pre_probed_info.get("filename")
                if p_fn:
                    self.filename = p_fn
                    if os.path.isdir(self.destination_path) or self.destination_path.endswith(("/", "\\")):
                        self.destination_path = os.path.join(self.destination_path, self.filename)
                        self.temp_dir = self.destination_path + ".sd_parts"
                self._has_pre_probed = True

        self.chunks: List[DownloadChunk] = []
        self.active_workers: List[threading.Thread] = []
        self._worker_threads: Dict[int, threading.Thread] = {}
        self._active_connections: List[urllib.request.addinfourl] = []
        self._conn_pool: Dict[Tuple[str, str, int], list] = {}

        self._lock = threading.RLock()
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._error_abort_event = threading.Event()
        self.is_running = False
        self.is_paused = False
        self.has_expired_link = False
        self.last_http_status = 0
        self._resume_mode = False

        # Speed calculation metrics
        self.start_time = 0.0
        self.last_speed_check_time = self._last_speed_time = 0.0
        self.last_downloaded_bytes = self._last_speed_bytes = 0
        self.current_speed = 0.0
        self._speed_samples: deque = deque()
        self._accumulated_active_sec = 0.0
        self._last_active_start_mono: Optional[float] = None
        self._session_start_bytes: int = 0


__all__ = ["TurboDownloadEngine", "EngineWorkersMixin"]
