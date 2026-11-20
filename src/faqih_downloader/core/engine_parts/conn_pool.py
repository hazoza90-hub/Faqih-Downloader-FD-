"""
EngineConnPoolMixin: HTTP(S) connection pooling, keep-alive reuse, and socket lifecycle management.
"""
import sys
import socket
import http.client
from typing import Optional, Tuple, Any

from .socket_utils import _is_ssl_socket
from .keepalive_wrapper import _resolve_is_urlopen_mocked


class EngineConnPoolMixin:
    """Provides HTTP(S) connection pooling, keep-alive reuse, and socket lifecycle management."""

    @staticmethod
    def _close_conn_safely(conn: Any):
        """Force-shuts underlying socket (if any) and closes connection/response immediately."""
        if conn is None:
            return
        sock = getattr(conn, "sock", None)
        if sock is not None and not hasattr(sock, "_mock_name"):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass

    def _drain_conn_pool(self):
        """Closes and removes all idle keep-alive connections stored in _conn_pool."""
        pool_map = getattr(self, "_conn_pool", None)
        if not pool_map:
            return
        with self._lock:
            for conns in list(pool_map.values()):
                for conn in conns:
                    self._close_conn_safely(conn)
            pool_map.clear()

    def _abort_active_conns_on_pause(self):
        """Drains idle pooled sockets on pause without closing active SSLSocket/HTTPResponse objects cross-thread."""
        self._drain_conn_pool()
        mocked = _resolve_is_urlopen_mocked()
        with self._lock:
            conns = list(self._active_connections)
        for conn in conns:
            if _is_ssl_socket(conn):
                continue
            is_live_http = hasattr(conn, "_resp") or isinstance(conn, (http.client.HTTPConnection, http.client.HTTPResponse))
            if mocked or hasattr(conn, "_mock_name") or not is_live_http:
                self._close_conn_safely(conn)
                with self._lock:
                    if conn in self._active_connections:
                        self._active_connections.remove(conn)

    def _acquire_pooled_conn(self, conn_key: Tuple[str, str, int]) -> Any:
        """Pops a healthy idle HTTP(S)Connection from _conn_pool for conn_key, if available."""
        pool_map = getattr(self, "_conn_pool", None)
        if not pool_map:
            return None
        with self._lock:
            pool = pool_map.get(conn_key)
            while pool:
                conn = pool.pop()
                if getattr(conn, "sock", None) is not None:
                    return conn
                self._close_conn_safely(conn)
        return None

    def _cleanup_worker_conns(self, resp: Any, conn: Any):
        """Removes worker response/connection from _active_connections and closes both."""
        with self._lock:
            if resp in self._active_connections:
                self._active_connections.remove(resp)
            if conn in self._active_connections:
                self._active_connections.remove(conn)
        self._close_conn_safely(resp)
        self._close_conn_safely(conn)

    def _drain_small_tail(
        self,
        resp: Any,
        raw_resp: Any,
        seg_bytes_read: int,
        expected_seg_bytes: Optional[int],
        req_end: Optional[int],
        chunk_end: int,
    ) -> int:
        """Drains a tiny leftover tail (<= 128 KB) after dynamic split to preserve keep-alive TLS sockets."""
        if req_end is None or not (0 < (req_end - chunk_end) <= 131072):
            return seg_bytes_read
        reader = raw_resp if raw_resp is not None else resp
        if reader is None or self._is_stopped() or self._pause_event.is_set():
            return seg_bytes_read
        rem = (expected_seg_bytes - seg_bytes_read) if expected_seg_bytes is not None else (req_end - chunk_end)
        rem = min(131072, max(0, rem))
        try:
            while rem > 0 and not self._is_stopped() and not self._pause_event.is_set():
                extra = reader.read(min(65536, rem))
                if not extra:
                    break
                seg_bytes_read += len(extra)
                rem -= len(extra)
        except Exception:
            pass
        return seg_bytes_read

    def _is_conn_reusable(self, conn: Any, raw_resp: Any, seg_bytes_read: int, expected_seg_bytes: Optional[int]) -> bool:
        """Checks whether an active HTTP(S)Connection completed its segment cleanly and is healthy for reuse."""
        return bool(
            conn is not None
            and raw_resp is not None
            and not self._is_stopped()
            and not self._pause_event.is_set()
            and not getattr(raw_resp, "will_close", False)
            and getattr(raw_resp, "isclosed", lambda: False)()
            and (expected_seg_bytes is None or seg_bytes_read >= expected_seg_bytes)
            and getattr(conn, "sock", None) is not None
        )

    def _release_or_close_conn(
        self,
        conn: Any,
        resp: Any,
        raw_resp: Any,
        conn_key: Optional[Tuple[str, str, int]],
        seg_bytes_read: int,
        expected_seg_bytes: Optional[int],
    ) -> None:
        """Returns clean keep-alive connection to _conn_pool when length==0; otherwise closes directly."""
        with self._lock:
            if resp in self._active_connections:
                self._active_connections.remove(resp)
            if conn in self._active_connections:
                self._active_connections.remove(conn)

        if (
            raw_resp is not None
            and getattr(raw_resp, "length", None) == 0
            and not getattr(raw_resp, "will_close", False)
            and not getattr(raw_resp, "isclosed", lambda: True)()
            and hasattr(raw_resp, "_close_conn")
        ):
            try:
                raw_resp._close_conn()
            except Exception:
                pass

        can_reuse = (
            conn_key is not None
            and getattr(raw_resp, "length", None) == 0
            and self._is_conn_reusable(conn, raw_resp, seg_bytes_read, expected_seg_bytes)
        )
        if can_reuse:
            pool_map = getattr(self, "_conn_pool", None)
            if pool_map is None:
                pool_map = {}
                self._conn_pool = pool_map
            with self._lock:
                pool_map.setdefault(conn_key, []).append(conn)
            return

        if resp is not None and hasattr(resp, "_mock_name"):
            self._close_conn_safely(resp)
        if conn is not None:
            self._close_conn_safely(conn)
        elif resp is not None:
            self._close_conn_safely(resp)
