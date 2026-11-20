"""
Backward-compatibility shim for engine_resumer.
Logic has moved to faqih_downloader.core.engine_parts.
"""
from .engine_parts.socket_utils import (
    _build_window_url,
    _is_urlopen_mocked,
    _is_ssl_socket,
)
from .engine_parts.conn_pool import EngineConnPoolMixin
from .engine_parts.resumer import EngineResumerMixin
from .resolver.refresh_validator import validate_refresh_url

__all__ = [
    "EngineResumerMixin",
    "EngineConnPoolMixin",
    "_build_window_url",
    "_is_urlopen_mocked",
    "_is_ssl_socket",
    "validate_refresh_url",
]
