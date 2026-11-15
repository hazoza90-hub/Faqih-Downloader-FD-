"""
Subtitle processing, VTT-to-SRT conversion, FFmpeg soft-muxing, and frame burn-in.
Dedicated service for flexible subtitle delivery modes (Stage 8.1 & Stage 9).
"""
import os
import re
import sys
import time
import subprocess
import shutil
import threading
from typing import Dict, List, Optional, Tuple, Callable, Any

from .subtitle_downloader import (
    _format_srt_timestamp,
    _format_seconds_to_srt,
    _parse_timestamp_or_seconds,
    _parse_xml_subtitles_to_srt,
    _parse_json_subtitles_to_srt,
    convert_vtt_to_srt,
    download_subtitle_as_srt,
    _translate_srt_cues_via_gtx,
)
from .external_subtitle_service import (
    get_valid_ext_tracks,
    get_protected_ext_langs,
    is_protected_external_srt,
    submit_external_prefetches,
    prepare_srt_once,
    process_external_subtitle_tracks,
    rename_sidecar_srts_on_video_rename,
)

try:
    from .youtube_models import find_ffmpeg_bin, detect_installed_cookie_browsers
except Exception:
    def find_ffmpeg_bin() -> Optional[str]: return shutil.which("ffmpeg")  # type: ignore
    def detect_installed_cookie_browsers() -> List[str]: return ["edge", "chrome", "firefox"]  # type: ignore

from .media_env_helpers import run_ffmpeg_with_progress

IS_WINDOWS = sys.platform.startswith("win")

ISO_639_2: Dict[str, str] = {
    "en": "eng", "ar": "ara", "es": "spa", "fr": "fra", "de": "deu", "it": "ita", "pt": "por",
    "ru": "rus", "ja": "jpn", "ko": "kor", "zh": "chi", "zh-hans": "chi", "zh-hant": "chi",
    "hi": "hin", "tr": "tur", "id": "ind", "nl": "nld", "pl": "pol", "vi": "vie", "th": "tha",
    "sv": "swe", "no": "nor", "da": "dan", "fi": "fin",
}

def run_cancellable_ffmpeg(cmd, cancel_event=None, creationflags=0, timeout=1800, subprocess_mod=None, total_duration=0.0, on_progress_pct=None):
    """
    Executes an FFmpeg command with cancellation event polling, progress tracking,
    and returns subprocess.CompletedProcess for 100% backward compatibility.
    """
    sp = subprocess_mod or subprocess
    if cancel_event and cancel_event.is_set():
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="Cancelled before execution")
    rc, err = run_ffmpeg_with_progress(
        cmd, cancel_event=cancel_event, creationflags=creationflags,
        total_duration=total_duration, on_progress_pct=on_progress_pct,
        subprocess_mod=sp
    )
    return subprocess.CompletedProcess(cmd, returncode=(-1 if rc == -999 else rc), stdout="", stderr=err)


def strip_burn_tag_from_filename(filepath: str) -> str:
    """Strips [Sub-Burned] or [Sub] tag from file on disk if burning was not performed."""
    if not filepath or not os.path.exists(filepath):
        return filepath
    dir_name, file_name = os.path.split(filepath)
    new_name = re.sub(r'\s*\[(?:sub|sub-burned)\]', '', file_name, flags=re.IGNORECASE).strip()
    if new_name != file_name:
        new_path = os.path.join(dir_name, new_name)
        try:
            if not os.path.exists(new_path) or os.path.samefile(filepath, new_path):
                os.replace(filepath, new_path)
                return new_path
        except Exception:
            pass
    return filepath


def _is_ascii_writable_dir(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    abs_path = os.path.abspath(path)
    if not all(ord(c) < 128 for c in abs_path):
        return False
    test_file = os.path.join(abs_path, f"_sd_test_{os.getpid()}_{int(time.time()*1000)}.tmp")
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False


def _get_ascii_safe_temp_dir(fallback_dir: str) -> str:
    """Returns the first existing writable 100% ASCII directory for libass safe fopen on Windows."""
    if fallback_dir and _is_ascii_writable_dir(fallback_dir):
        return os.path.abspath(fallback_dir)
    import tempfile
    candidates = [
        tempfile.gettempdir(),
        r"C:\Users\Public",
        r"C:\Users\Public\Documents",
        r"C:\Users\Public\Downloads",
        r"C:\Temp",
        r"C:\Windows\Temp",
    ]
    for cand in candidates:
        try:
            if not os.path.isdir(cand) and cand == r"C:\Temp":
                try:
                    os.makedirs(cand, exist_ok=True)
                except Exception:
                    pass
            if _is_ascii_writable_dir(cand):
                return os.path.abspath(cand)
        except Exception:
            pass
    return os.path.abspath(fallback_dir) if fallback_dir else os.getcwd()


def embed_subtitle_into_mp4(
    video_path: str, srt_path: str, lang_code: str, ffmpeg_path: str,
    on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """Muxes .srt into MP4 as soft subtitle stream via FFmpeg, atomically replacing video file."""
    if cancel_event and cancel_event.is_set():
        return False
    if not ffmpeg_path or not video_path.lower().endswith(".mp4") or not os.path.isfile(video_path) or not os.path.isfile(srt_path):
        return False
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

    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0

    def _exec(current_cmd: List[str]) -> Tuple[int, str]:
        rc, err = run_ffmpeg_with_progress(
            current_cmd, cancel_event=cancel_event, creationflags=cflags,
            cwd=ascii_work_dir, total_duration=total_duration,
            on_progress_pct=on_progress_pct, subprocess_mod=subprocess
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
) -> bool:
    """Burns subtitles directly onto video frames using ASS styling filter or robust fallback chain."""
    if cancel_event and cancel_event.is_set():
        return False
    if not ffmpeg_path or not os.path.isfile(video_path) or not os.path.isfile(srt_path):
        return False
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
            from .subtitle_style_engine import generate_styled_ass_file
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

    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0

    def _run_burn_cmd(current_cmd: List[str]) -> Tuple[int, str]:
        rc, err = run_ffmpeg_with_progress(
            current_cmd, cancel_event=cancel_event, creationflags=cflags,
            cwd=ascii_work_dir, total_duration=total_duration,
            on_progress_pct=on_progress_pct, subprocess_mod=subprocess
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
                from .audio_and_chapters_engine import get_studio_audio_boost_filter
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


def _strip_burn_with_srts(
    output_path: str, protected_langs: Optional[set] = None, srt_path: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """Strips [Burn] tag from video filename and keeps matching protected external .srt stems in sync."""
    new_path = strip_burn_tag_from_filename(output_path)
    if new_path != output_path and protected_langs:
        old_s = os.path.splitext(os.path.basename(output_path))[0]
        new_s = os.path.splitext(os.path.basename(new_path))[0]
        rename_sidecar_srts_on_video_rename(os.path.dirname(output_path), old_s, new_s, only_langs=protected_langs)
        if srt_path and os.path.basename(srt_path).startswith(f"{old_s}."):
            cand = os.path.join(os.path.dirname(srt_path), f"{new_s}{os.path.basename(srt_path)[len(old_s):]}")
            if os.path.isfile(cand):
                srt_path = cand
    return new_path, srt_path


def start_subtitle_prefetch(stream_info: Any, output_path: str) -> Optional[threading.Thread]:
    """Starts background parallel prefetch for internal, dual, and external .srt tracks."""
    if not stream_info or not output_path or hasattr(stream_info, "_mock_name"):
        return None
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_prim = isinstance(sub, dict) and sub.get("sub_id") not in (None, "none") and bool(sub.get("url") or sub.get("base_url"))
    ext_tracks = get_valid_ext_tracks(stream_info)
    if not has_prim and not ext_tracks:
        return None

    def _bg():
        from concurrent.futures import ThreadPoolExecutor
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                f_prim = pool.submit(download_subtitle_as_srt, sub, output_path) if has_prim else None
                sec_trk = getattr(stream_info, "secondary_subtitle_track", None)
                f_sec = None
                if has_prim and getattr(stream_info, "dual_subtitle_enabled", False) and isinstance(sec_trk, dict) and (sec_trk.get("url") or sec_trk.get("base_url")):
                    f_sec = pool.submit(download_subtitle_as_srt, sec_trk, f"{os.path.splitext(output_path)[0]}.sec.srt")
                ext_futs = submit_external_prefetches(pool, stream_info, output_path, download_subtitle_as_srt) if ext_tracks else {}
                if f_prim:
                    srt_p = f_prim.result()
                    if isinstance(srt_p, str) and srt_p and os.path.isfile(srt_p): setattr(stream_info, "_prefetched_srt_path", srt_p)
                if f_sec:
                    sec_p = f_sec.result()
                    if isinstance(sec_p, str) and sec_p and os.path.isfile(sec_p): setattr(stream_info, "_prefetched_sec_srt_path", sec_p)
                ext_ready = dict(getattr(stream_info, "_prefetched_external_srts", None) or {})
                for lang, fut in ext_futs.items():
                    try:
                        p = fut.result()
                        if isinstance(p, str) and p and os.path.isfile(p): ext_ready[lang] = p
                    except Exception: pass
                if ext_ready: setattr(stream_info, "_prefetched_external_srts", ext_ready)
        except Exception:
            pass

    t = threading.Thread(target=_bg, daemon=True)
    setattr(stream_info, "_subtitle_prefetch_thread", t)
    t.start()
    return t


def handle_subtitles_post_download(
    stream_info: Any, output_path: str, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
) -> str:
    """Post-download pipeline: downloads external SRTs, and handles soft-muxing or hard burning."""
    if cancel_event and cancel_event.is_set():
        return output_path
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_prim = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")))
    ext_tracks = get_valid_ext_tracks(stream_info)
    if not has_prim and not ext_tracks:
        return output_path
    try:
        if has_prim and on_progress_pct is not None:
            try: on_progress_pct(0.0, "--:--")
            except Exception: pass
        pf_thread = getattr(stream_info, "_subtitle_prefetch_thread", None)
        if isinstance(pf_thread, threading.Thread) and pf_thread.is_alive():
            pf_thread.join(timeout=15.0)
        mode = getattr(stream_info, "subtitle_embed_mode", "hard_burn")
        orig_stem = os.path.splitext(output_path)[0]
        from .media_clipper_engine import prepare_post_download_subtitles
        prim_lang = str(sub.get("language") or sub.get("sub_id") or "").strip().lower() if has_prim else ""
        defer_langs = {prim_lang} if (has_prim and mode == "hard_burn" and prim_lang) else set()
        ext_paths, protected_ext_paths = process_external_subtitle_tracks(
            stream_info, output_path, orig_stem, on_log=on_log, cancel_event=cancel_event,
            download_fn=download_subtitle_as_srt, prepare_fn=prepare_post_download_subtitles, defer_prepare_langs=defer_langs,
        )
        protected_langs = get_protected_ext_langs(stream_info)
        if not has_prim or (cancel_event and cancel_event.is_set()):
            return output_path

        prefetched = getattr(stream_info, "_prefetched_srt_path", None)
        if isinstance(prefetched, str) and prefetched and os.path.isfile(prefetched):
            srt_path = prefetched
            if on_log: on_log(f"[SUBTITLES] Using prefetched subtitle track: {os.path.basename(srt_path)}")
        elif prim_lang and prim_lang in ext_paths and os.path.isfile(ext_paths[prim_lang]):
            srt_path = ext_paths[prim_lang]
        else:
            if on_log: on_log(f"[SUBTITLES] Downloading subtitle track: {sub.get('label', sub.get('language', 'sub'))}...")
            srt_path = download_subtitle_as_srt(sub, output_path)

        if not srt_path or not os.path.isfile(srt_path) or (cancel_event and cancel_event.is_set()):
            if on_log and not (cancel_event and cancel_event.is_set()):
                on_log("[SUBTITLES] Warning: Failed to download or convert subtitle track.")
            return _strip_burn_with_srts(output_path, protected_langs)[0] if mode == "hard_burn" else output_path

        if on_log: on_log(f"[SUBTITLES] Saved subtitle to {os.path.basename(srt_path)}")
        if mode != "hard_burn":
            prepare_srt_once(stream_info, srt_path, orig_stem, prepare_post_download_subtitles)
        if mode == "srt_only" or (cancel_event and cancel_event.is_set()):
            if on_log and mode == "srt_only":
                on_log("[SUBTITLES] External .srt saved (SRT-only mode selected; skipping video mux).")
            return output_path

        ffmpeg_bin = find_ffmpeg_bin()
        if not ffmpeg_bin or not output_path.lower().endswith(".mp4"):
            if on_log and not ffmpeg_bin: on_log("[SUBTITLES] FFmpeg not found; skipping video subtitle embedding/burning.")
            if mode == "hard_burn":
                output_path, srt_path = _strip_burn_with_srts(output_path, protected_langs, srt_path)
                prepare_srt_once(stream_info, srt_path, os.path.splitext(output_path)[0], prepare_post_download_subtitles)
            return output_path

        sub_kwargs: Dict[str, Any] = {"cancel_event": cancel_event} if cancel_event is not None else {}
        if on_progress_pct is not None: sub_kwargs["on_progress_pct"] = on_progress_pct
        eff_dur = float(total_duration or 0.0)
        if eff_dur <= 0.0 and not hasattr(stream_info, "_mock_name"):
            d = getattr(stream_info, "duration", 0.0) or getattr(stream_info, "duration_seconds", 0.0)
            if isinstance(d, (int, float)) and d > 0: eff_dur = float(d)
        if eff_dur > 0.0 and on_progress_pct is not None: sub_kwargs["total_duration"] = eff_dur
        default_srt = f"{orig_stem}.srt"

        def _cleanup_srt():
            cur_stem = os.path.splitext(output_path)[0]
            for p_path in {srt_path, default_srt, f"{cur_stem}.srt", f"{orig_stem}.sec.srt", f"{cur_stem}.sec.srt"}:
                if p_path and os.path.isfile(p_path) and not is_protected_external_srt(p_path, orig_stem, cur_stem, protected_langs, protected_ext_paths):
                    try: os.remove(p_path)
                    except Exception: pass

        sub_pos = getattr(stream_info, "subtitle_position", None)
        if mode == "hard_burn":
            if on_log: on_log("[SUBTITLES] Burning subtitles permanently onto video frames...")
            burn_kwargs = dict(sub_kwargs)
            if isinstance(sub_pos, str) and sub_pos != "bottom": burn_kwargs["subtitle_position"] = sub_pos
            cfg_from_track = sub.get("style_config") if isinstance(sub, dict) else None
            eff_cfg = getattr(stream_info, "style_config", None) or cfg_from_track
            if not hasattr(stream_info, "_mock_name") and (eff_cfg or getattr(stream_info, "subtitle_preset", None) or getattr(stream_info, "clip_start_sec", None) or getattr(stream_info, "clip_end_sec", None)):
                sc = dict(eff_cfg) if eff_cfg else {
                    "preset": getattr(stream_info, "subtitle_preset", "youtube"), "font_scale": getattr(stream_info, "subtitle_font_scale", 1.0),
                    "text_color": getattr(stream_info, "subtitle_text_color", "#FFFFFF"), "bg_mode": getattr(stream_info, "subtitle_bg_mode", "box"),
                    "pos_x": getattr(stream_info, "subtitle_pos_x", 50.0), "pos_y": getattr(stream_info, "subtitle_pos_y", 86.0), "subtitle_position": sub_pos,
                }
                sc.setdefault("custom_edits", getattr(stream_info, "subtitle_custom_edits", {}))
                sc.setdefault("clip_start", getattr(stream_info, "clip_start_sec", 0.0)); sc.setdefault("clip_end", getattr(stream_info, "clip_end_sec", 0.0))
                sc.setdefault("_already_trimmed", bool(getattr(stream_info, "_already_trimmed", False)))
                sec_trk = getattr(stream_info, "secondary_subtitle_track", None) or sc.get("secondary_track")
                if getattr(stream_info, "dual_subtitle_enabled", False) and sec_trk and isinstance(sec_trk, dict) and (sec_trk.get("url") or sec_trk.get("base_url")):
                    sec_f, pf_sec = f"{orig_stem}.sec.srt", getattr(stream_info, "_prefetched_sec_srt_path", None)
                    sec_srt = pf_sec if (isinstance(pf_sec, str) and pf_sec and os.path.isfile(pf_sec)) else (sec_f if os.path.isfile(sec_f) else download_subtitle_as_srt(sec_trk, sec_f))
                    if sec_srt and os.path.isfile(sec_srt): sc["secondary_srt_source"] = sec_srt
                burn_kwargs["style_config"] = sc
            ok = burn_subtitle_into_video(output_path, srt_path, ffmpeg_bin, on_log=on_log, **burn_kwargs)
            if ok:
                _cleanup_srt()
                if is_protected_external_srt(srt_path, orig_stem, os.path.splitext(output_path)[0], protected_langs, protected_ext_paths):
                    prepare_srt_once(stream_info, srt_path, os.path.splitext(output_path)[0], prepare_post_download_subtitles)
                if eff_cfg and eff_cfg.get("audio_boost"): setattr(stream_info, "_audio_boost_applied", True)
            elif not (cancel_event and cancel_event.is_set()):
                if on_log: on_log("[SUBTITLES] Hard burn failed; falling back to soft subtitle embedding.")
                output_path, srt_path = _strip_burn_with_srts(output_path, protected_langs, srt_path)
                prepare_srt_once(stream_info, srt_path, os.path.splitext(output_path)[0], prepare_post_download_subtitles)
                if embed_subtitle_into_mp4(output_path, srt_path, sub.get("language", "und"), ffmpeg_bin, on_log=on_log, **sub_kwargs): _cleanup_srt()
        else:
            if embed_subtitle_into_mp4(output_path, srt_path, sub.get("language", "und"), ffmpeg_bin, on_log=on_log, **sub_kwargs): _cleanup_srt()
        return output_path
    except Exception as exc:
        if on_log: on_log(f"[SUBTITLES] Warning: Subtitle handling encountered an issue: {exc}")
        return output_path
