"""
progress.py: Coordinator chunk snapshot aggregation, size estimation, and progress/stage emission.
"""
import sys
import threading
import dataclasses
from typing import List

from ..chunk import DownloadChunk
from ...services.media_clipper_engine import estimate_clip_total_bytes


class CoordinatorProgressMixin:
    """Progress calculation, stage reporting, and chunk snapshot aggregation for StreamDownloadCoordinator."""

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


__all__ = ["CoordinatorProgressMixin"]
