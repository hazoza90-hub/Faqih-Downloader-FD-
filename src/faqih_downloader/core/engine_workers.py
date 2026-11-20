"""
Backward-compatibility shim for engine_workers.
Logic has moved to faqih_downloader.core.engine_parts.
"""
import time

from .chunk import DownloadChunk
from .engine_parts.socket_utils import (
    GOOGLEVIDEO_WINDOW_BYTES,
    _configure_fast_socket,
    _build_window_url,
    _is_urlopen_mocked,
    _is_ssl_socket,
)
from .engine_parts.keepalive_wrapper import _KeepAliveResponseWrapper
from .engine_parts.resumer import EngineResumerMixin
from .engine_parts.workers import EngineWorkersMixin
from ..utils.url_utils import parse_filename_from_cd_header

__all__ = [
    "EngineWorkersMixin",
    "EngineResumerMixin",
    "GOOGLEVIDEO_WINDOW_BYTES",
    "_configure_fast_socket",
    "_KeepAliveResponseWrapper",
    "_build_window_url",
    "_is_urlopen_mocked",
    "_is_ssl_socket",
    "DownloadChunk",
    "parse_filename_from_cd_header",
    "time",
]
