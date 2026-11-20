"""
controls.py: Coordinator logging, running/paused state, speed limiting, start/pause/resume/cancel/shutdown.
"""
import time
import threading


class CoordinatorControlsMixin:
    """Playback/transfer control and state methods for StreamDownloadCoordinator."""

    def log(self, msg: str):
        if self.on_log:
            try: self.on_log(msg)
            except Exception: pass

    @property
    def is_running(self) -> bool:
        with self._lock: return self._is_running

    @property
    def is_paused(self) -> bool:
        with self._lock: return self._is_paused

    def set_speed_limit(self, bytes_per_sec: float):
        with self._lock:
            self.rate_limit = bytes_per_sec
            targets = list(self._active_engines) if self._active_engines else ([self.current_engine] if self.current_engine else [])
            for eng in targets:
                try: eng.set_speed_limit(bytes_per_sec)
                except Exception: pass

    def start(self):
        self._is_running, self._is_paused = True, False
        self._cancel_event.clear(); self._pause_event.clear()
        self.start_time = time.time()
        self._supervisor_thread = threading.Thread(target=self._run_coordinator, daemon=True)
        self._supervisor_thread.start()

    def _toggle_subproc(self, suspend: bool):
        if not self._active_subproc: return
        try:
            from ...services.media_clipper_engine import _set_process_suspended
            _set_process_suspended(self._active_subproc, suspend)
        except Exception: pass

    def pause(self):
        with self._lock:
            self._is_paused = True; self._pause_event.set(); self._toggle_subproc(True)
            self._v_speed = 0.0; self._a_speed = 0.0
            self._v_active = 0; self._a_active = 0
            for eng in (self._active_engines or ([self.current_engine] if self.current_engine else [])):
                try: eng.pause()
                except Exception: pass
            done, total = self._current_progress_pair()
        self._emit_progress(done, total, 0.0, "Paused", 0)

    def resume(self):
        with self._lock:
            self._is_paused = False; self._pause_event.clear(); self._toggle_subproc(False)
            engines = self._active_engines or ([self.current_engine] if self.current_engine else [])
            for eng in engines:
                try: eng.resume()
                except Exception: pass
            done, total = self._current_progress_pair()
            active = sum(sum(1 for c in getattr(e, "chunks", []) if getattr(c, "status", "") == "active") for e in engines)
        self._emit_progress(done, total, 0.0, "Downloading", active)

    def _stop_all(self, use_safe: bool = False):
        with self._lock:
            self._is_running = False
            self._cancel_event.set()
            if self._active_subproc:
                try: self._active_subproc.kill()
                except Exception: pass
                self._active_subproc = None
            for eng in (self._active_engines or ([self.current_engine] if self.current_engine else [])):
                try: (eng.safe_shutdown() if (use_safe and hasattr(eng, "safe_shutdown")) else eng.cancel())
                except Exception: pass

    def cancel(self):
        self._stop_all(use_safe=False)

    def safe_shutdown(self):
        self._stop_all(use_safe=True)


__all__ = ["CoordinatorControlsMixin"]
