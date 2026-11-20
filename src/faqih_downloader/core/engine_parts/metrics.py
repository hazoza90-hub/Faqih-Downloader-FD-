"""
EngineMetricsMixin: Download transfer speed calculation (EMA smoothing), ETA estimation, and progress emission.
"""
import sys
import time
import threading
from collections import deque


def _get_time_monotonic():
    ew = sys.modules.get("faqih_downloader.core.engine_workers")
    if ew is not None and hasattr(ew, "time") and hasattr(ew.time, "monotonic"):
        return ew.time.monotonic()
    return time.monotonic()


class EngineMetricsMixin:
    """Provides progress metrics, EMA speed smoothing over a >=2.0s window, and ETA calculation."""

    def _update_progress_metrics(self):
        """Computes responsive EMA-smoothed transfer speed over a >=2.0s window, ETA, and progress metrics."""
        emit_lock = getattr(self, "_progress_emit_lock", None)
        if emit_lock is None:
            with self._lock:
                emit_lock = self._progress_emit_lock = getattr(self, "_progress_emit_lock", None) or threading.RLock()
        with emit_lock:
            return self._update_progress_metrics_impl()

    def _update_progress_metrics_impl(self):
        with self._lock:
            total_downloaded = sum(c.downloaded_bytes for c in self.chunks)
            active_count = sum(1 for c in self.chunks if c.status == "active")
        if self.is_paused or self._pause_event.is_set():
            self.current_speed = 0.0
            return

        now = _get_time_monotonic()
        samples = getattr(self, "_speed_samples", None)
        if samples is None:
            samples = deque([(self.last_speed_check_time or now, self.last_downloaded_bytes)])
            self._speed_samples = samples
        elif not samples:
            samples.append((now, total_downloaded))

        dt = now - self.last_speed_check_time
        should_emit = (dt >= 0.20) or (self.total_size > 0 and total_downloaded >= self.total_size) or self._is_stopped()
        if dt >= 0.20:
            samples.append((now, total_downloaded))
            while len(samples) > 2 and (now - samples[1][0]) >= 2.5:
                samples.popleft()
            win_dt = now - samples[0][0]
            win_bytes = max(0, total_downloaded - samples[0][1])
            instant_speed = (win_bytes / win_dt) if win_dt > 0 else 0.0
            alpha = 0.40 if instant_speed >= self.current_speed else 0.22
            self.current_speed = instant_speed if self.current_speed <= 0.0 else (alpha * instant_speed + (1.0 - alpha) * self.current_speed)
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

        if self.is_paused or self._pause_event.is_set():
            self.current_speed = 0.0
            return
        if self.on_progress and should_emit:
            self.on_progress(total_downloaded, self.total_size, self.current_speed, eta_str, active_count)
