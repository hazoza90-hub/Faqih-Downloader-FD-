"""
StreamDownloadCoordinator: Orchestrates separate video/audio stream downloads and container multiplexing.
"""
import os
import threading
import ssl
from typing import Optional, Callable, Dict, Any, List

from .engine import TurboDownloadEngine
from .chunk import DownloadChunk
from .coordinator import (
    CoordinatorLifecycleMixin,
    run_single_stream_download,
    run_dual_stream_download,
    merge_dual_streams,
)
from ..config import IS_WINDOWS
from ..services.subtitle_processor import run_cancellable_ffmpeg, start_subtitle_prefetch
from ..services.youtube_models import YouTubeStreamInfo, MediaStreamInfo, is_youtube_url
from ..services.media_env_helpers import has_ffmpeg, find_ffmpeg_bin, run_ffmpeg_with_progress
from ..services.media_clipper_engine import estimate_clip_total_bytes, download_clipped_stream_direct


class StreamDownloadCoordinator(CoordinatorLifecycleMixin):
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

    def _run_coordinator(self):
        video_tmp, audio_tmp = "", ""
        cleanup_ctx: Dict[str, Any] = {"actual_dest": "", "is_mp3_request": False}
        v_error: List[str] = []
        a_error: List[str] = []
        has_error = False
        try:
            if self.destination_path:
                os.makedirs(os.path.dirname(os.path.abspath(self.destination_path)), exist_ok=True)
            self._start_subtitle_prefetch()
            if float(getattr(self.stream_info, "clip_end_sec", 0.0) or 0.0) > float(getattr(self.stream_info, "clip_start_sec", 0.0) or 0.0) >= 0.0:
                if download_clipped_stream_direct(self):
                    return
                if self._cancel_event.is_set() or not self._is_running:
                    return
            if self.stream_info.is_progressive or not self.stream_info.audio_url:
                run_single_stream_download(
                    self, has_ffmpeg_fn=has_ffmpeg, cleanup_ctx=cleanup_ctx,
                )
                return

            video_tmp = self.destination_path + ".video.tmp"
            a_ext = getattr(self.stream_info, "audio_ext", "m4a") or "m4a"
            audio_tmp = f"{self.destination_path}.audio.{a_ext}.tmp"
            plat = getattr(self.stream_info, "platform", "Media")
            tag = plat.upper().replace(" / X", "")
            cancelled, v_error, a_error, v_engine, a_engine = run_dual_stream_download(
                self, video_tmp, audio_tmp, tag,
            )
            if cancelled:
                return
            merge_dual_streams(
                self, video_tmp, audio_tmp, tag, plat, a_error,
                v_engine=v_engine, a_engine=a_engine,
            )
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
                self._safe_remove_paths(
                    video_tmp, audio_tmp,
                    (cleanup_ctx["actual_dest"] if cleanup_ctx.get("is_mp3_request") else ""),
                    include_part_dirs=True,
                )
