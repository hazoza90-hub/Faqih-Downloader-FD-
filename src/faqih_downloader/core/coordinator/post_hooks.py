"""
post_hooks.py: Coordinator temporary path cleanup, subtitle prefetching, and post-download clip/subtitle hooks.
"""
import os
import sys
import shutil

from ...services.subtitle_processor import start_subtitle_prefetch


class CoordinatorPostHooksMixin:
    """Temp file cleanup and subtitle/clip post-processing hooks for StreamDownloadCoordinator."""

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


__all__ = ["CoordinatorPostHooksMixin"]
