"""
local_proxy.py: Local loopback HTTP proxy bridge for windowed high-speed media streaming.
"""
from __future__ import annotations

import http.server
import threading
import urllib.parse
import uuid
from typing import Any, Dict, Optional

from .upstream_streamer import stream_upstream_media


class PreviewStreamBridge:
    """Local loopback HTTP proxy bridge for windowed high-speed media streaming."""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self.port: int = 0
        self._server: Optional[http.server.ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._registered_streams: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self) -> int:
        """Starts the local proxy bridge HTTP server on an available port."""
        if self._server is not None and self.port > 0:
            return self.port
        bridge_self = self

        class _BridgeHandler(http.server.BaseHTTPRequestHandler):
            timeout = 15.0

            def log_message(self, format, *args):
                pass

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

            def do_HEAD(self):
                self._serve(is_head=True)

            def do_GET(self):
                self._serve(is_head=False)

            def _serve(self, is_head: bool):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                stream_id = params.get("id", [""])[0]
                with bridge_self._lock:
                    info = bridge_self._registered_streams.get(stream_id)
                if not info:
                    self.send_response(404)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"Stream not found")
                    return
                stream_upstream_media(self, info["url"], info.get("headers") or {}, is_head=is_head)

        server = http.server.ThreadingHTTPServer((self.host, 0), _BridgeHandler)
        server.daemon_threads = True
        self.port = server.server_address[1]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True, name="SD-ClipperStreamBridge")
        self._thread.start()
        return self.port

    def register_stream(self, upstream_url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """Registers an upstream URL and returns a local proxy URL."""
        if self.port == 0:
            self.start()
        sid = uuid.uuid4().hex[:12]
        with self._lock:
            self._registered_streams[sid] = {"url": upstream_url, "headers": headers or {}}
        return f"http://{self.host}:{self.port}/stream?id={sid}"

    def stop(self) -> None:
        """Stops the proxy bridge server and releases resources."""
        with self._lock:
            self._registered_streams.clear()
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
            self.port = 0


__all__ = ["PreviewStreamBridge"]
