"""
Engine lifecycle management mixin: startup, speed control, chunk snapshots, pause, resume, cancel, and cleanup.
"""
import os
import time
import threading
import ssl
import shutil
from collections import deque
from typing import List, Optional

from ..chunk import DownloadChunk


class EngineLifecycleMixin:
    """Download lifecycle, worker cancellation, and state control mixin."""

    def log(self, message: str):
        if self.on_log:
            try:
                self.on_log(f"[{time.strftime('%H:%M:%S')}] {message}")
            except Exception:
                pass

    def set_speed_limit(self, bytes_per_sec: float):
        """Update speed limit on the fly."""
        self.rate_limiter.set_limit(bytes_per_sec)
        spd = "Unlimited" if bytes_per_sec <= 0 else (
            f"{bytes_per_sec / (1024*1024):.2f} MB/s" if bytes_per_sec >= 1024*1024 else f"{bytes_per_sec / 1024:.1f} KB/s"
        )
        self.log(f"Speed limit set to: {spd}")

    def get_chunks_snapshot(self) -> List[DownloadChunk]:
        """Returns a thread-safe snapshot copy of the current chunk list."""
        with self._lock:
            return list(self.chunks)

    def start(self):
        """Launches the download supervisor thread."""
        self.is_running, self.is_paused = True, False
        self._cancel_event.clear()
        self._pause_event.clear()
        now = time.monotonic()
        self.start_time = time.time()
        self._last_active_start_mono = self.last_speed_check_time = self._last_speed_time = now
        dl_bytes = sum(c.downloaded_bytes for c in self.chunks)
        self.last_downloaded_bytes = self._last_speed_bytes = self._session_start_bytes = dl_bytes
        self._speed_samples = deque([(now, dl_bytes)])
        threading.Thread(target=self._supervisor_loop, daemon=True).start()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _abort_active_conns(self, force: bool = True):
        with self._lock:
            for conn in list(self._active_connections):
                sock = getattr(conn, "sock", None) or getattr(getattr(conn, "_conn", None), "sock", None)
                if not isinstance(sock, ssl.SSLSocket):
                    self._close_conn_safely(conn)
            self._active_connections.clear()
        self._drain_conn_pool()

    def pause(self):
        """Pauses all active chunk downloads and signals workers to exit cleanly."""
        if not self.is_running or self.is_paused:
            return
        with self._lock:
            self.is_paused = True
            self._pause_event.set()
            if getattr(self, "_progress_emit_lock", None) is None:
                self._progress_emit_lock = threading.RLock()
            if self._last_active_start_mono is not None:
                self._accumulated_active_sec += max(0.0, time.monotonic() - self._last_active_start_mono)
                self._last_active_start_mono = None
            self.current_speed = 0.0
            if hasattr(self, "_speed_samples"):
                self._speed_samples.clear()
        self._abort_active_conns_on_pause()
        with self._lock:
            dl_bytes = sum(c.downloaded_bytes for c in self.chunks)
            self.last_downloaded_bytes = self._last_speed_bytes = dl_bytes
        threading.Thread(target=self.save_state, daemon=True).start()
        with self._progress_emit_lock:
            self.current_speed = 0.0
            if self.on_progress:
                try:
                    self.on_progress(dl_bytes, self.total_size, 0.0, "Paused", 0)
                except Exception:
                    pass
        self.log("Download paused by user.")

    def resume(self):
        """Resumes all active chunk downloads and spawns workers for dead/incomplete chunks."""
        if not self.is_paused or self.is_cancelled:
            return
        with self._lock:
            if getattr(self, "_progress_emit_lock", None) is None:
                self._progress_emit_lock = threading.RLock()
            self.is_paused = False
            now = time.monotonic()
            self._last_active_start_mono = self.last_speed_check_time = self._last_speed_time = now
            dl_bytes = sum(c.downloaded_bytes for c in self.chunks)
            self.last_downloaded_bytes = self._last_speed_bytes = self._session_start_bytes = dl_bytes
            self._speed_samples = deque([(now, dl_bytes)])
            self._pause_event.clear()
            incomplete = [c for c in self.chunks if not c.is_completed and c.status != "failed"]
            wt = getattr(self, "_worker_threads", {})
            active_cnt = sum(1 for c in incomplete if wt.get(c.chunk_id) is not None and wt[c.chunk_id].is_alive())
            for c in incomplete:
                t = wt.get(c.chunk_id)
                if t is None or not t.is_alive():
                    if active_cnt >= self.max_connections and c.status == "pending":
                        continue
                    c.status = "active"
                    self._spawn_worker(c)
                    active_cnt += 1
        with self._progress_emit_lock:
            if self.on_progress and not self.is_paused:
                try:
                    self.on_progress(dl_bytes, self.total_size, 0.0, "Downloading", active_cnt)
                except Exception:
                    pass
        self.log("Download resumed.")

    def cancel(self):
        """Cancels download and stops all worker threads immediately."""
        self.is_running, self.is_paused, self._last_active_start_mono = False, False, None
        self._user_cancelled = True
        self._cancel_event.set()
        self._pause_event.clear()
        self._abort_active_conns(force=True)
        with self._lock:
            workers = list(self.active_workers)
        for w in workers:
            try:
                w.join(timeout=0.2)
            except Exception:
                pass
        self.log("Download cancelled by user.")
        self.cleanup_temp_files()

    def cleanup_temp_files(self):
        """Safely cleans up temporary chunk directory and files."""
        try:
            lk = getattr(self, "_state_save_lock", None)

            def _rm():
                if getattr(self, "temp_dir", None) and os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir, ignore_errors=True)

            if lk is not None:
                with lk:
                    _rm()
            else:
                _rm()
        except Exception:
            pass
