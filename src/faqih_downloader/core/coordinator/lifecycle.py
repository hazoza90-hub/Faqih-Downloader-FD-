"""
lifecycle.py: Coordinator state properties, progress/stage emission, chunk snapshot aggregation,
pause/resume/cancel/shutdown, URL refresh, and temp file cleanup.
"""
import os
import sys
import time
import shutil
import threading
import dataclasses
from typing import Optional, Dict, Any, List

from ..engine import TurboDownloadEngine
from ..chunk import DownloadChunk
from ...services.subtitle_processor import start_subtitle_prefetch
from ...services.media_clipper_engine import estimate_clip_total_bytes


class CoordinatorLifecycleMixin:
    """Lifecycle, state properties, chunk aggregation, and control methods for StreamDownloadCoordinator."""

    def log(self, msg: str):
        if self.on_log:
            try: self.on_log(msg)
            except Exception: pass

    @property
    def chunks(self) -> List[DownloadChunk]:
        return self.get_chunks_snapshot()

    def get_chunks_snapshot(self) -> List[DownloadChunk]:
        """Returns snapshot combining chunks from all active engines with distinct IDs."""
        with self._lock:
            if getattr(self, "_clip_chunks", None):
                return list(self._clip_chunks)
            res: List[DownloadChunk] = []
            targets = list(self._active_engines) if self._active_engines else ([self.current_engine] if self.current_engine else [])
            if len(self._active_engines) > 1:
                v_eng = self._active_engines[0]
                try:
                    if sum(len(getattr(e, "chunks", []) or []) for e in self._active_engines) > self.max_connections:
                        v_chunks = getattr(v_eng, "chunks", [])
                        if v_chunks and any(getattr(c, "status", "") != "completed" for c in v_chunks):
                            targets = [v_eng]
                        elif v_chunks and len(self._active_engines) > 1:
                            targets = [self._active_engines[1]]
                except Exception:
                    pass
            offset = 0
            for eng in targets:
                try:
                    with eng._lock:
                        max_id = -1
                        for c in eng.chunks:
                            res.append(dataclasses.replace(c, chunk_id=c.chunk_id + offset) if offset > 0 else c)
                            if c.chunk_id > max_id:
                                max_id = c.chunk_id
                        offset += max(0, max_id + 1)
                except Exception:
                    pass
            return res

    def _emit_stage_progress(self, stage_name: str, pct: float, eta_str: str = ""):
        tot = max(100, self.total_size)
        clamped_pct = max(0.0, min(100.0, float(pct or 0.0)))
        done = tot
        n_lanes = max(1, self.max_connections)
        if not getattr(self, "_clip_chunks", None) or len(self._clip_chunks) != n_lanes:
            span = max(1, tot // n_lanes)
            self._clip_chunks = [
                DownloadChunk(chunk_id=i, start_byte=i * span, end_byte=((i + 1) * span - 1 if i < n_lanes - 1 else tot - 1), downloaded_bytes=0, status="active")
                for i in range(n_lanes)
            ]
        for c in self._clip_chunks:
            c_span = max(1, c.end_byte - c.start_byte + 1)
            c.downloaded_bytes = int(c_span * (clamped_pct / 100.0))
            c.status = "completed" if clamped_pct >= 99.9 else "active"
        prog_lbl = f"{stage_name}@{clamped_pct:.1f}|{eta_str}" if eta_str else f"{stage_name}@{clamped_pct:.1f}"
        if self.on_progress: self.on_progress(done, tot, self._last_active_speed, prog_lbl, self.max_connections)
        if self.on_chunk_update:
            try: self.on_chunk_update()
            except Exception: pass

    @property
    def total_size(self) -> int:
        with self._lock:
            if getattr(self, "_clip_total_size", 0) > 0:
                return self._clip_total_size
            if self.stream_info.is_progressive or not self.stream_info.audio_url:
                raw_tot = self.current_engine.total_size if (self.current_engine and self.current_engine.total_size > 0) else self.stream_info.video_size
            else:
                raw_tot = max(1, self._v_total_size + self._a_total_size)
            sc_mod = sys.modules.get("faqih_downloader.core.stream_coordinator")
            est_fn = getattr(sc_mod, "estimate_clip_total_bytes", estimate_clip_total_bytes) if sc_mod else estimate_clip_total_bytes
            return est_fn(self.stream_info, raw_tot)

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

    def _current_progress_pair(self):
        with self._lock:
            if len(self._active_engines) > 1 or self._v_downloaded > 0 or self._a_downloaded > 0:
                tot = max(0, self._v_total_size + self._a_total_size)
                dl = self._v_downloaded + self._a_downloaded
                return (min(tot, dl) if tot > 0 else dl), tot
            eng = self.current_engine
            if eng:
                dl = sum(getattr(c, "downloaded_bytes", 0) for c in getattr(eng, "chunks", []))
                tot = getattr(eng, "total_size", 0) or self._v_total_size
                return dl, tot
            return 0, self.total_size

    def _toggle_subproc(self, suspend: bool):
        if not self._active_subproc: return
        try:
            from ...services.media_clipper_engine import _set_process_suspended
            _set_process_suspended(self._active_subproc, suspend)
        except Exception: pass

    def _emit_progress(self, *args):
        if args[3] != "Paused" and self._is_paused:
            for e in (self._active_engines or ()):
                if getattr(e, "is_running", False) and not getattr(e, "is_paused", False): threading.Thread(target=e.pause, daemon=True).start()
            return
        with self._lock:
            if not hasattr(self, "_prog_emit_lock"): self._prog_emit_lock = threading.RLock()
            lk = self._prog_emit_lock
        with lk:
            if self.on_progress and not (args[3] != "Paused" and self._is_paused):
                try: self.on_progress(*args)
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

    def _make_engine(self, url, dest, max_conn, allow_split, headers, on_prog, on_comp, on_err, est_size):
        pre = {"total_size": int(est_size or 0), "supports_ranges": True} if int(est_size or 0) > 0 else None
        sc_mod = sys.modules.get("faqih_downloader.core.stream_coordinator")
        eng_cls = getattr(sc_mod, "TurboDownloadEngine", TurboDownloadEngine) if sc_mod else TurboDownloadEngine
        return eng_cls(
            url=url, destination_path=dest, max_connections=max_conn, allow_dynamic_split=allow_split,
            rate_limit_bytes_per_sec=self.rate_limit, ssl_context=self.ssl_context, headers=headers,
            on_progress=on_prog, on_chunk_update=self.on_chunk_update, on_log=self.on_log,
            on_complete=on_comp, on_error=on_err, pre_probed_info=pre,
        )

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

    def update_url(self, new_url: str, headers: Optional[Dict[str, str]] = None):
        with self._lock:
            if self.current_engine: self.current_engine.update_url(new_url, headers)

    def refresh_link(self, new_url: str, headers: Optional[Dict[str, str]] = None, auto_resume: bool = True) -> bool:
        with self._lock:
            return self.current_engine.refresh_link(new_url, headers, auto_resume) if self.current_engine else False

    @property
    def url(self) -> str:
        with self._lock:
            if getattr(self.stream_info, "webpage_url", ""):
                return self.stream_info.webpage_url
            v_url = getattr(self.stream_info, "video_url", "")
            if (TurboDownloadEngine.is_googlevideo_url(v_url) or "youtube.com" in v_url or "googlevideo.com" in v_url) and getattr(self.stream_info, "video_id", ""):
                return f"https://www.youtube.com/watch?v={self.stream_info.video_id}"
            return self.current_engine.url if (self.current_engine and getattr(self.current_engine, "url", None)) else v_url

    @property
    def supports_ranges(self) -> bool:
        with self._lock:
            return getattr(self.current_engine, "supports_ranges", True) if self.current_engine else True

    @property
    def has_expired_link(self) -> bool:
        with self._lock:
            return getattr(self.current_engine, "has_expired_link", False) if self.current_engine else False

    @property
    def last_http_status(self) -> int:
        with self._lock:
            return getattr(self.current_engine, "last_http_status", 0) if self.current_engine else 0

    def _safe_remove_paths(self, *paths: str, include_part_dirs: bool = False):
        for p in paths:
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
            if include_part_dirs and p:
                for ext in (".sd_parts", ".tdm_parts"):
                    if os.path.isdir(p + ext): shutil.rmtree(p + ext, ignore_errors=True)

    def _start_subtitle_prefetch(self):
        try:
            sc_mod = sys.modules.get("faqih_downloader.core.stream_coordinator")
            pf_fn = getattr(sc_mod, "start_subtitle_prefetch", start_subtitle_prefetch) if sc_mod else start_subtitle_prefetch
            return pf_fn(self.stream_info, self.destination_path)
        except Exception:
            return None

    def _process_subtitles(self, target_path: str):
        try:
            from ...services.media_clipper_engine import process_post_download_clip_and_subtitles
            f_path = process_post_download_clip_and_subtitles(
                self.stream_info, target_path, on_log=self.log, cancel_event=self._cancel_event,
                on_stage_progress=lambda st, p, eta: self._emit_stage_progress(st, p, eta),
            )
            if f_path and os.path.isfile(f_path): self.destination_path = f_path
        except Exception as e:
            self.log(f"[CLIP/SUBTITLES] Warning: {e}")


__all__ = ["CoordinatorLifecycleMixin"]
