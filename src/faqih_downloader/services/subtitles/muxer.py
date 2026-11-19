"""
muxer.py: Soft subtitle MP4 muxing and hard subtitle frame burning via FFmpeg.
"""
import os
import sys
import time
import subprocess
from typing import Dict, List, Optional, Tuple, Callable, Any

from ..media_env.ffmpeg_runner import run_ffmpeg_with_progress
from .ffmpeg_exec import IS_WINDOWS, _get_ascii_safe_temp_dir

ISO_639_2: Dict[str, str] = {
    "en": "eng", "ar": "ara", "es": "spa", "fr": "fra", "de": "deu", "it": "ita", "pt": "por",
    "ru": "rus", "ja": "jpn", "ko": "kor", "zh": "chi", "zh-hans": "chi", "zh-hant": "chi",
    "hi": "hin", "tr": "tur", "id": "ind", "nl": "nld", "pl": "pol", "vi": "vie", "th": "tha",
    "sv": "swe", "no": "nor", "da": "dan", "fi": "fin",
}


def embed_subtitle_into_mp4(
    video_path: str, srt_path: str, lang_code: str, ffmpeg_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
    subprocess_mod: Any = None,
    run_ffmpeg_fn: Optional[Callable[..., Tuple[int, str]]] = None,
) -> bool:
    """Muxes .srt into MP4 as soft subtitle stream via FFmpeg, atomically replacing video file."""
    if cancel_event and cancel_event.is_set():
        return False
    if not ffmpeg_path or not video_path.lower().endswith(".mp4") or not os.path.isfile(video_path) or not os.path.isfile(srt_path):
        return False

    sp_mod = sys.modules.get("faqih_downloader.services.subtitle_processor")
    sp = subprocess_mod or (getattr(sp_mod, "subprocess", subprocess) if sp_mod else subprocess)
    eff_run_ffmpeg = run_ffmpeg_fn or (getattr(sp_mod, "run_ffmpeg_with_progress", run_ffmpeg_with_progress) if sp_mod else run_ffmpeg_with_progress)

    norm_lang = str(lang_code or "und").strip().lower()
    base_lang = norm_lang.split("-")[0].split("_")[0]
    iso3 = ISO_639_2.get(norm_lang) or ISO_639_2.get(base_lang) or (base_lang if len(base_lang) == 3 and base_lang.isalpha() else "und")
    temp_mp4 = f"{os.path.splitext(video_path)[0]}.submux.mp4"
    video_dir = os.path.dirname(os.path.abspath(video_path))
    ascii_work_dir = _get_ascii_safe_temp_dir(video_dir)
    temp_srt = os.path.join(ascii_work_dir, f"_sd_mux_{os.getpid()}_{int(time.time() * 1000)}.srt")

    try:
        with open(os.path.abspath(srt_path), "r", encoding="utf-8-sig", errors="replace") as sf:
            srt_content = sf.read()
        with open(temp_srt, "w", encoding="utf-8") as df:
            df.write(srt_content)
    except Exception:
        temp_srt = srt_path

    cmd_copy = [
        ffmpeg_path, "-y", "-i", video_path, "-i", temp_srt,
        "-map", "0:v:0", "-map", "0:a?", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
        "-metadata:s:s:0", f"language={iso3}", "-disposition:s:0", "default", "-f", "mp4", temp_mp4
    ]
    cmd_transcode = [
        ffmpeg_path, "-y", "-i", video_path, "-i", temp_srt,
        "-map", "0:v:0", "-map", "0:a?", "-map", "1:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
        "-metadata:s:s:0", f"language={iso3}", "-disposition:s:0", "default", "-f", "mp4", temp_mp4
    ]

    cflags = getattr(sp, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0

    def _exec(current_cmd: List[str]) -> Tuple[int, str]:
        rc, err = eff_run_ffmpeg(
            current_cmd, cancel_event=cancel_event, creationflags=cflags,
            cwd=ascii_work_dir, total_duration=total_duration,
            on_progress_pct=on_progress_pct, subprocess_mod=sp
        )
        if rc == -999 and os.path.exists(temp_mp4):
            try: os.remove(temp_mp4)
            except Exception: pass
        return rc, err

    try:
        rc, err = _exec(cmd_copy)
        if rc != 0 and (not cancel_event or not cancel_event.is_set()):
            if on_log:
                on_log(f"[SUBTITLES] Soft-mux copy attempt failed, retrying with audio transcode AAC: {err[-160:].strip()}")
            if os.path.exists(temp_mp4):
                try: os.remove(temp_mp4)
                except Exception: pass
            rc, err = _exec(cmd_transcode)

        if rc == 0 and os.path.isfile(temp_mp4) and os.path.getsize(temp_mp4) > 0:
            os.replace(temp_mp4, video_path)
            if on_log: on_log(f"[SUBTITLES] Successfully embedded soft subtitle ({iso3}) into MP4 container.")
            return True
        if on_log and err:
            on_log(f"[SUBTITLES] Soft-mux error: {err[-200:].strip()}")
        if os.path.exists(temp_mp4):
            try: os.remove(temp_mp4)
            except Exception: pass
        return False
    except Exception as exc:
        if on_log: on_log(f"[SUBTITLES] FFmpeg soft-muxing skipped: {exc}")
        if os.path.exists(temp_mp4):
            try: os.remove(temp_mp4)
            except Exception: pass
        return False
    finally:
        if temp_srt != srt_path and os.path.exists(temp_srt):
            try: os.remove(temp_srt)
            except Exception: pass


def burn_subtitle_into_video(
    video_path: str, srt_path: str, ffmpeg_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    subtitle_position: str = "bottom",
    style_config: Optional[Dict[str, Any]] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
    subprocess_mod: Any = None,
    run_ffmpeg_fn: Optional[Callable[..., Tuple[int, str]]] = None,
) -> bool:
    """Burns subtitles directly onto video frames using ASS styling filter or robust fallback chain."""
    if cancel_event and cancel_event.is_set():
        return False
    if not ffmpeg_path or not os.path.isfile(video_path) or not os.path.isfile(srt_path):
        return False

    sp_mod = sys.modules.get("faqih_downloader.services.subtitle_processor")
    sp = subprocess_mod or (getattr(sp_mod, "subprocess", subprocess) if sp_mod else subprocess)
    eff_run_ffmpeg = run_ffmpeg_fn or (getattr(sp_mod, "run_ffmpeg_with_progress", run_ffmpeg_with_progress) if sp_mod else run_ffmpeg_with_progress)

    abs_video = os.path.abspath(video_path)
    abs_srt = os.path.abspath(srt_path)
    video_dir = os.path.dirname(abs_video)
    ascii_work_dir = _get_ascii_safe_temp_dir(video_dir)
    burn_srt_name = f"_sd_burn_{os.getpid()}_{int(time.time() * 1000)}.srt"
    burn_srt_path = os.path.join(ascii_work_dir, burn_srt_name)
    burn_ass_name = f"_sd_burn_{os.getpid()}_{int(time.time() * 1000)}.ass"
    burn_ass_path = os.path.join(ascii_work_dir, burn_ass_name)
    temp_burn_mp4 = f"{os.path.splitext(abs_video)[0]}.burn.mp4"

    try:
        with open(abs_srt, "r", encoding="utf-8-sig", errors="replace") as sf:
            srt_content = sf.read()
        with open(burn_srt_path, "w", encoding="utf-8") as bf:
            bf.write(srt_content)
    except Exception as exc:
        if on_log:
            on_log(f"[SUBTITLES] Warning: Failed to prepare UTF-8 SRT: {exc}")
        return False

    escaped_srt = burn_srt_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    escaped_ass = burn_ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

    align_styles = {
        "top": "Alignment=8,MarginV=25,FontSize=20,Outline=1,Shadow=1",
        "middle": "Alignment=5,MarginV=0,FontSize=20,Outline=1,Shadow=1",
        "bottom": "Alignment=2,MarginV=25,FontSize=20,Outline=1,Shadow=1",
    }
    style_str = align_styles.get(str(subtitle_position or "bottom").strip().lower(), align_styles["bottom"])

    candidate_vfs = []
    if style_config is not None:
        cfg = dict(style_config)
        if "subtitle_position" not in cfg and subtitle_position:
            cfg["subtitle_position"] = subtitle_position
        ass_ok = False
        try:
            from ..subtitle_style_engine import generate_styled_ass_file
            ass_ok = generate_styled_ass_file(
                abs_srt, burn_ass_path, video_path=abs_video, ffmpeg_path=ffmpeg_path, **cfg
            )
        except Exception:
            pass
        if ass_ok and os.path.isfile(burn_ass_path):
            candidate_vfs.extend([f"ass={burn_ass_name}", f"ass='{escaped_ass}'"])

    candidate_vfs.extend([
        f"subtitles={burn_srt_name}:charenc=UTF-8:force_style='{style_str}'",
        f"subtitles={burn_srt_name}:force_style='{style_str}'",
        f"subtitles='{escaped_srt}':force_style='{style_str}'",
    ])

    cflags = getattr(sp, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0

    def _run_burn_cmd(current_cmd: List[str]) -> Tuple[int, str]:
        rc, err = eff_run_ffmpeg(
            current_cmd, cancel_event=cancel_event, creationflags=cflags,
            cwd=ascii_work_dir, total_duration=total_duration,
            on_progress_pct=on_progress_pct, subprocess_mod=sp
        )
        if rc == -999 and os.path.exists(temp_burn_mp4):
            try: os.remove(temp_burn_mp4)
            except Exception: pass
        return rc, err

    try:
        success = False
        last_err = ""
        clip_s = float(style_config.get("clip_start", 0.0) or 0.0) if style_config else 0.0
        clip_e = float(style_config.get("clip_end", 0.0) or 0.0) if style_config else 0.0
        clip_args = ["-ss", f"{clip_s:.3f}", "-to", f"{clip_e:.3f}"] if (clip_e > clip_s >= 0 and not (style_config and style_config.get("_already_trimmed"))) else []
        af_args: List[str] = []
        if style_config and style_config.get("audio_boost"):
            try:
                from ..audio_and_chapters_engine import get_studio_audio_boost_filter
                af_args = ["-af", get_studio_audio_boost_filter()]
            except Exception: pass
        for idx, vf in enumerate(candidate_vfs, 1):
            if cancel_event and cancel_event.is_set():
                break
            cmd = [
                ffmpeg_path, "-y", *clip_args, "-i", abs_video, "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                *af_args, "-c:a", "aac", "-b:a", "192k", "-f", "mp4", temp_burn_mp4
            ]
            rc, err = _run_burn_cmd(cmd)
            if rc == 0:
                if os.path.isfile(temp_burn_mp4) and os.path.getsize(temp_burn_mp4) > 0:
                    for _ in range(3):
                        try:
                            os.replace(temp_burn_mp4, abs_video)
                            break
                        except Exception:
                            time.sleep(0.08)
                if on_log:
                    on_log(f"[SUBTITLES] Successfully burned subtitles permanently into video frames (Candidate {idx}).")
                if style_config and style_config.get("audio_boost"): style_config["_audio_boost_applied"] = True
                success = True
                break
            else:
                last_err = err
                if on_log and err:
                    on_log(f"[SUBTITLES] Burn candidate {idx} failed (code {rc}): {err[-180:].strip()}")
                if os.path.exists(temp_burn_mp4):
                    try: os.remove(temp_burn_mp4)
                    except Exception: pass

        if success:
            return True

        if on_log and last_err:
            on_log(f"[SUBTITLES] All subtitle burn candidates failed: {last_err[-200:].strip()}")
        if os.path.exists(temp_burn_mp4):
            try: os.remove(temp_burn_mp4)
            except Exception: pass
        return False
    except Exception as exc:
        if on_log:
            on_log(f"[SUBTITLES] FFmpeg burn exception: {exc}")
        if os.path.exists(temp_burn_mp4):
            try: os.remove(temp_burn_mp4)
            except Exception: pass
        return False
    finally:
        if os.path.exists(burn_srt_path):
            try: os.remove(burn_srt_path)
            except Exception: pass
        if os.path.exists(burn_ass_path):
            try: os.remove(burn_ass_path)
            except Exception: pass


__all__ = [
    "ISO_639_2",
    "embed_subtitle_into_mp4",
    "burn_subtitle_into_video",
]
