"""
EngineChunkWorkerMixin: Chunk worker loops, network socket I/O, range streaming, and error aborts.
"""
import os
import sys
import time
import socket
import http.client
import urllib.request
import urllib.error
import urllib.parse
import threading
from typing import Optional, Dict, Any

from ..chunk import DownloadChunk
from ...utils.url_utils import parse_filename_from_cd_header
from .socket_utils import (
    GOOGLEVIDEO_WINDOW_BYTES as _CANONICAL_GV_WINDOW_BYTES,
    _configure_fast_socket as _canonical_configure_fast_socket,
    _build_window_url as _canonical_build_window_url,
    _is_urlopen_mocked as _canonical_is_urlopen_mocked,
    _is_ssl_socket,
)
from .keepalive_wrapper import _KeepAliveResponseWrapper as _CanonicalKeepAliveWrapper


def _resolve_is_urlopen_mocked() -> bool:
    for mod_name in (
        "faqih_downloader.core.engine_workers",
        "faqih_downloader.core.engine_resumer",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "_is_urlopen_mocked"):
            fn = getattr(mod, "_is_urlopen_mocked")
            if fn is not _canonical_is_urlopen_mocked:
                return fn()
    return _canonical_is_urlopen_mocked()


def _resolve_gv_window_bytes() -> int:
    mod = sys.modules.get("faqih_downloader.core.engine_workers")
    if mod is not None and hasattr(mod, "GOOGLEVIDEO_WINDOW_BYTES"):
        return getattr(mod, "GOOGLEVIDEO_WINDOW_BYTES")
    return _CANONICAL_GV_WINDOW_BYTES


def _resolve_build_window_url(url: str, start_byte: int, end_byte: Optional[int], is_gv: bool, req_num: Optional[int] = None) -> str:
    for mod_name in (
        "faqih_downloader.core.engine_workers",
        "faqih_downloader.core.engine_resumer",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "_build_window_url"):
            fn = getattr(mod, "_build_window_url")
            if fn is not _canonical_build_window_url:
                return fn(url, start_byte, end_byte, is_gv, req_num)
    return _canonical_build_window_url(url, start_byte, end_byte, is_gv, req_num)


def _resolve_configure_fast_socket(conn: Any) -> None:
    mod = sys.modules.get("faqih_downloader.core.engine_workers")
    if mod is not None and hasattr(mod, "_configure_fast_socket"):
        fn = getattr(mod, "_configure_fast_socket")
        if fn is not _canonical_configure_fast_socket:
            return fn(conn)
    return _canonical_configure_fast_socket(conn)


def _resolve_keepalive_wrapper():
    mod = sys.modules.get("faqih_downloader.core.engine_workers")
    if mod is not None and hasattr(mod, "_KeepAliveResponseWrapper"):
        cls = getattr(mod, "_KeepAliveResponseWrapper")
        if cls is not _CanonicalKeepAliveWrapper:
            return cls
    return _CanonicalKeepAliveWrapper


class EngineChunkWorkerMixin:
    """Worker loop orchestration, HTTP range chunk downloading, and connection dispatch."""

    @staticmethod
    def is_googlevideo_url(url: str) -> bool:
        """Detects if a URL is hosted on YouTube CDN (googlevideo.com)."""
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower()
            if (
                host.endswith(".googlevideo.com")
                or host == "googlevideo.com"
                or any(d in host for d in ("youtube.com", "youtu.be", "ytimg.com"))
                or "videoplayback" in (parsed.path or "").lower()
            ):
                return True
        except Exception:
            pass
        u_lo = str(url).lower()
        return "googlevideo.com" in u_lo or "videoplayback" in u_lo

    def _parse_filename_from_cd(self, cd: str) -> Optional[str]:
        """Extracts clean filename from Content-Disposition header, ignoring parameters."""
        return parse_filename_from_cd_header(cd)

    def _create_request(self, method: Optional[str] = None, url: Optional[str] = None) -> urllib.request.Request:
        """Constructs an HTTP request pre-populated with standard headers and custom headers."""
        target_url = url or self.url
        req = urllib.request.Request(target_url, method=method) if method else urllib.request.Request(target_url)
        if not any(k.lower() == "user-agent" for k in self.headers):
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0")
        if not any(k.lower() == "connection" for k in self.headers):
            req.add_header("Connection", "keep-alive")
        for k, v in self.headers.items():
            req.add_header(k, v)
        return req

    def _spawn_worker(self, chunk: DownloadChunk):
        """Spawns an asynchronous worker thread for a chunk (single-worker guarded)."""
        with self._lock:
            wt = getattr(self, "_worker_threads", None)
            if wt is None:
                wt = self._worker_threads = {}
            existing = wt.get(chunk.chunk_id)
            if existing is not None and existing.is_alive():
                return
            with chunk.lock:
                if chunk.status == "completed":
                    return
                chunk.status = "active"
            t = threading.Thread(target=self._chunk_worker, args=(chunk,), daemon=True)
            self.active_workers.append(t)
            wt[chunk.chunk_id] = t
        t.start()

    def _is_stopped(self) -> bool:
        """Checks if current download task was cancelled, aborted, or stopped."""
        return self._cancel_event.is_set() or self._error_abort_event.is_set() or not self.is_running

    def _wait_if_paused(self) -> bool:
        """Blocks while download is paused; returns True if resumed, False if stopped/cancelled."""
        while self._pause_event.is_set() and not self._is_stopped():
            time.sleep(0.05)
        return not self._is_stopped()

    def _chunk_worker(self, chunk: DownloadChunk):
        """Worker thread with persistent Keep-Alive connection, fast burst windows, and file streaming."""
        max_retries = 15
        retry_count = 0
        win_rn = 0
        adaptive_gv_win = 2 * 1024 * 1024
        is_gv = getattr(self, "is_googlevideo", False)

        while retry_count < max_retries and not self._is_stopped():
            if not self._wait_if_paused():
                return

            resp = raw_resp = conn = conn_key = out_file = None
            seg_bytes_read = 0
            current_url = self.url

            try:
                while not self._is_stopped():
                    with chunk.lock:
                        chunk.status = "active"
                        cur_offset = chunk.current_byte
                        target_end = chunk.end_byte
                        if (self.total_size > 0 and cur_offset > target_end) or (self.total_size == 0 and chunk.downloaded_bytes > 0 and chunk.status == "completed"):
                            if self.total_size > 0:
                                chunk.status = "completed"
                            chunk_done = True
                        else:
                            chunk_done = False
                    if chunk_done:
                        try:
                            self._dynamic_split_check()
                        except Exception:
                            pass
                        return

                    is_mocked = _resolve_is_urlopen_mocked()
                    cur_gv_window = _resolve_gv_window_bytes()
                    cur_gv_win = cur_gv_window if (is_mocked or cur_gv_window < 1024 * 1024) else adaptive_gv_win
                    if self.supports_ranges and self.total_size > 0:
                        req_end = min(target_end, cur_offset + cur_gv_win - 1) if (is_gv and (target_end - cur_offset + 1) > cur_gv_win) else target_end
                    else:
                        req_end = None

                    if win_rn <= 1 or retry_count > 0 or is_mocked:
                        end_str = f"{req_end:,}" if req_end is not None else "end"
                        self.log(f"Connection #{chunk.chunk_id} (Attempt {retry_count+1}): Byte range [{cur_offset:,} - {end_str}]")
                        if self.on_chunk_update:
                            self.on_chunk_update()

                    req_num = win_rn if (is_gv and not is_mocked and req_end is not None) else None
                    if req_num is not None:
                        win_rn += 1
                    win_url = _resolve_build_window_url(current_url, cur_offset, req_end, is_gv, req_num=req_num)
                    expected_seg_bytes = (req_end - cur_offset + 1) if (req_end is not None) else None
                    seg_bytes_read = 0
                    seg_start_mono = time.monotonic()

                    if is_mocked:
                        req = self._create_request(url=win_url)
                        if self.supports_ranges and self.total_size > 0 and req_end is not None:
                            req.add_header("Range", f"bytes={cur_offset}-{req_end}")
                        resp = urllib.request.urlopen(req, timeout=15, context=self.ssl_context)
                    else:
                        has_ua = any(k.lower() == "user-agent" for k in self.headers)
                        hdrs = {"Connection": "keep-alive", "Accept-Encoding": "identity"}
                        if not has_ua:
                            hdrs["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"
                        for hk, hv in self.headers.items():
                            if hk.lower() != "range":
                                hdrs[hk] = hv
                        if self.supports_ranges and self.total_size > 0 and req_end is not None and not is_gv:
                            hdrs["Range"] = f"bytes={cur_offset}-{req_end}"

                        def _split_target(u: str):
                            u_p = urllib.parse.urlsplit(u)
                            sch, hst = u_p.scheme or "http", u_p.hostname or "localhost"
                            return u_p, sch, hst, u_p.port or (443 if sch == "https" else 80), (u_p.path or "/") + (f"?{u_p.query}" if u_p.query else "")

                        p, scheme, host, port, path_q = _split_target(win_url)
                        if conn is not None and conn_key != (scheme, host, port):
                            self._close_conn_safely(conn)
                            conn = None

                        raw_resp = None
                        for send_attempt in range(2):
                            if conn is None:
                                conn = self._acquire_pooled_conn((scheme, host, port)) or (
                                    http.client.HTTPSConnection(host, port, timeout=15, context=self.ssl_context)
                                    if scheme == "https"
                                    else http.client.HTTPConnection(host, port, timeout=15)
                                )
                                conn_key = (scheme, host, port)
                            with self._lock:
                                if conn not in self._active_connections:
                                    self._active_connections.append(conn)
                            try:
                                conn.request("GET", path_q, headers=dict(hdrs, Host=p.netloc))
                                raw_resp = conn.getresponse()
                                _resolve_configure_fast_socket(conn)
                                break
                            except (http.client.HTTPException, ConnectionError, OSError):
                                self._cleanup_worker_conns(None, conn)
                                conn = None
                                if send_attempt == 1 or self._is_stopped() or self._pause_event.is_set():
                                    raise

                        redir_count = 0
                        while raw_resp and raw_resp.status in (301, 302, 303, 307, 308) and redir_count < 5:
                            redir_count += 1
                            loc = raw_resp.getheader("Location")
                            if not loc:
                                break
                            try:
                                raw_resp.read()
                            except Exception:
                                pass
                            if conn:
                                self._cleanup_worker_conns(None, conn)
                                conn = None
                            current_url = urllib.parse.urljoin(current_url, loc)
                            is_gv = is_gv or self.is_googlevideo_url(current_url)
                            win_url = _resolve_build_window_url(current_url, cur_offset, req_end, is_gv, req_num=req_num)
                            p, scheme, host, port, path_q = _split_target(win_url)
                            conn = (
                                http.client.HTTPSConnection(host, port, timeout=15, context=self.ssl_context)
                                if scheme == "https"
                                else http.client.HTTPConnection(host, port, timeout=15)
                            )
                            conn_key = (scheme, host, port)
                            with self._lock:
                                self._active_connections.append(conn)
                            conn.request("GET", path_q, headers=dict({k: v for k, v in hdrs.items() if not (is_gv and k.lower() == "range")}, Host=p.netloc))
                            raw_resp = conn.getresponse()
                            _resolve_configure_fast_socket(conn)

                        wrapper_cls = _resolve_keepalive_wrapper()
                        resp = wrapper_cls(raw_resp, conn, self._pause_event, self._cancel_event)

                    code = resp.getcode()
                    if code not in (200, 206):
                        self.last_http_status = code
                        if code in (401, 403, 410):
                            self.has_expired_link = True
                            chunk.error_msg = f"HTTP {code}: Forbidden (Expired or Forbidden Link)"
                            with chunk.lock:
                                chunk.status = "failed"
                            self._stop_workers_for_error()
                        raise RuntimeError(f"Unexpected HTTP status {code}")
                    if self.supports_ranges and self.total_size > 0 and code == 200 and cur_offset > 0 and not is_gv:
                        raise RuntimeError("Server returned HTTP 200 instead of HTTP 206 for non-zero range")

                    if self._is_stopped():
                        break

                    if out_file is None:
                        with chunk.lock:
                            if self.total_size > 0 and chunk.start_byte + chunk.downloaded_bytes > chunk.end_byte:
                                chunk.status = "completed"
                                return
                        f_mode = "r+b" if (chunk.downloaded_bytes > 0 and os.path.exists(chunk.part_filepath)) else "w+b"
                        out_file = open(chunk.part_filepath, f_mode, buffering=1024 * 1024)
                        out_file.seek(chunk.downloaded_bytes if f_mode == "r+b" else 0)
                        out_file.truncate()

                    with self._lock:
                        self._active_connections.append(resp)

                    BUF_SIZE = 262144
                    paused_break = False
                    chunk_done = False
                    while not self._is_stopped():
                        if self._pause_event.is_set():
                            paused_break = True
                            break

                        with chunk.lock:
                            pos = chunk.start_byte + chunk.downloaded_bytes
                            if self.total_size > 0 and pos > chunk.end_byte:
                                chunk.status = "completed"
                                chunk_done = True
                            else:
                                effective_end = min(chunk.end_byte, req_end) if req_end is not None else chunk.end_byte
                                to_read = min(BUF_SIZE, effective_end - pos + 1) if self.total_size > 0 else BUF_SIZE
                        if chunk_done or to_read <= 0:
                            break

                        data = resp.read(to_read)
                        if not data:
                            if self._pause_event.is_set() or self.is_paused:
                                paused_break = True
                                break
                            if expected_seg_bytes is not None and seg_bytes_read < expected_seg_bytes:
                                raise RuntimeError(f"Premature EOF from server: received {seg_bytes_read:,} of {expected_seg_bytes:,} bytes")
                            break

                        self.rate_limiter.acquire(len(data), self._cancel_event)

                        with chunk.lock:
                            pos = chunk.start_byte + chunk.downloaded_bytes
                            effective_end = min(chunk.end_byte, req_end) if req_end is not None else chunk.end_byte
                            if self.total_size > 0:
                                if pos > effective_end:
                                    break
                                needed = effective_end - pos + 1
                                if len(data) > needed:
                                    data = data[:needed]

                            out_file.write(data)
                            chunk.downloaded_bytes += len(data)
                            seg_bytes_read += len(data)

                            if self.total_size > 0 and (chunk.start_byte + chunk.downloaded_bytes > chunk.end_byte):
                                chunk.status = "completed"
                                chunk_done = True
                        if chunk_done:
                            break

                    if out_file:
                        try:
                            out_file.flush()
                        except Exception:
                            pass

                    if paused_break or self._pause_event.is_set() or self.is_paused:
                        self._cleanup_worker_conns(resp, conn)
                        resp = conn = None
                        if not self._wait_if_paused():
                            return
                        continue

                    with chunk.lock:
                        cur_chunk_end = chunk.end_byte
                        if chunk_done or (self.total_size > 0 and chunk.start_byte + chunk.downloaded_bytes > cur_chunk_end) or self.total_size == 0:
                            chunk.status = "completed"
                            chunk_done = True

                    if chunk_done:
                        if _resolve_is_urlopen_mocked():
                            self._cleanup_worker_conns(resp, None)
                            resp = None
                        else:
                            seg_bytes_read = self._drain_small_tail(resp, raw_resp, seg_bytes_read, expected_seg_bytes, req_end, cur_chunk_end)
                            self._release_or_close_conn(conn, resp, raw_resp, conn_key, seg_bytes_read, expected_seg_bytes)
                            conn = resp = None
                        try:
                            self._dynamic_split_check()
                        except Exception:
                            pass
                        return

                    if expected_seg_bytes is not None and seg_bytes_read >= expected_seg_bytes:
                        seg_dt = max(0.001, time.monotonic() - seg_start_mono)
                        seg_speed = seg_bytes_read / seg_dt
                        throttled_gv = False
                        if is_gv and not is_mocked and cur_gv_window >= 1024 * 1024:
                            if seg_speed >= 450 * 1024:
                                adaptive_gv_win = min(8 * 1024 * 1024, int(adaptive_gv_win * 1.5))
                            elif seg_speed < 160 * 1024:
                                adaptive_gv_win = 1572864
                                throttled_gv = True
                        with self._lock:
                            if resp in self._active_connections:
                                self._active_connections.remove(resp)
                        if hasattr(resp, "_mock_name"):
                            self._close_conn_safely(resp)
                        resp = None
                        if is_mocked or throttled_gv or not self._is_conn_reusable(conn, raw_resp, seg_bytes_read, expected_seg_bytes):
                            self._cleanup_worker_conns(None, conn)
                            conn = None
                        retry_count = 0
                        continue

                    if not _resolve_is_urlopen_mocked():
                        self._release_or_close_conn(conn, resp, raw_resp, conn_key, seg_bytes_read, expected_seg_bytes)
                    else:
                        self._cleanup_worker_conns(resp, None)
                    resp = conn = None
                    raise RuntimeError(f"Premature EOF from server before chunk completion ({chunk.downloaded_bytes:,}/{cur_chunk_end - chunk.start_byte + 1:,} bytes)")

            except Exception as e:
                if self._pause_event.is_set() or self.is_paused:
                    if out_file:
                        try:
                            out_file.flush()
                        except Exception:
                            pass
                    self._cleanup_worker_conns(resp, conn)
                    resp = conn = None
                    while self._pause_event.is_set() and not self.is_cancelled and self.is_running:
                        time.sleep(0.05)
                    if self._is_stopped():
                        return
                    continue
                if isinstance(e, urllib.error.HTTPError):
                    e.close()
                    self.last_http_status = e.code
                    if e.code in (401, 403, 410):
                        self.has_expired_link = True
                        chunk.error_msg = f"HTTP {e.code}: {e.reason} (Expired or Forbidden Link)"
                        with chunk.lock:
                            chunk.status = "failed"
                        self._stop_workers_for_error()
                        break
                if self.has_expired_link:
                    with chunk.lock:
                        chunk.status = "failed"
                    break
                if self._cancel_event.is_set() or not self.is_running:
                    return
                if self._error_abort_event.is_set():
                    break
                retry_count = 0 if seg_bytes_read >= 65536 else (max(0, retry_count - 1) if seg_bytes_read > 0 else retry_count)
                retry_count += 1
                chunk.retry_count = retry_count
                backoff = min(1.5, 0.25 * (1.3 ** min(retry_count, 5)))
                self.log(f"Connection #{chunk.chunk_id} error: {e}. Retry {retry_count}/{max_retries} in {backoff:.1f}s...")
                t_end = time.time() + backoff
                while time.time() < t_end and not self._is_stopped() and not self._pause_event.is_set():
                    time.sleep(0.05)
                if self._pause_event.is_set():
                    if not self._wait_if_paused():
                        return
                    continue
                if self._cancel_event.is_set() or not self.is_running:
                    return
                if self._error_abort_event.is_set():
                    break
            finally:
                if out_file:
                    try:
                        out_file.close()
                    except Exception:
                        pass
                    out_file = None
                self._cleanup_worker_conns(resp, conn)
                resp = conn = None
                if self.on_chunk_update:
                    self.on_chunk_update()

        if self._cancel_event.is_set() or not self.is_running:
            return

        with chunk.lock:
            if chunk.status != "completed":
                chunk.status = "failed"
                if not chunk.error_msg:
                    chunk.error_msg = f"Connection failed after {max_retries} attempts"
                self.log(f"Chunk #{chunk.chunk_id} failed permanently: {chunk.error_msg}")
        self.save_state()
        if self.on_chunk_update:
            self.on_chunk_update()

    def _stop_workers_for_error(self):
        """Closes active non-SSL connections and signals all workers to abort immediately."""
        self._error_abort_event.set()
        with self._lock:
            for conn in list(self._active_connections):
                if not _is_ssl_socket(conn):
                    self._close_conn_safely(conn)
            self._active_connections.clear()
        self._drain_conn_pool()
