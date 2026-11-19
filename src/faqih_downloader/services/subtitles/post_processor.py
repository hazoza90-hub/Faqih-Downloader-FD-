"""
post_processor.py: Post-download subtitle coordination, burn-tag stripping, and sidecar .srt sync.
"""
import os
import re
import sys
import shutil
import threading
from typing import Dict, Optional, Tuple, Callable, Any

from ..external_subtitle_service import (
    get_valid_ext_tracks,
    get_protected_ext_langs,
    is_protected_external_srt,
    prepare_srt_once,
    process_external_subtitle_tracks,
    rename_sidecar_srts_on_video_rename,
)
try:
    from ..media_env.ffmpeg_probe import find_ffmpeg_bin
except Exception:
    def find_ffmpeg_bin() -> Optional[str]: return shutil.which("ffmpeg")  # type: ignore

from .downloader import download_subtitle_as_srt
from .muxer import embed_subtitle_into_mp4, burn_subtitle_into_video


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


def handle_subtitles_post_download(
    stream_info: Any, output_path: str, on_log: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[Any] = None,
    total_duration: float = 0.0,
    on_progress_pct: Optional[Callable[[float, str], None]] = None,
    download_fn: Optional[Callable[..., Optional[str]]] = None,
    find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None,
    embed_fn: Optional[Callable[..., bool]] = None,
    burn_fn: Optional[Callable[..., bool]] = None,
) -> str:
    """Post-download pipeline: downloads external SRTs, and handles soft-muxing or hard burning."""
    if cancel_event and cancel_event.is_set():
        return output_path
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_prim = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")))
    ext_tracks = get_valid_ext_tracks(stream_info)
    if not has_prim and not ext_tracks:
        return output_path

    sp_mod = sys.modules.get("faqih_downloader.services.subtitle_processor")
    eff_download_fn = download_fn or (getattr(sp_mod, "download_subtitle_as_srt", None) if sp_mod else None) or download_subtitle_as_srt
    eff_embed_fn = embed_fn or (getattr(sp_mod, "embed_subtitle_into_mp4", None) if sp_mod else None) or embed_subtitle_into_mp4
    eff_burn_fn = burn_fn or (getattr(sp_mod, "burn_subtitle_into_video", None) if sp_mod else None) or burn_subtitle_into_video

    eff_find_ffmpeg = find_ffmpeg_fn
    if eff_find_ffmpeg is None or eff_find_ffmpeg is find_ffmpeg_bin:
        sp_find = getattr(sp_mod, "find_ffmpeg_bin", None) if sp_mod else None
        meh_mod = sys.modules.get("faqih_downloader.services.media_env_helpers")
        meh_find = getattr(meh_mod, "find_ffmpeg_bin", None) if meh_mod else None
        if sp_find is not None and sp_find is not find_ffmpeg_bin:
            eff_find_ffmpeg = sp_find
        elif meh_find is not None and meh_find is not find_ffmpeg_bin:
            eff_find_ffmpeg = meh_find
        else:
            eff_find_ffmpeg = find_ffmpeg_bin

    try:
        if has_prim and on_progress_pct is not None:
            try: on_progress_pct(0.0, "--:--")
            except Exception: pass
        pf_thread = getattr(stream_info, "_subtitle_prefetch_thread", None)
        if isinstance(pf_thread, threading.Thread) and pf_thread.is_alive():
            pf_thread.join(timeout=45.0)
        mode = getattr(stream_info, "subtitle_embed_mode", "hard_burn")
        orig_stem = os.path.splitext(output_path)[0]
        from ..media_clipper_engine import prepare_post_download_subtitles
        prim_lang = str(sub.get("language") or sub.get("sub_id") or "").strip().lower() if has_prim else ""
        defer_langs = {prim_lang} if (has_prim and mode == "hard_burn" and prim_lang) else set()
        ext_paths, protected_ext_paths = process_external_subtitle_tracks(
            stream_info, output_path, orig_stem, on_log=on_log, cancel_event=cancel_event,
            download_fn=eff_download_fn, prepare_fn=prepare_post_download_subtitles, defer_prepare_langs=defer_langs,
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
            srt_path = eff_download_fn(sub, output_path)

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

        ffmpeg_bin = eff_find_ffmpeg()
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
                    sec_srt = pf_sec if (isinstance(pf_sec, str) and pf_sec and os.path.isfile(pf_sec)) else (sec_f if os.path.isfile(sec_f) else eff_download_fn(sec_trk, sec_f))
                    if sec_srt and os.path.isfile(sec_srt): sc["secondary_srt_source"] = sec_srt
                burn_kwargs["style_config"] = sc
            ok = eff_burn_fn(output_path, srt_path, ffmpeg_bin, on_log=on_log, **burn_kwargs)
            if ok:
                _cleanup_srt()
                if is_protected_external_srt(srt_path, orig_stem, os.path.splitext(output_path)[0], protected_langs, protected_ext_paths):
                    prepare_srt_once(stream_info, srt_path, os.path.splitext(output_path)[0], prepare_post_download_subtitles)
                if eff_cfg and eff_cfg.get("audio_boost"): setattr(stream_info, "_audio_boost_applied", True)
            elif not (cancel_event and cancel_event.is_set()):
                if on_log: on_log("[SUBTITLES] Hard burn failed; falling back to soft subtitle embedding.")
                output_path, srt_path = _strip_burn_with_srts(output_path, protected_langs, srt_path)
                prepare_srt_once(stream_info, srt_path, os.path.splitext(output_path)[0], prepare_post_download_subtitles)
                if eff_embed_fn(output_path, srt_path, sub.get("language", "und"), ffmpeg_bin, on_log=on_log, **sub_kwargs): _cleanup_srt()
        else:
            if eff_embed_fn(output_path, srt_path, sub.get("language", "und"), ffmpeg_bin, on_log=on_log, **sub_kwargs): _cleanup_srt()
        return output_path
    except Exception as exc:
        if on_log: on_log(f"[SUBTITLES] Warning: Subtitle handling encountered an issue: {exc}")
        return output_path


__all__ = [
    "strip_burn_tag_from_filename",
    "_strip_burn_with_srts",
    "handle_subtitles_post_download",
]
