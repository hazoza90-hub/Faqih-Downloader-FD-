"""
engine_bridge.py: Engine instantiation, URL refresh, and active engine metadata delegation.
"""
import sys
from typing import Optional, Dict

from ..engine import TurboDownloadEngine


class CoordinatorEngineBridgeMixin:
    """Engine factory, URL refresh, and status inspection properties for StreamDownloadCoordinator."""

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


__all__ = ["CoordinatorEngineBridgeMixin"]
