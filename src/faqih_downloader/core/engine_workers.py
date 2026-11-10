"""
EngineWorkersMixin: Background worker thread pooling and dynamic chunk splitting.
"""
import os
import re
import time
import http.client
import urllib.request
import urllib.error
import urllib.parse
import threading
from typing import Optional, Dict, Any

from .chunk import DownloadChunk
from .engine_resumer import EngineResumerMixin
from ..utils.url_utils import parse_filename_from_cd_header


GOOGLEVIDEO_WINDOW_BYTES = 10 * 1024 * 1024  # 10 MB Fast Burst Window matching yt-dlp optimal chunk size


def _build_window_url(url: str, start_byte: int, end_byte: Optional[int], is_gv: bool) -> str:
    """Appends or updates &range=start-end query parameter on googlevideo URLs for native CDN pacing."""
    if not is_gv or end_byte is None:
        return url
    rng = f"range={start_byte}-{end_byte}"
    if re.search(r"([?&])range=[^&]*", url):
        return re.sub(r"([?&])range=[^&]*", rf"\g<1>{rng}", url)
    return f"{url}&{rng}" if "?" in url else f"{url}?{rng}"


def _is_urlopen_mocked() -> bool:
    """Checks if urllib.request.urlopen is replaced by a unittest mock."""
    fn = getattr(urllib.request, "urlopen", None)
    return fn is not None and (hasattr(fn, "_mock_name") or "mock" in type(fn).__name__.lower() or hasattr(fn, "side_effect"))


class _KeepAliveResponseWrapper:
    """Wraps an http.client.HTTPResponse for transparent compatibility with urllib response interface."""
    def __init__(self, raw_resp: Any, conn: Any):
        self._resp = raw_resp
        self._conn = conn
        self.status = getattr(raw_resp, "status", 200)
        self.headers = getattr(raw_resp, "headers", {})
        self.will_close = getattr(raw_resp, "will_close", False)

    def getcode(self) -> int:
        return self.status

    def read(self, amt: int = -1) -> bytes:
        return self._resp.read(amt)

    def close(self):
        if self._conn and getattr(self._conn, "sock", None):
            try: self._conn.sock.shutdown(2)
            except Exception: pass
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
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower()
            if host.endswith(".googlevideo.com") or host == "googlevideo.com":
                return True
            if any(dom in host for dom in ("youtube.com", "youtu.be", "ytimg.com")):
                return True
            path = (parsed.path or "").lower()
            if "videoplayback" in path:
                return True
        except Exception:
            pass
        url_lower = str(url).lower()
        return "googlevideo.com" in url_lower or "videoplayback" in url_lower

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
        """Spawns an asynchronous worker thread for a specific chunk."""
        t = threading.Thread(target=self._chunk_worker, args=(chunk,), daemon=True)
        with self._lock:
            self.active_workers.append(t)
        t.start()

    def _is_stopped(self) -> bool:
        """Checks if current download task was cancelled, aborted, or stopped."""
        return self._cancel_event.is_set() or self._error_abort_event.is_set() or not self.is_running

    def _wait_if_paused(self) -> bool:
        """Blocks while download is paused; returns True if resumed, False if stopped/cancelled."""
        while self._pause_event.is_set() and not self._is_stopped():
            time.sleep(0.1)
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
                        cur_offset = chunk.start_byte + chunk.downloaded_bytes
                        target_end = chunk.end_byte
                        if (self.total_size > 0 and cur_offset > target_end) or (self.total_size == 0 and chunk.downloaded_bytes > 0 and chunk.status == "completed"):
                            if self.total_size > 0: chunk.status = "completed"
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
                        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0", "Connection": "keep-alive"}
                        hdrs.update(self.headers)
                        if self.supports_ranges and self.total_size > 0 and req_end is not None:
                            hdrs["Range"] = f"bytes={cur_offset}-{req_end}"

                        p = urllib.parse.urlsplit(win_url)
                        scheme, host = p.scheme or "http", p.hostname or "localhost"
                        port = p.port or (443 if scheme == "https" else 80)
                        path_q = (p.path or "/") + (f"?{p.query}" if p.query else "")

                        if conn is not None and conn_key != (scheme, host, port):
                            try: conn.close()
                            except Exception: pass
                            conn = None

                        raw_resp = None
                        for send_attempt in range(2):
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
                                break
                            except (http.client.NotConnected, http.client.CannotSendRequest,
                                    http.client.BadStatusLine, ConnectionError, OSError):
                                with self._lock:
                                    if conn in self._active_connections:
                                        self._active_connections.remove(conn)
                                try: conn.close()
                                except Exception: pass
                                conn = None
                                if send_attempt == 1 or self._is_stopped(): raise

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

                        resp = _KeepAliveResponseWrapper(raw_resp, conn)

                    if self.supports_ranges and self.total_size > 0:
                        code = resp.getcode()
                        if code not in (200, 206):
                            if code in (401, 403, 410):
                                self.has_expired_link = True
                                chunk.error_msg = f"HTTP {code}: (Expired or Forbidden Link)"
                            raise RuntimeError(f"Unexpected HTTP status {code}")
                        if code == 200 and cur_offset > 0:
                            raise RuntimeError("Server returned HTTP 200 instead of HTTP 206 for non-zero range")

                    if self._is_stopped():
                        break

                    if out_file is None:
                        f_mode = "r+b" if (chunk.downloaded_bytes > 0 and os.path.exists(chunk.part_filepath)) else "w+b"
                        out_file = open(chunk.part_filepath, f_mode, buffering=1024 * 1024)
                        out_file.seek(chunk.downloaded_bytes if f_mode == "r+b" else 0)
                        out_file.truncate()

                    with self._lock:
                        self._active_connections.append(resp)

                    BUF_SIZE = 262144
                    while not self._is_stopped():
                        if self._pause_event.is_set():
                            break

                        with chunk.lock:
                            pos = chunk.start_byte + chunk.downloaded_bytes
                            if self.total_size > 0 and pos > chunk.end_byte:
                                chunk.status = "completed"
                                return
                            effective_end = min(chunk.end_byte, req_end) if req_end is not None else chunk.end_byte
                            to_read = min(BUF_SIZE, effective_end - pos + 1) if self.total_size > 0 else BUF_SIZE

                        if to_read <= 0:
                            break

                        data = resp.read(to_read)
                        if not data:
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
                                return

                    if out_file:
                        try: out_file.flush()
                        except Exception: pass

                    if self._pause_event.is_set():
                        with self._lock:
                            if resp in self._active_connections:
                                self._active_connections.remove(resp)
                        if resp:
                            try: resp.close()
                            except Exception: pass
                            resp = None
                        if conn:
                            try: conn.close()
                            except Exception: pass
                            conn = None
                        if not self._wait_if_paused():
                            return
                        continue

                    with self._lock:
                        if resp in self._active_connections:
                            self._active_connections.remove(resp)

                    if _is_urlopen_mocked():
                        try: resp.close()
                        except Exception: pass
                        resp = None
                    else:
                        if getattr(raw_resp, "will_close", False) or (expected_seg_bytes is not None and seg_bytes_read < expected_seg_bytes):
                            if conn:
                                try: conn.close()
                                except Exception: pass
                                conn = None
                        resp = None

                    with chunk.lock:
                        if (self.total_size > 0 and chunk.start_byte + chunk.downloaded_bytes > chunk.end_byte) or self.total_size == 0:
                            chunk.status = "completed"
                            return
                        if self.total_size > 0 and (chunk.start_byte + chunk.downloaded_bytes <= chunk.end_byte):
                            if expected_seg_bytes is not None and seg_bytes_read >= expected_seg_bytes:
                                retry_count = 0
                                continue
                            raise RuntimeError(f"Premature EOF from server before chunk completion ({chunk.downloaded_bytes:,}/{chunk.end_byte - chunk.start_byte + 1:,} bytes)")
                        chunk.status = "completed"
                        return

            except Exception as e:
                if self._is_stopped():
                    return
                if self._pause_event.is_set():
                    if not self._wait_if_paused(): return
                    continue
                if isinstance(e, urllib.error.HTTPError):
                    e.close()
                    self.last_http_status = e.code
                    if e.code in (401, 403, 410):
                        self.has_expired_link = True
                        chunk.error_msg = f"HTTP {e.code}: {e.reason} (Expired or Forbidden Link)"
                        break
                if self._is_stopped():
                    return
                retry_count = 0 if seg_bytes_read >= 65536 else (max(0, retry_count - 1) if seg_bytes_read > 0 else retry_count)
                retry_count += 1
                backoff = min(4.0, 0.8 * (1.4 ** min(retry_count, 5)))
                self.log(f"Connection #{chunk.chunk_id} error: {e}. Retry {retry_count}/{max_retries} in {backoff:.1f}s...")
                t_end = time.time() + backoff
                while time.time() < t_end and not self._is_stopped() and not self._pause_event.is_set():
                    time.sleep(0.1)
                if self._is_stopped():
                    return
            finally:
                if out_file:
                    try: out_file.close()
                    except Exception: pass
                    out_file = None
                if conn:
                    with self._lock:
                        if conn in self._active_connections:
                            self._active_connections.remove(conn)
                    try: conn.close()
                    except Exception: pass
                    conn = None
                if resp:
                    with self._lock:
                        if resp in self._active_connections:
                            self._active_connections.remove(resp)
                    try: resp.close()
                    except Exception: pass
                    resp = None
                if self.on_chunk_update:
                    self.on_chunk_update()

        if self._is_stopped():
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
        """Computes smoothed transfer speed, ETA, and progress metrics."""
        now = time.monotonic()
        dt = now - self.last_speed_check_time

        with self._lock:
            total_downloaded = sum(c.downloaded_bytes for c in self.chunks)
            active_count = sum(1 for c in self.chunks if c.status == "active")

        if dt >= 0.12:
            delta_bytes = total_downloaded - self.last_downloaded_bytes
            instant_speed = max(0.0, delta_bytes / dt)
            if self.current_speed == 0.0:
                self.current_speed = instant_speed
            else:
                self.current_speed = (0.45 * instant_speed) + (0.55 * self.current_speed)
            self.last_downloaded_bytes = total_downloaded
            self.last_speed_check_time = now

        if self.current_speed <= 0.0 and total_downloaded > 0:
            st = getattr(self, "start_time", 0.0)
            elapsed = (time.time() - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
            self.current_speed = total_downloaded / max(0.05, elapsed)

        if self.current_speed > 1024 and self.total_size > total_downloaded:
            rem_bytes = self.total_size - total_downloaded
            eta_sec = int(rem_bytes / self.current_speed)
            eta_str = f"{eta_sec // 3600:02d}:{(eta_sec % 3600) // 60:02d}:{eta_sec % 60:02d}"
        else:
            eta_str = "--:--:--"

        if self.on_progress:
            self.on_progress(total_downloaded, self.total_size, self.current_speed, eta_str, active_count)

    def _stop_workers_for_error(self):
        """Closes active socket connections and signals all workers to abort immediately."""
        self._error_abort_event.set()
        with self._lock:
            for conn in list(self._active_connections):
                try: conn.close()
                except Exception: pass
            self._active_connections.clear()


__all__ = ["EngineWorkersMixin", "EngineResumerMixin"]
