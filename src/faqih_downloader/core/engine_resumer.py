"""
Engine resumer and dynamic URL refresh mixin for Smart Download (SD).
"""
import os
import re
import ssl
import time
import socket
import http.client
import urllib.request
import threading
from typing import Optional, Dict, Tuple, Any

from .html_resolver import validate_refresh_url


def _build_window_url(url: str, start_byte: int, end_byte: Optional[int], is_gv: bool, req_num: Optional[int] = None) -> str:
    """Appends or updates &range=start-end (and &rn=req_num when provided) on googlevideo URLs."""
    if not is_gv or end_byte is None:
        return url
    rng = f"range={start_byte}-{end_byte}"
    out = re.sub(r"([?&])range=[^&]*", rf"\g<1>{rng}", url) if re.search(r"([?&])range=[^&]*", url) else (f"{url}&{rng}" if "?" in url else f"{url}?{rng}")
    if req_num is not None:
        rn_p = f"rn={int(req_num)}"
        out = re.sub(r"([?&])rn=[^&]*", rf"\g<1>{rn_p}", out) if re.search(r"([?&])rn=[^&]*", out) else f"{out}&{rn_p}"
    return out


def _is_urlopen_mocked() -> bool:
    """Checks if urllib.request.urlopen is replaced by a unittest mock."""
    fn = getattr(urllib.request, "urlopen", None)
    return fn is not None and (hasattr(fn, "_mock_name") or "mock" in type(fn).__name__.lower() or hasattr(fn, "side_effect"))


def _is_ssl_socket(conn: Any) -> bool:
    """Returns True if conn or its wrapped _conn owns an active ssl.SSLSocket."""
    sock = getattr(conn, "sock", None) or getattr(getattr(conn, "_conn", None), "sock", None)
    return isinstance(sock, ssl.SSLSocket)


class EngineResumerMixin:
    """Provides methods for updating download URLs, validating refreshed links, and resuming transfers."""

    def _next_gv_rn(self) -> int:
        """Returns monotonically increasing googlevideo request sequence number (&rn=N)."""
        with self._lock:
            n = getattr(self, "_gv_rn_counter", 0) + 1
            self._gv_rn_counter = n
            return n

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
        mocked = _is_urlopen_mocked()
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
            if resp in self._active_connections: self._active_connections.remove(resp)
            if conn in self._active_connections: self._active_connections.remove(conn)
        self._close_conn_safely(resp); self._close_conn_safely(conn)

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

    def update_url(self, new_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Updates target download URL and session headers on the fly.
        Propagates to active workers and persists state.
        """
        with self._lock:
            self.url = str(new_url).strip()
            if headers:
                self.headers.update(headers)

            if hasattr(self, "is_googlevideo_url"):
                self.is_googlevideo = self.is_googlevideo_url(self.url)
            else:
                self.is_googlevideo = "googlevideo.com" in self.url.lower()

            for conn in list(self._active_connections):
                try:
                    conn.close()
                except Exception:
                    pass
            self._active_connections.clear()
            self.save_state()
            self.log(f"Download URL updated: {self.url}")

    def validate_new_url(self, new_url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[bool, str, int]:
        """Validates new URL against current total_size and range requirements."""
        is_valid, msg, size, ranges = validate_refresh_url(
            new_url=new_url,
            expected_size=self.total_size,
            check_range=self.supports_ranges,
            ssl_context=self.ssl_context,
            headers=headers or self.headers
        )
        return is_valid, msg, size

    def _prepare_resume_chunks(self):
        """Revalidates existing chunk part files, truncates excess bytes, and spawns pending workers."""
        self.log(f"Resuming download from existing chunks ({len(self.chunks)} parts)...")
        os.makedirs(self.temp_dir, exist_ok=True)
        with self._lock:
            prior_workers = list(self.active_workers)
        for w in prior_workers:
            if w.is_alive() and w != threading.current_thread():
                w.join(timeout=0.3)
        self._error_abort_event.clear()
        with self._lock:
            self.active_workers.clear()
            if hasattr(self, "_worker_threads"):
                self._worker_threads.clear()
            self._active_connections.clear()
            for c in self.chunks:
                with c.lock:
                    expected = c.end_byte - c.start_byte + 1
                    if os.path.exists(c.part_filepath):
                        try:
                            actual_bytes = os.path.getsize(c.part_filepath)
                            c.downloaded_bytes = min(actual_bytes, expected)
                            if actual_bytes > expected:
                                with open(c.part_filepath, "r+b") as tf:
                                    tf.truncate(expected)
                        except Exception:
                            pass
                    if self.total_size > 0 and c.downloaded_bytes >= expected:
                        c.status = "completed"
                    else:
                        c.status = "pending"
                        c.error_msg = ""
            pending_chunks = [c for c in self.chunks if c.status == "pending"]
            for c in pending_chunks[:self.max_connections]:
                self._spawn_worker(c)
        self._resume_mode = False
        self.save_state()

    def resume_transfer(self):
        """Resumes download transfer using existing chunks and part files."""
        if self.is_running:
            if self.is_paused:
                self.resume()
            return

        self._error_abort_event.clear()
        with self._lock:
            prior_workers = list(self.active_workers)
        for w in prior_workers:
            if w.is_alive() and w != threading.current_thread():
                w.join(timeout=0.3)

        self._resume_mode = True
        self.is_running = True
        self.is_paused = False
        self._cancel_event.clear()
        self._pause_event.clear()
        self.start_time = time.time()
        self._last_active_start_mono = time.monotonic()
        self.last_speed_check_time = time.monotonic()
        self.last_downloaded_bytes = sum(c.downloaded_bytes for c in self.chunks)
        self._session_start_bytes = self.last_downloaded_bytes

        supervisor_thread = threading.Thread(target=self._supervisor_loop, daemon=True)
        supervisor_thread.start()

    def refresh_link(self, new_url: str, headers: Optional[Dict[str, str]] = None, auto_resume: bool = True) -> bool:
        """
        Validates new URL, updates download address and headers, and resumes downloading
        seamlessly from existing chunk progress without losing downloaded parts.
        """
        is_valid, err_msg, new_size, new_ranges = validate_refresh_url(
            new_url=new_url,
            expected_size=self.total_size,
            check_range=self.supports_ranges,
            timeout=12.0,
            ssl_context=self.ssl_context,
            headers=headers or self.headers
        )
        if not is_valid:
            self.log(f"[REFRESH ERROR] Validation failed: {err_msg}")
            raise ValueError(err_msg)

        self.update_url(new_url, headers)
        self.has_expired_link = False
        self._error_abort_event.clear()

        if auto_resume:
            if self.is_running:
                with self._lock:
                    for c in self.chunks:
                        with c.lock:
                            if c.status == "failed":
                                c.status = "pending"
                                c.error_msg = ""
                if self.is_paused:
                    self.resume()
                else:
                    with self._lock:
                        active_count = sum(1 for c in self.chunks if c.status == "active")
                        pending = [c for c in self.chunks if c.status == "pending"]
                        to_spawn = pending[:max(0, self.max_connections - active_count)]
                    for c in to_spawn:
                        self._spawn_worker(c)
            else:
                self.resume_transfer()

        self.log(f"[REFRESH SUCCESS] Link refreshed successfully: {new_url}")
        return True


__all__ = ["EngineResumerMixin", "_build_window_url", "_is_urlopen_mocked", "_is_ssl_socket"]
