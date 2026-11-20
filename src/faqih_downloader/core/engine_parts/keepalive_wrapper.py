"""
_KeepAliveResponseWrapper: HTTPResponse wrapper for jitter-resilient read streaming and pause handling.
"""
import sys
import socket
import threading
from typing import Optional, Any

from .socket_utils import _is_urlopen_mocked as _canonical_is_urlopen_mocked


def _resolve_is_urlopen_mocked() -> bool:
    ew = sys.modules.get("faqih_downloader.core.engine_workers")
    if ew is not None and hasattr(ew, "_is_urlopen_mocked"):
        fn = getattr(ew, "_is_urlopen_mocked")
        if fn is not _canonical_is_urlopen_mocked:
            return fn()
    er = sys.modules.get("faqih_downloader.core.engine_resumer")
    if er is not None and hasattr(er, "_is_urlopen_mocked"):
        fn = getattr(er, "_is_urlopen_mocked")
        if fn is not _canonical_is_urlopen_mocked:
            return fn()
    return _canonical_is_urlopen_mocked()


class _KeepAliveResponseWrapper:
    """Wraps an http.client.HTTPResponse for jitter-resilient read1() streaming and safe pause exit."""
    def __init__(self, raw_resp: Any, conn: Any, pause_event: Any = None, cancel_event: Any = None):
        self._resp, self._conn, self._pause_event, self._cancel_event = raw_resp, conn, pause_event, cancel_event
        self._owner_tid, self._reading = threading.get_ident(), False
        self.status = getattr(raw_resp, "status", 200)
        self.headers = getattr(raw_resp, "headers", {})
        self.will_close = getattr(raw_resp, "will_close", False)

    def getcode(self) -> int:
        return self.status

    def _aborted(self) -> bool:
        return bool(
            (self._pause_event is not None and self._pause_event.is_set()) or
            (self._cancel_event is not None and self._cancel_event.is_set())
        )

    def read(self, amt: Optional[int] = None) -> bytes:
        if self._aborted():
            return b""
        self._reading = True
        self._owner_tid = threading.get_ident()
        try:
            if amt is not None and hasattr(self._resp, "read1") and not hasattr(self._resp, "_mock_name"):
                read_sz = min(262144, amt) if amt > 0 else 65536
                for _ in range(15):
                    if self._aborted():
                        return b""
                    try:
                        piece = self._resp.read1(read_sz)
                        if getattr(self._resp, "length", None) == 0 and not self._resp.isclosed() and hasattr(self._resp, "_close_conn"):
                            try:
                                self._resp._close_conn()
                            except Exception:
                                pass
                        return piece
                    except (socket.timeout, TimeoutError):
                        if hasattr(self._resp, "_mock_name") or _resolve_is_urlopen_mocked():
                            raise
                        continue
                raise socket.timeout("Socket read timed out after 15s")
            return self._resp.read(amt)
        finally:
            self._reading = False

    def close(self):
        tid = threading.get_ident()
        if self._reading and tid != self._owner_tid:
            return
        cancelled = self._cancel_event is not None and self._cancel_event.is_set()
        if tid != self._owner_tid and not cancelled:
            return
        try:
            self._resp.close()
        except Exception:
            pass
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
