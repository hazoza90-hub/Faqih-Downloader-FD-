"""
StreamDownloadCoordinator: Orchestrates separate video/audio stream downloads and container multiplexing.
"""
import os
import sys
import time
import threading
import subprocess
import shutil
import ssl
import dataclasses
from typing import Optional, Callable, Dict, Any, List

from .engine import TurboDownloadEngine
from .chunk import DownloadChunk
from ..config import IS_WINDOWS
from ..services.subtitle_processor import run_cancellable_ffmpeg
from ..services.youtube_models import YouTubeStreamInfo, MediaStreamInfo, is_youtube_url
from ..services.media_env_helpers import has_ffmpeg, find_ffmpeg_bin, run_ffmpeg_with_progress
from ..services.media_clipper_engine import estimate_clip_total_bytes, download_clipped_stream_direct

class StreamDownloadCoordinator:
    """Coordinates multi-part YouTube & media stream downloads, dynamic chunking, and FFmpeg multiplexing."""
    def __init__(
        self, stream_info: YouTubeStreamInfo, destination_path: str, max_connections: int = 8,
        rate_limit_bytes_per_sec: float = 0.0, ssl_context: Optional[ssl.SSLContext] = None,
        on_progress: Optional[Callable] = None, on_chunk_update: Optional[Callable] = None,
        on_log: Optional[Callable] = None, on_complete: Optional[Callable] = None, on_error: Optional[Callable] = None
    ):
        self.stream_info = stream_info
        self.destination_path = destination_path
        self.max_connections = max(1, min(max_connections, 32))
        self._requested_max_connections = self.max_connections
        self.rate_limit = rate_limit_bytes_per_sec
        self.ssl_context = ssl_context
        self.on_progress, self.on_chunk_update, self.on_log = on_progress, on_chunk_update, on_log
        self.on_complete, self.on_error = on_complete, on_error

        # YouTube googlevideo CDN detection
        self.is_youtube_stream = (
            TurboDownloadEngine.is_googlevideo_url(self.stream_info.video_url)
            or (bool(self.stream_info.audio_url) and TurboDownloadEngine.is_googlevideo_url(self.stream_info.audio_url))
            or is_youtube_url(getattr(self.stream_info, "video_id", ""))
            or "googlevideo.com" in (self.stream_info.video_url or "")
            or getattr(self.stream_info, "platform", "").lower() == "youtube"
        )
        self.current_engine: Optional[TurboDownloadEngine] = None
        self._active_subproc: Optional[Any] = None
        self._lock = threading.RLock()
        self._cancel_event, self._pause_event = threading.Event(), threading.Event()
        self._supervisor_thread: Optional[threading.Thread] = None
        self._is_running = self._is_paused = False
        self.start_time, self._last_active_speed = 0.0, 0.0
        self._active_engines: List[TurboDownloadEngine] = []

        # Aggregated stream metrics for smooth progress visualization
        self._v_total_size = max(0, self.stream_info.video_size)
        self._a_total_size = max(0, self.stream_info.audio_size) if not self.stream_info.is_progressive else 0
        self._v_downloaded, self._a_downloaded, self._active_phase = 0, 0, 1

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
            return estimate_clip_total_bytes(self.stream_info, raw_tot)

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

    def pause(self):
        with self._lock:
            self._is_paused = True; self._pause_event.set()
            if self._active_subproc:
                try: from ..services.media_clipper_engine import _set_process_suspended; _set_process_suspended(self._active_subproc, True)
                except Exception: pass
            for eng in (self._active_engines or ([self.current_engine] if self.current_engine else [])):
                try: eng.pause()
                except Exception: pass
            done, total = self._current_progress_pair()
        if self.on_progress:
            try: self.on_progress(done, total, 0.0, "Paused", 0)
            except Exception: pass

    def resume(self):
        with self._lock:
            self._is_paused = False; self._pause_event.clear()
            if self._active_subproc:
                try: from ..services.media_clipper_engine import _set_process_suspended; _set_process_suspended(self._active_subproc, False)
                except Exception: pass
            engines = self._active_engines or ([self.current_engine] if self.current_engine else [])
            for eng in engines:
                try: eng.resume()
                except Exception: pass
            done, total = self._current_progress_pair()
            active = sum(sum(1 for c in getattr(e, "chunks", []) if getattr(c, "status", "") == "active") for e in engines)
        if self.on_progress:
            try: self.on_progress(done, total, 0.0, "Downloading", active)
            except Exception: pass

    def _make_engine(self, url, dest, max_conn, allow_split, headers, on_prog, on_comp, on_err, est_size):
        pre = {"total_size": int(est_size or 0), "supports_ranges": True} if int(est_size or 0) > 0 else None
        return TurboDownloadEngine(
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

    def _run_coordinator(self):
        video_tmp, audio_tmp, actual_dest = "", "", ""
        is_mp3_request, has_error = False, False
        v_error, a_error = [], []
        try:
            if float(getattr(self.stream_info, "clip_end_sec", 0.0) or 0.0) > float(getattr(self.stream_info, "clip_start_sec", 0.0) or 0.0) >= 0.0:
                if download_clipped_stream_direct(self):
                    return
                if self._cancel_event.is_set() or not self._is_running:
                    return
            if self.stream_info.is_progressive or not self.stream_info.audio_url:
                # Progressive single-stream download with dynamic chunking
                # Check if this is an audio-only stream requesting MP3 conversion via FFmpeg
                src_audio_ext = (getattr(self.stream_info, "audio_ext", "") or "").lower()
                is_mp3_request = (
                    self.stream_info.is_audio_only
                    and (self.destination_path.lower().endswith(".mp3") or self.stream_info.video_ext.lower() == "mp3")
                    and src_audio_ext != "mp3"
                    and has_ffmpeg()
                )
                if is_mp3_request and not self.destination_path.lower().endswith(".mp3"):
                    base, _ = os.path.splitext(self.destination_path)
                    self.destination_path = base + ".mp3"
                actual_dest = self.destination_path + ".audio.tmp" if is_mp3_request else self.destination_path
                plat = getattr(self.stream_info, "platform", "Media")
                tag = plat.upper().replace(" / X", "")
                self.log(f"[{tag}] Initializing dynamic multi-chunk download for: {os.path.basename(self.destination_path)}")

                def _on_single_complete(path, size, elapsed):
                    if is_mp3_request:
                        self.log("[FFMPEG] Transcoding downloaded audio stream to universal MP3...")
                        try:
                            ffmpeg_bin = find_ffmpeg_bin()
                            if not ffmpeg_bin: raise RuntimeError("FFmpeg executable not found.")
                            cmd = [ffmpeg_bin, "-y", "-i", actual_dest, "-vn", "-c:a", "libmp3lame", "-q:a", "2", self.destination_path]
                            cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0
                            def _mp3_prog(pct: float, eta_str: str): self._emit_stage_progress("Transcoding", pct, eta_str)
                            v_dur = float(getattr(self.stream_info, "duration", 0.0) or 0.0)
                            rc, err = run_ffmpeg_with_progress(cmd, cancel_event=self._cancel_event, creationflags=cflags, total_duration=v_dur, on_progress_pct=_mp3_prog, subprocess_mod=subprocess)
                            if rc != 0: raise RuntimeError(f"FFmpeg MP3 transcoding failed: {err.strip()}")
                            if os.path.exists(actual_dest):
                                try: os.remove(actual_dest)
                                except Exception: pass
                            final_sz = os.path.getsize(self.destination_path)
                            self.log(f"[SUCCESS] Audio converted to MP3 successfully ({final_sz:,} bytes)!")
                            with self._lock: self._is_running = False
                            if self.on_complete: self.on_complete(self.destination_path, final_sz, elapsed)
                        except Exception as ex:
                            for p in (actual_dest, self.destination_path):
                                if os.path.exists(p):
                                    try: os.remove(p)
                                    except Exception: pass
                            with self._lock: self._is_running = False
                            if self.on_error: self.on_error(f"MP3 transcoding error: {ex}")
                    else:
                        self._process_subtitles(path)
                        final_sz = os.path.getsize(path) if os.path.isfile(path) else size
                        with self._lock: self._is_running = False
                        if self.on_complete: self.on_complete(path, final_sz, elapsed)

                safe_conn = max(1, self.max_connections)
                allow_split = (self.max_connections > 1)

                def _on_single_prog(downloaded, total, speed, eta, active):
                    if self._is_paused:
                        if self.on_progress: self.on_progress(downloaded, total, 0.0, "Paused", 0)
                        return
                    if speed > 0:
                        self._last_active_speed = speed
                    elif downloaded > 0 and self._last_active_speed <= 0.0:
                        st = self.start_time; el = (time.time() - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
                        self._last_active_speed = downloaded / max(0.05, el)
                    if self.on_progress:
                        self.on_progress(downloaded, total, speed, eta, active)

                def _on_single_error(err):
                    with self._lock: self._is_running = False
                    if self.on_error: self.on_error(err)

                engine = self._make_engine(
                    self.stream_info.video_url, actual_dest, safe_conn, allow_split,
                    self.stream_info.video_headers, _on_single_prog, _on_single_complete, _on_single_error,
                    getattr(self.stream_info, "video_size", 0),
                )
                with self._lock:
                    self.current_engine = engine
                    self._active_engines = [engine]
                    if self._is_paused:
                        engine.pause()
                engine.start()

                while engine.is_running and not self._cancel_event.is_set():
                    time.sleep(0.1)
                return

            # Dual-stream: Video + Audio + FFmpeg merge
            video_tmp = self.destination_path + ".video.tmp"
            a_ext = getattr(self.stream_info, "audio_ext", "m4a") or "m4a"
            audio_tmp = f"{self.destination_path}.audio.{a_ext}.tmp"

            self._active_phase = 1
            plat = getattr(self.stream_info, "platform", "Media")
            tag = plat.upper().replace(" / X", "")
            self.log(f"[{tag}] Phase 1/2: Downloading Video & Audio streams in parallel ({self.stream_info.video_resolution})...")
            v_completed = threading.Event()
            a_completed = threading.Event()
            v_error: List[str] = []
            a_error: List[str] = []

            self._v_speed = 0.0
            self._a_speed = 0.0
            self._v_active = 0
            self._a_active = 0

            def _report_combined():
                with self._lock:
                    combined_total = max(1, self._v_total_size + self._a_total_size)
                    combined_dl = min(combined_total, self._v_downloaded + self._a_downloaded)
                    if self._is_paused:
                        combined_speed, combined_active = 0.0, 0
                    else:
                        combined_speed = self._v_speed + self._a_speed
                        combined_active = self._v_active if not v_completed.is_set() else self._a_active
                        if combined_speed > 0:
                            self._last_active_speed = combined_speed
                        elif combined_dl > 0 and self._last_active_speed <= 0.0:
                            st = self.start_time; el = (time.time() - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
                            self._last_active_speed = combined_dl / max(0.05, el)
                        if combined_speed <= 0.0 and self._last_active_speed > 0 and (v_completed.is_set() or a_completed.is_set()):
                            combined_speed = self._last_active_speed
                if self._is_paused:
                    eta_str = "Paused"
                elif combined_speed > 1024 and combined_total > combined_dl:
                    eta_sec = int((combined_total - combined_dl) / combined_speed)
                    eta_str = f"{eta_sec // 3600:02d}:{(eta_sec % 3600) // 60:02d}:{eta_sec % 60:02d}"
                else:
                    eta_str = "--:--:--"
                if self.on_progress:
                    self.on_progress(combined_dl, combined_total, combined_speed, eta_str, combined_active)

            def _on_v_complete(path, size, elapsed):
                with self._lock:
                    if size > 0: self._v_total_size = size
                    self._v_downloaded = self._v_total_size
                    self._v_speed = 0.0
                    self._v_active = 0
                    if not a_completed.is_set():
                        self.current_engine = a_engine
                v_completed.set()
                _report_combined()

            def _on_v_error(err):
                v_error.append(err)
                v_completed.set()
                a_completed.set()
                try: a_engine.cancel()
                except Exception: pass

            def _on_v_progress(downloaded, total, speed, eta, active):
                with self._lock:
                    self._v_downloaded = downloaded
                    if total > 0: self._v_total_size = total
                    self._v_speed = speed
                    self._v_active = active
                _report_combined()

            def _on_a_complete(path, size, elapsed):
                with self._lock:
                    if size > 0: self._a_total_size = size
                    self._a_downloaded = self._a_total_size
                    self._a_speed = 0.0
                    self._a_active = 0
                a_completed.set()
                _report_combined()

            def _on_a_error(err):
                with self._lock:
                    self._a_speed = 0.0
                    self._a_active = 0
                a_error.append(err); a_completed.set(); _report_combined()

            def _on_a_progress(downloaded, total, speed, eta, active):
                with self._lock:
                    self._a_downloaded = downloaded
                    if total > 0: self._a_total_size = total
                    self._a_speed, self._a_active = speed, active
                _report_combined()

            v_conn = max(1, self.max_connections)
            v_engine = self._make_engine(
                self.stream_info.video_url, video_tmp, v_conn, (self.max_connections > 1),
                self.stream_info.video_headers, _on_v_progress, _on_v_complete, _on_v_error,
                getattr(self.stream_info, "video_size", 0),
            )
            a_conn = min(4, max(2, self.max_connections // 2)) if self.max_connections >= 4 else 1  # Wi-Fi safe: a_conn = 1 on single-stream
            a_engine = self._make_engine(
                self.stream_info.audio_url, audio_tmp, a_conn, (a_conn > 1),  # Wi-Fi safe: allow_dynamic_split=False when a_conn <= 1
                self.stream_info.audio_headers, _on_a_progress, _on_a_complete, _on_a_error,
                getattr(self.stream_info, "audio_size", 0),
            )

            with self._lock:
                self.current_engine = v_engine
                self._active_engines = [v_engine, a_engine]
                if self._is_paused:
                    v_engine.pause()
                    a_engine.pause()
            v_engine.start()
            a_engine.start()

            while not (v_completed.is_set() and a_completed.is_set()) and not self._cancel_event.is_set():
                if v_error:
                    break
                time.sleep(0.05)

            def _drain_workers():
                for eng in (v_engine, a_engine):
                    for w in list(getattr(eng, "active_workers", [])):
                        if w.is_alive() and w != threading.current_thread():
                            w.join(timeout=0.15)

            if self._cancel_event.is_set():
                v_engine.cancel(); a_engine.cancel(); _drain_workers(); return
            if v_error:
                a_engine.cancel(); _drain_workers()
                raise RuntimeError(f"Video stream download error: {v_error[0]}")

            # Audio completeness validation and automatic yt-dlp fallback recovery
            from ..services.media_env_helpers import ensure_complete_audio_file
            if not ensure_complete_audio_file(self.stream_info, audio_tmp, tag, self.log, has_prior_error=bool(a_error)):
                v_engine.cancel(); _drain_workers()
                err_msg = a_error[0] if a_error else "Audio stream is incomplete or missing and recovery failed"
                raise RuntimeError(f"Audio stream download error: {err_msg}")

            # 3. Merge Phase via FFmpeg
            self._active_phase = 3
            with self._lock: self._active_engines.clear()
            combined_total = max(1, self._v_total_size + self._a_total_size)
            self.log(f"[{tag}] Phase 2/2: Merging video and audio streams into final container...")
            def _merge_prog(pct: float, eta_str: str): self._emit_stage_progress("Merging", pct, eta_str)
            from ..services.youtube_service import YouTubeResolver
            v_dur = float(getattr(self.stream_info, "duration", 0.0) or 0.0)
            boost_on = bool(getattr(self.stream_info, "audio_boost_enabled", False))
            YouTubeResolver.merge_video_audio(video_tmp, audio_tmp, self.destination_path, on_log=self.log, cancel_event=self._cancel_event, total_duration=v_dur, on_progress_pct=_merge_prog, audio_boost=boost_on)
            if boost_on: setattr(self.stream_info, "_audio_boost_applied", True)
            self._process_subtitles(self.destination_path)

            elapsed = max(0.01, time.time() - self.start_time)
            final_size = os.path.getsize(self.destination_path) if os.path.isfile(self.destination_path) else combined_total
            self.log(f"[SUCCESS] {plat} media assembled & merged successfully ({final_size:,} bytes in {elapsed:.1f}s)!")
            with self._lock: self._is_running = False
            if self.on_complete:
                self.on_complete(self.destination_path, final_size, elapsed)

        except Exception as e:
            has_error = True
            tag = getattr(self.stream_info, "platform", "Media").upper().replace(" / X", "")
            self.log(f"[{tag} ERROR] {e}")
            with self._lock: self._is_running = False
            if self.on_error: self.on_error(str(e))
        finally:
            with self._lock: self._is_running = False
            # Cleanly remove temporary part files on cancel or error
            if self._cancel_event.is_set() or has_error or v_error or a_error:
                clean_targets = [p for p in (video_tmp, audio_tmp, actual_dest if is_mp3_request else "") if p]
                for p in clean_targets:
                    if os.path.exists(p):
                        try: os.remove(p)
                        except Exception: pass
                    for ext in (".sd_parts", ".tdm_parts"):
                        if os.path.isdir(p + ext):
                            try: shutil.rmtree(p + ext, ignore_errors=True)
                            except Exception: pass

    def _process_subtitles(self, target_path: str):
        try:
            from ..services.media_clipper_engine import process_post_download_clip_and_subtitles
            def _stage_prog(stage_name: str, pct: float, eta_str: str):
                self._emit_stage_progress(stage_name, pct, eta_str)
            f_path = process_post_download_clip_and_subtitles(
                self.stream_info, target_path, on_log=self.log,
                cancel_event=self._cancel_event, on_stage_progress=_stage_prog
            )
            if f_path and os.path.isfile(f_path): self.destination_path = f_path
        except Exception as e:
            self.log(f"[CLIP/SUBTITLES] Warning: {e}")
