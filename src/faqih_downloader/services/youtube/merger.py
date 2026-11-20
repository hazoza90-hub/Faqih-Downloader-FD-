"""
YouTubeStreamMergerMixin: lossless FFmpeg stream multiplexing and transcode fallback.
"""
import os
import sys
import subprocess
from typing import Optional, Callable, Any

from ..media_env.ffmpeg_probe import find_ffmpeg_bin
from ..media_env.ffmpeg_runner import run_ffmpeg_with_progress

_CANONICAL_FIND_FFMPEG_BIN = find_ffmpeg_bin


def _resolve_find_ffmpeg_bin():
    for mod_name in (
        "faqih_downloader.services.youtube_service",
        "faqih_downloader.services.youtube_models",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "find_ffmpeg_bin"):
            fn = getattr(mod, "find_ffmpeg_bin")
            if fn is not _CANONICAL_FIND_FFMPEG_BIN:
                return fn
    return find_ffmpeg_bin


class YouTubeStreamMergerMixin:
    """Mixin providing FFmpeg video + audio stream merging."""

    @staticmethod
    def merge_video_audio(
        video_path: str, audio_path: str, output_path: str,
        on_log: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[Any] = None,
        total_duration: float = 0.0,
        on_progress_pct: Optional[Callable[[float, str], None]] = None,
        audio_boost: bool = False
    ) -> bool:
        """Lossless FFmpeg stream multiplexing (-c copy) or transcode fallback."""
        ffmpeg_bin = _resolve_find_ffmpeg_bin()()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable was not found on PATH or app directory. Cannot merge video and audio.")
        if cancel_event and cancel_event.is_set():
            if on_log:
                on_log("[FFMPEG] Merge cancelled before execution.")
            return False
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video part file not found: {video_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio part file not found: {audio_path}")
        dest_dir = os.path.dirname(output_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        if on_log:
            on_log(f"[FFMPEG] Merging streams into final file: {os.path.basename(output_path)}...")

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform.startswith("win") else 0

        def _run_proc(cmd_list):
            rc, err = run_ffmpeg_with_progress(
                cmd_list, cancel_event=cancel_event, creationflags=flags,
                total_duration=total_duration, on_progress_pct=on_progress_pct, subprocess_mod=subprocess
            )
            if rc == -999 and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            return rc, err

        def _build_cmd(extra_args):
            return [ffmpeg_bin, "-y", "-i", video_path, "-i", audio_path, "-map", "0:v:0", "-map", "1:a:0"] + extra_args + [output_path]

        af_resync = "aresample=async=1:first_pts=0"
        boost_af = ""
        if audio_boost:
            try:
                from ..audio_and_chapters_engine import get_studio_audio_boost_filter
                boost_af = get_studio_audio_boost_filter()
                af_resync = f"{boost_af},{af_resync}"
            except Exception:
                pass

        aac_args = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-threads", "0"]
        audio_incompatible = any(e in audio_path.lower() for e in (".webm", ".opus", ".ogg")) and output_path.lower().endswith((".mp4", ".m4v"))
        first_args = (aac_args + (["-af", boost_af] if boost_af else [])) if audio_boost else (aac_args if audio_incompatible else ["-c", "copy"])
        rc, primary_err = _run_proc(_build_cmd(first_args))
        if cancel_event and cancel_event.is_set():
            return False

        if rc != 0:
            for enc_args, desc in [
                (aac_args + ["-af", af_resync], "audio transcode to AAC with timestamp resync"),
                (["-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k", "-threads", "0", "-af", af_resync], "container transcode (libx264+aac)"),
            ]:
                if on_log:
                    on_log(f"[FFMPEG] Direct copy inapplicable/failed ({rc}). Retrying with {desc}...")
                rc, primary_err = _run_proc(_build_cmd(enc_args))
                if (cancel_event and cancel_event.is_set()) or rc == 0:
                    break
            if rc != 0:
                err_msg = primary_err.strip() or "Unknown FFmpeg error"
                if on_log:
                    on_log(f"[FFMPEG ERROR] Merge failed (exit code {rc}): {err_msg}")
                raise RuntimeError(f"FFmpeg stream merge failed: {err_msg}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("FFmpeg merge completed but output file is missing or empty.")
        for p in (video_path, audio_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        if on_log:
            on_log(f"[FFMPEG SUCCESS] Merged file successfully created ({os.path.getsize(output_path):,} bytes).")
        return True
