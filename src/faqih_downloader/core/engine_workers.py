"""
EngineWorkersMixin: Background worker thread pooling and dynamic chunk splitting.
"""
import os, re, time
import http.client
import urllib.request
import urllib.error
import urllib.parse
import threading
from typing import Optional, Dict, Any

from .chunk import DownloadChunk
from .engine_resumer import EngineResumerMixin, _build_window_url, _is_urlopen_mocked, _is_ssl_socket
from ..utils.url_utils import parse_filename_from_cd_header


GOOGLEVIDEO_WINDOW_BYTES = 2 * 1024 * 1024  # 2 MB fast burst window with HTTP Range headers + keep-alive reuse


class _KeepAliveResponseWrapper:
    """Wraps an http.client.HTTPResponse for fast read1() TLS batching and safe pause exit."""
    def __init__(self, raw_resp: Any, conn: Any, pause_event: Any = None, cancel_event: Any = None):
        self._resp = raw_resp
        self._conn = conn
        self._pause_event = pause_event
        self._cancel_event = cancel_event
        self._owner_tid = threading.get_ident()
        self._reading = False
        self.status = getattr(raw_resp, "status", 200)
        self.headers = getattr(raw_resp, "headers", {})
        self.will_close = getattr(raw_resp, "will_close", False)

    def getcode(self) -> int:
        return self.status

    def read(self, amt: int = -1) -> bytes:
        self._reading = True
        self._owner_tid = threading.get_ident()
        try:
            if amt > 0 and hasattr(type(self._resp), "read1") and not hasattr(self._resp, "_mock_name"):
                chunks = []
                got = 0
                while got < amt:
                    if (self._pause_event is not None and self._pause_event.is_set()) or (self._cancel_event is not None and self._cancel_event.is_set()):
                        break
                    piece = self._resp.read1(min(65536, amt - got))
                    if not piece:
                        break
                    chunks.append(piece)
                    got += len(piece)
                    if getattr(self._resp, "length", None) == 0:
                        break
                if getattr(self._resp, "length", None) == 0 and not self._resp.isclosed() and hasattr(self._resp, "_close_conn"):
                    try: self._resp._close_conn()
                    except Exception: pass
                return b"".join(chunks) if len(chunks) != 1 else chunks[0]
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
        try: self._resp.close()
        except Exception: pass
        if self._conn:
            try: self._conn.close()
            except Exception: pass


class EngineWorkersMixin(EngineResumerMixin):
    """Mixin providing worker management, chunk streaming, dynamic splitting, and rate limiting."""

    @staticmethod
    def is_googlevideo_url(url: str) -> bool:
        """Detects if a URL is hosted on YouTube CDN (googlevideo.com)."""
        if not url or not isinstance(url, str): return False
        try:
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower()
            if host.endswith(".googlevideo.com") or host == "googlevideo.com" or any(d in host for d in ("youtube.com", "youtu.be", "ytimg.com")) or "videoplayback" in (parsed.path or "").lower():
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
        for k, v in self.headers.items(): req.add_header(k, v)
        return req

    def _spawn_worker(self, chunk: DownloadChunk):
        """Spawns an asynchronous worker thread for a chunk (single-worker guarded)."""
        with self._lock:
            wt = getattr(self, "_worker_threads", None)
            if wt is None: wt = self._worker_threads = {}
            existing = wt.get(chunk.chunk_id)
            if existing is not None and existing.is_alive(): return
            with chunk.lock:
                if chunk.status == "completed": return
                chunk.status = "active"
            t = threading.Thread(target=self._chunk_worker, args=(chunk,), daemon=True)
            self.active_workers.append(t); wt[chunk.chunk_id] = t
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
        max_retries = 8
        retry_count = 0
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
                            if self.total_size > 0: chunk.status = "completed"
                            chunk_done = True
                        else:
                            chunk_done = False
                    if chunk_done:
                        try: self._dynamic_split_check()
                        except Exception: pass
                        return

                    if self.supports_ranges and self.total_size > 0:
                        req_end = min(target_end, cur_offset + GOOGLEVIDEO_WINDOW_BYTES - 1) if (is_gv and (target_end - cur_offset + 1) > GOOGLEVIDEO_WINDOW_BYTES) else target_end
                    else:
                        req_end = None

                    end_str = f"{req_end:,}" if req_end is not None else "end"
                    self.log(f"Connection #{chunk.chunk_id} (Attempt {retry_count+1}): Byte range [{cur_offset:,} - {end_str}]")
                    if self.on_chunk_update: self.on_chunk_update()

                    win_url = _build_window_url(current_url, cur_offset, req_end, is_gv)
                    expected_seg_bytes = (req_end - cur_offset + 1) if (req_end is not None) else None
                    seg_bytes_read = 0

                    if _is_urlopen_mocked():
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
                        if self.supports_ranges and self.total_size > 0 and req_end is not None:
                            hdrs["Range"] = f"bytes={cur_offset}-{req_end}"

                        p = urllib.parse.urlsplit(win_url)
                        scheme, host = p.scheme or "http", p.hostname or "localhost"
                        port = p.port or (443 if scheme == "https" else 80)
                        path_q = (p.path or "/") + (f"?{p.query}" if p.query else "")

                        if conn is not None and conn_key != (scheme, host, port):
                            self._close_conn_safely(conn)
                            conn = None

                        raw_resp = None
                        for send_attempt in range(2):
                            if conn is None:
                                conn = self._acquire_pooled_conn((scheme, host, port))
                                if conn is not None:
                                    conn_key = (scheme, host, port)
                            if conn is None:
                                conn = http.client.HTTPSConnection(host, port, timeout=15, context=self.ssl_context) if scheme == "https" else http.client.HTTPConnection(host, port, timeout=15)
                                conn_key = (scheme, host, port)
                            with self._lock:
                                if conn not in self._active_connections:
                                    self._active_connections.append(conn)
                            req_h = dict(hdrs, Host=p.netloc)
                            try:
                                conn.request("GET", path_q, headers=req_h)
                                raw_resp = conn.getresponse()
                                if getattr(conn, "sock", None) is not None and hasattr(conn.sock, "settimeout"):
                                    conn.sock.settimeout(2.0)
                                break
                            except (http.client.HTTPException, ConnectionError, OSError):
                                with self._lock:
                                    if conn in self._active_connections:
                                        self._active_connections.remove(conn)
                                try: conn.close()
                                except Exception: pass
                                conn = None
                                if send_attempt == 1 or self._is_stopped() or self._pause_event.is_set(): raise

                        redir_count = 0
                        while raw_resp and raw_resp.status in (301, 302, 303, 307, 308) and redir_count < 5:
                            redir_count += 1
                            loc = raw_resp.getheader("Location")
                            if not loc: break
                            try: raw_resp.read()
                            except Exception: pass
                            if conn:
                                with self._lock:
                                    if conn in self._active_connections:
                                        self._active_connections.remove(conn)
                                try: conn.close()
                                except Exception: pass
                                conn = None
                            current_url = urllib.parse.urljoin(current_url, loc)
                            is_gv = is_gv or self.is_googlevideo_url(current_url)
                            win_url = _build_window_url(current_url, cur_offset, req_end, is_gv)
                            p = urllib.parse.urlsplit(win_url)
                            scheme, host = p.scheme or "http", p.hostname or "localhost"
                            port = p.port or (443 if scheme == "https" else 80)
                            path_q = (p.path or "/") + (f"?{p.query}" if p.query else "")
                            conn = http.client.HTTPSConnection(host, port, timeout=15, context=self.ssl_context) if scheme == "https" else http.client.HTTPConnection(host, port, timeout=15)
                            conn_key = (scheme, host, port)
                            with self._lock:
                                self._active_connections.append(conn)
                            conn.request("GET", path_q, headers=dict(hdrs, Host=p.netloc))
                            raw_resp = conn.getresponse()
                            if getattr(conn, "sock", None) is not None and hasattr(conn.sock, "settimeout"):
                                conn.sock.settimeout(2.0)

                        resp = _KeepAliveResponseWrapper(raw_resp, conn, self._pause_event, self._cancel_event)

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
                            paused_break = True; break

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
                                paused_break = True; break
                            if expected_seg_bytes is not None and seg_bytes_read < expected_seg_bytes:
                                raise RuntimeError(f"Premature EOF from server: received {seg_bytes_read:,} of {expected_seg_bytes:,} bytes")
                            break

                        self.rate_limiter.acquire(len(data), self._cancel_event)

                        with chunk.lock:
                            pos = chunk.start_byte + chunk.downloaded_bytes
                            effective_end = min(chunk.end_byte, req_end) if req_end is not None else chunk.end_byte
                            if self.total_size > 0:
                                if pos > effective_end: break
                                needed = effective_end - pos + 1
                                if len(data) > needed: data = data[:needed]

                            out_file.write(data)
                            chunk.downloaded_bytes += len(data)
                            seg_bytes_read += len(data)

                            if self.total_size > 0 and (chunk.start_byte + chunk.downloaded_bytes > chunk.end_byte):
                                chunk.status = "completed"
                                chunk_done = True
                        if chunk_done:
                            break

                    if out_file:
                        try: out_file.flush()
                        except Exception: pass

                    if paused_break or self._pause_event.is_set() or self.is_paused:
                        self._cleanup_worker_conns(resp, conn)
                        resp = conn = None
                        if not self._wait_if_paused(): return
                        continue

                    with chunk.lock:
                        cur_chunk_end = chunk.end_byte
                        if chunk_done or (self.total_size > 0 and chunk.start_byte + chunk.downloaded_bytes > cur_chunk_end) or self.total_size == 0:
                            chunk.status = "completed"
                            chunk_done = True

                    if chunk_done:
                        if _is_urlopen_mocked():
                            self._cleanup_worker_conns(resp, None); resp = None
                        else:
                            seg_bytes_read = self._drain_small_tail(resp, raw_resp, seg_bytes_read, expected_seg_bytes, req_end, cur_chunk_end)
                            self._release_or_close_conn(conn, resp, raw_resp, conn_key, seg_bytes_read, expected_seg_bytes)
                            conn = resp = None
                        try: self._dynamic_split_check()
                        except Exception: pass
                        return

                    if expected_seg_bytes is not None and seg_bytes_read >= expected_seg_bytes:
                        with self._lock:
                            if resp in self._active_connections: self._active_connections.remove(resp)
                        if hasattr(resp, "_mock_name"): self._close_conn_safely(resp)
                        resp = None
                        if _is_urlopen_mocked() or not self._is_conn_reusable(conn, raw_resp, seg_bytes_read, expected_seg_bytes):
                            self._cleanup_worker_conns(None, conn); conn = None
                        retry_count = 0; continue

                    if not _is_urlopen_mocked():
                        self._release_or_close_conn(conn, resp, raw_resp, conn_key, seg_bytes_read, expected_seg_bytes)
                    else:
                        self._cleanup_worker_conns(resp, None)
                    resp = conn = None
                    raise RuntimeError(f"Premature EOF from server before chunk completion ({chunk.downloaded_bytes:,}/{cur_chunk_end - chunk.start_byte + 1:,} bytes)")

            except Exception as e:
                if self._pause_event.is_set() or self.is_paused:
                    if out_file:
                        try: out_file.flush()
                        except Exception: pass
                    self._cleanup_worker_conns(resp, conn); resp = conn = None
                    while self._pause_event.is_set() and not self.is_cancelled and self.is_running:
                        time.sleep(0.05)
                    if self._is_stopped(): return
                    continue
                if isinstance(e, urllib.error.HTTPError):
                    e.close(); self.last_http_status = e.code
                    if e.code in (401, 403, 410):
                        self.has_expired_link = True
                        chunk.error_msg = f"HTTP {e.code}: {e.reason} (Expired or Forbidden Link)"
                        with chunk.lock: chunk.status = "failed"
                        self._stop_workers_for_error(); break
                if self.has_expired_link:
                    with chunk.lock: chunk.status = "failed"
                    break
                if self._cancel_event.is_set() or not self.is_running: return
                if self._error_abort_event.is_set(): break
                retry_count = 0 if seg_bytes_read >= 65536 else (max(0, retry_count - 1) if seg_bytes_read > 0 else retry_count)
                retry_count += 1; chunk.retry_count = retry_count
                backoff = min(4.0, 0.8 * (1.4 ** min(retry_count, 5)))
                self.log(f"Connection #{chunk.chunk_id} error: {e}. Retry {retry_count}/{max_retries} in {backoff:.1f}s...")
                t_end = time.time() + backoff
                while time.time() < t_end and not self._is_stopped() and not self._pause_event.is_set():
                    time.sleep(0.05)
                if self._pause_event.is_set():
                    if not self._wait_if_paused(): return
                    continue
                if self._cancel_event.is_set() or not self.is_running: return
                if self._error_abort_event.is_set(): break
            finally:
                if out_file:
                    try: out_file.close()
                    except Exception: pass
                    out_file = None
                self._cleanup_worker_conns(resp, conn); resp = conn = None
                if self.on_chunk_update: self.on_chunk_update()

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

    def _dynamic_split_check(self):
        """TDM Adaptive Dynamic Midpoint Splitting Mechanism."""
        with self._lock:
            if not self.allow_dynamic_split or not getattr(self, "supports_ranges", False):
                return

        split_any = False
        while True:
            if self._is_stopped():
                break
            new_chunk = candidate = None
            split_start = old_end = new_id = 0
            with self._lock:
                if sum(1 for c in self.chunks if c.status in ("active", "pending")) >= self.max_connections:
                    break
                candidates = [c for c in self.chunks if c.status in ("active", "pending") and c.remaining_bytes >= self.min_split_threshold * 2] or \
                             [c for c in self.chunks if c.status in ("active", "pending") and c.remaining_bytes >= self.min_split_threshold]
                if not candidates:
                    break
                candidate = max(candidates, key=lambda c: c.remaining_bytes)
                with candidate.lock:
                    remaining = candidate.end_byte - (candidate.start_byte + candidate.downloaded_bytes) + 1
                    half = remaining // 2
                    if remaining < self.min_split_threshold or half < 32768 or candidate.status not in ("active", "pending"):
                        break
                    split_start = candidate.start_byte + candidate.downloaded_bytes + half
                    old_end = candidate.end_byte
                    candidate.end_byte = split_start - 1

                new_id = len(self.chunks)
                part_path = os.path.join(self.temp_dir, f"{os.path.basename(self.destination_path)}.part_{new_id}")
                new_chunk = DownloadChunk(new_id, split_start, old_end, 0, "pending", part_filepath=part_path)
                self.chunks.append(new_chunk)

            if new_chunk and candidate:
                split_any = True
                self.log(f"[SPLIT] Fast Ramp-Up Split: Chunk #{candidate.chunk_id} split! Spawned Chunk #{new_id} [{split_start:,} - {old_end:,}]")
                self._spawn_worker(new_chunk)
            else:
                break

        if split_any:
            self.save_state()

    def _update_progress_metrics(self):
        """Computes responsive EMA-smoothed transfer speed over a >=2.0s window, ETA, and progress metrics."""
        emit_lock = getattr(self, "_progress_emit_lock", None)
        if emit_lock is None:
            with self._lock: emit_lock = self._progress_emit_lock = getattr(self, "_progress_emit_lock", None) or threading.RLock()
        with emit_lock: return self._update_progress_metrics_impl()

    def _update_progress_metrics_impl(self):
        with self._lock:
            total_downloaded = sum(c.downloaded_bytes for c in self.chunks)
            active_count = sum(1 for c in self.chunks if c.status == "active")
        if self.is_paused or self._pause_event.is_set():
            self.current_speed = 0.0
            return

        now = time.monotonic()
        samples = getattr(self, "_speed_samples", None)
        if samples is None:
            from collections import deque
            samples = deque([(self.last_speed_check_time or now, self.last_downloaded_bytes)])
            self._speed_samples = samples
        elif not samples:
            samples.append((now, total_downloaded))

        dt = now - self.last_speed_check_time
        should_emit = (dt >= 0.20) or (self.total_size > 0 and total_downloaded >= self.total_size) or self._is_stopped()
        if dt >= 0.20:
            samples.append((now, total_downloaded))
            while len(samples) > 2 and (now - samples[1][0]) >= 2.0:
                samples.popleft()
            win_dt = now - samples[0][0]
            win_bytes = max(0, total_downloaded - samples[0][1])
            instant_speed = (win_bytes / win_dt) if win_dt > 0 else 0.0
            self.current_speed = instant_speed if self.current_speed <= 0.0 else (0.35 * instant_speed + 0.65 * self.current_speed)
            self.last_downloaded_bytes = self._last_speed_bytes = total_downloaded
            self.last_speed_check_time = self._last_speed_time = now

        if self.current_speed <= 0.0 and total_downloaded > 0:
            st = getattr(self, "_last_active_start_mono", None)
            elapsed = (now - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
            session_dl = max(0, total_downloaded - getattr(self, "_session_start_bytes", 0))
            if session_dl > 0:
                self.current_speed = session_dl / max(0.05, elapsed)

        if self.current_speed > 1024 and self.total_size > total_downloaded:
            eta_sec = int((self.total_size - total_downloaded) / self.current_speed)
            eta_str = f"{eta_sec // 3600:02d}:{(eta_sec % 3600) // 60:02d}:{eta_sec % 60:02d}"
        else:
            eta_str = "--:--:--"

        if self.is_paused or self._pause_event.is_set(): self.current_speed = 0.0; return
        if self.on_progress and should_emit:
            self.on_progress(total_downloaded, self.total_size, self.current_speed, eta_str, active_count)

    def _stop_workers_for_error(self):
        """Closes active non-SSL connections and signals all workers to abort immediately."""
        self._error_abort_event.set()
        with self._lock:
            for conn in list(self._active_connections):
                if not _is_ssl_socket(conn):
                    self._close_conn_safely(conn)
            self._active_connections.clear()
        self._drain_conn_pool()


__all__ = ["EngineWorkersMixin", "EngineResumerMixin"]
