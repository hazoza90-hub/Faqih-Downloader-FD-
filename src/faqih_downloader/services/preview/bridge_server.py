"""
bridge_server.py: Singleton ephemeral loopback HTTP server lifecycle for the preview bridge.
"""
import http.server
import sys
import threading
from typing import Optional

from .http_handler import PreviewBridgeRequestHandler

_SERVER_LOCK = threading.Lock()
_BRIDGE_SERVER: Optional[http.server.ThreadingHTTPServer] = None
_BRIDGE_PORT: int = 0


def start_preview_bridge(host: str = "127.0.0.1") -> int:
    """Starts the singleton background preview bridge HTTP server on an ephemeral loopback port."""
    global _BRIDGE_SERVER, _BRIDGE_PORT
    with _SERVER_LOCK:
        if _BRIDGE_SERVER is not None and _BRIDGE_PORT > 0:
            return _BRIDGE_PORT
        server = http.server.ThreadingHTTPServer((host, 0), PreviewBridgeRequestHandler)
        server.daemon_threads = True
        _BRIDGE_PORT, _BRIDGE_SERVER = server.server_address[1], server
        psb = sys.modules.get("faqih_downloader.services.preview_stream_bridge")
        if psb is not None:
            try:
                psb._BRIDGE_SERVER = _BRIDGE_SERVER
                psb._BRIDGE_PORT = _BRIDGE_PORT
            except Exception:
                pass
        threading.Thread(target=server.serve_forever, daemon=True, name="SD-PreviewBridge").start()
        return _BRIDGE_PORT


def get_preview_bridge_port() -> int:
    """Returns the active preview bridge port, starting the server if necessary."""
    return _BRIDGE_PORT if _BRIDGE_PORT > 0 else start_preview_bridge()


__all__ = [
    "_SERVER_LOCK",
    "_BRIDGE_SERVER",
    "_BRIDGE_PORT",
    "start_preview_bridge",
    "get_preview_bridge_port",
]
