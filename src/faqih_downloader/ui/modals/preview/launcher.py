"""
launcher.py: Orchestrates VidMate-style video preview window launch via bridge and chromeless/webview UI.
"""
from __future__ import annotations

import os
import re
import sys
import time
import tempfile
import subprocess
import webbrowser
from typing import Dict, List, Optional, Any, Callable

from ....config import get_setting, parse_safe_int
from . import process_launcher
from .process_launcher import IS_WINDOWS, terminate_active_preview_proc, _find_chromeless_browser
from .stream_selector import _find_progressive_mp4_url, _convert_srt_to_vtt_data_uri


def open_video_preview(
    parent: Any,
    url: str,
    video_title: str,
    stream_info: Optional[Any] = None,
    info_dict: Optional[Dict[str, Any]] = None,
    selected_sub_track: Optional[Dict[str, Any]] = None,
    theme: Optional[Dict[str, str]] = None,
    on_log: Optional[Callable[[str], None]] = None,
    selected_audio_track: Optional[Dict[str, Any]] = None,
    options: Optional[List[Any]] = None,
    audio_tracks: Optional[List[Dict[str, Any]]] = None,
    subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
    default_dest_path: str = "",
    on_confirm: Optional[Callable[[Any, str], None]] = None,
    on_open_in_main: Optional[Callable[[Any, str], None]] = None,
    on_cancel: Optional[Callable[[], None]] = None,
    parent_app: Optional[Any] = None,
    modal_ref: Optional[Any] = None,
    use_bridge: bool = True,
    subtitle_embed_mode: str = "hard_burn",
    selected_q_idx: int = 0,
    subtitle_position: str = "bottom",
    subtitle_preset: str = "youtube",
    subtitle_font_scale: float = 1.0,
    subtitle_text_color: str = "#FFFFFF",
    subtitle_bg_mode: str = "box",
    subtitle_pos_x: float = 50.0,
    subtitle_pos_y: float = 86.0,
    max_connections: Optional[int] = None,
    external_subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
    **kwargs,
) -> str:
    """
    Builds and opens a real, VidMate-style video preview with synchronized live audio dubbing,
    asynchronous subtitles, and interactive format picker in a chromeless native window.
    """
    terminate_active_preview_proc()
    clean_url = str(url or "").strip()
    title = str(video_title or "Video Preview").strip()
    if on_log:
        on_log(f"[PREVIEW] Preparing video preview for: {title[:40]}...")

    cur_opt = options[selected_q_idx] if (options and 0 <= selected_q_idx < len(options)) else stream_info
    eff_preset = str(getattr(cur_opt, "subtitle_preset", subtitle_preset or "youtube"))
    eff_scale = float(getattr(cur_opt, "subtitle_font_scale", subtitle_font_scale or 1.0))
    eff_color = str(getattr(cur_opt, "subtitle_text_color", subtitle_text_color or "#FFFFFF"))
    eff_bg = str(getattr(cur_opt, "subtitle_bg_mode", subtitle_bg_mode or "box"))
    eff_px = float(getattr(cur_opt, "subtitle_pos_x", subtitle_pos_x or 50.0))
    eff_py = float(getattr(cur_opt, "subtitle_pos_y", subtitle_pos_y or 86.0))
    eff_conn = (parse_safe_int(max_connections)
                or parse_safe_int(getattr(cur_opt, "max_connections", None))
                or (parse_safe_int(parent_app.conn_var.get()) if (parent_app and hasattr(parent_app, "conn_var")) else None)
                or parse_safe_int(get_setting("max_connections", 8)) or 8)

    chapters = []
    try:
        from ....services.audio_and_chapters_engine import extract_video_chapters
        tot_d = float((info_dict.get("duration") if isinstance(info_dict, dict) else 0) or getattr(stream_info, "duration", 0) or 0.0)
        chapters = extract_video_chapters(info_dict or {}, total_duration=tot_d)
    except Exception:
        chapters = []

    eff_boost = bool(getattr(cur_opt, "audio_boost_enabled", False))
    eff_ch_title = str(getattr(cur_opt, "selected_chapter_title", "") or "")
    raw_ext = external_subtitle_tracks
    if raw_ext is None and cur_opt is not None:
        cand = getattr(cur_opt, "external_subtitle_tracks", None)
        if isinstance(cand, list) and cand:
            raw_ext = cand
    if raw_ext is None and parent_app is not None:
        cand = getattr(parent_app, "_main_external_subtitle_tracks", None)
        if isinstance(cand, list):
            raw_ext = cand
    eff_ext_subs = [t for t in (raw_ext or []) if isinstance(t, dict) and str(t.get("sub_id") or "").lower() != "none"]

    stream_url = _find_progressive_mp4_url(stream_info, info_dict, source_url=clean_url)

    yt_match = re.search(r'(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})', clean_url)
    video_id = yt_match.group(1) if yt_match else (info_dict.get("id") if isinstance(info_dict, dict) else None)

    # Subtitle metadata
    vtt_data_uri = None
    sub_label = None
    sub_lang = "ar"
    if selected_sub_track and selected_sub_track.get("sub_id") not in (None, "none"):
        sub_label = selected_sub_track.get("label") or selected_sub_track.get("language") or "Subtitles"
        sub_lang = (selected_sub_track.get("language") or "ar").split("-")[0].split("_")[0] or "ar"

    # Audio dubbing metadata
    dub_audio_url = None
    audio_label = None
    if selected_audio_track and selected_audio_track.get("track_id") != "original":
        dub_audio_url = selected_audio_track.get("url")
        audio_label = selected_audio_track.get("label") or selected_audio_track.get("language")

    # Determine quality badge
    quality_label = getattr(stream_info, "resolution_label", None) if stream_info else None
    if not quality_label and stream_url:
        quality_label = "Direct MP4"
    elif not quality_label:
        quality_label = "Web Player"

    # Set up preview bridge session
    sid = None
    port = None
    target_launch_url = None
    if use_bridge:
        try:
            from ....services.preview_stream_bridge import register_preview_session, get_preview_bridge_port
            port = get_preview_bridge_port()
            sid = register_preview_session(
                url=clean_url,
                video_title=title,
                info_dict=info_dict,
                options=options or ([stream_info] if stream_info else []),
                audio_tracks=audio_tracks or ([selected_audio_track] if selected_audio_track else []),
                subtitle_tracks=subtitle_tracks or ([selected_sub_track] if selected_sub_track else []),
                default_dest_path=default_dest_path,
                on_confirm=on_confirm,
                on_open_in_main=on_open_in_main,
                on_cancel=on_cancel,
                parent_app=parent_app,
                modal_ref=modal_ref,
                selected_audio_track=selected_audio_track,
                selected_sub_track=selected_sub_track,
                subtitle_embed_mode=subtitle_embed_mode,
                selected_q_idx=selected_q_idx,
                subtitle_position=subtitle_position,
                subtitle_preset=eff_preset,
                subtitle_font_scale=eff_scale,
                subtitle_text_color=eff_color,
                subtitle_bg_mode=eff_bg,
                subtitle_pos_x=eff_px,
                subtitle_pos_y=eff_py,
                chapters=chapters,
                audio_boost=eff_boost,
                chapter_title=eff_ch_title,
                max_connections=eff_conn,
                external_subtitle_tracks=eff_ext_subs,
            )
            target_launch_url = f"http://127.0.0.1:{port}/player?sid={sid}"
            if not stream_url:
                stream_url = f"http://127.0.0.1:{port}/stream_video?sid={sid}&q_idx={selected_q_idx}"
            if dub_audio_url and not dub_audio_url.startswith("http://127.0.0.1"):
                sel_a_idx = 0
                all_auds = audio_tracks or ([selected_audio_track] if selected_audio_track else [])
                if selected_audio_track and all_auds:
                    for idx, trk in enumerate(all_auds):
                        if trk == selected_audio_track or (trk.get("track_id") and trk.get("track_id") == selected_audio_track.get("track_id")):
                            sel_a_idx = idx
                            break
                dub_audio_url = f"http://127.0.0.1:{port}/stream_audio?sid={sid}&a_idx={sel_a_idx if sel_a_idx > 0 else 1}&q_idx={selected_q_idx}"
            elif not dub_audio_url and options and 0 <= selected_q_idx < len(options):
                cur_opt = options[selected_q_idx]
                if not getattr(cur_opt, "is_progressive", False) and not getattr(cur_opt, "is_audio_only", False) and getattr(cur_opt, "audio_url", None):
                    dub_audio_url = f"http://127.0.0.1:{port}/stream_audio?sid={sid}&a_idx=0&q_idx={selected_q_idx}"
        except Exception as exc:
            if on_log:
                on_log(f"[PREVIEW] Note: Local bridge setup skipped: {exc}")

    # Fallback to synchronous subtitle conversion ONLY when not using bridge
    if not sid and selected_sub_track and selected_sub_track.get("sub_id") not in (None, "none"):
        try:
            from ....services.subtitle_downloader import download_subtitle_as_srt
            temp_sub_stem = os.path.join(tempfile.gettempdir(), f"_sd_prev_{os.getpid()}_{int(time.time()*1000)}")
            srt_path = download_subtitle_as_srt(selected_sub_track, f"{temp_sub_stem}.mp4")
            if srt_path and os.path.isfile(srt_path):
                with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as sf:
                    srt_text = sf.read()
                vtt_data_uri = _convert_srt_to_vtt_data_uri(srt_text)
                try: os.remove(srt_path)
                except Exception: pass
        except Exception:
            pass

    # Generate self-contained HTML
    from ..preview_html_builder import generate_preview_html
    html_content = generate_preview_html(
        url=clean_url,
        video_title=title,
        stream_url=stream_url,
        vtt_data_uri=vtt_data_uri,
        video_id=video_id,
        sub_label=sub_label,
        quality_label=quality_label,
        sub_lang=sub_lang,
        dub_audio_url=dub_audio_url,
        audio_label=audio_label,
        selected_audio_track=selected_audio_track,
        audio_tracks=audio_tracks,
        options=options,
        subtitle_tracks=subtitle_tracks,
        default_dest_path=default_dest_path,
        sid=sid,
        bridge_port=port,
        selected_sub_track=selected_sub_track,
        subtitle_embed_mode=subtitle_embed_mode,
        selected_q_idx=selected_q_idx,
        subtitle_position=subtitle_position,
        subtitle_preset=eff_preset,
        subtitle_font_scale=eff_scale,
        subtitle_text_color=eff_color,
        subtitle_bg_mode=eff_bg,
        subtitle_pos_x=eff_px,
        subtitle_pos_y=eff_py,
        clip_start=float(getattr(options[selected_q_idx], "clip_start_sec", 0.0) or 0.0) if (options and 0 <= selected_q_idx < len(options)) else 0.0,
        clip_end=float(getattr(options[selected_q_idx], "clip_end_sec", 0.0) or 0.0) if (options and 0 <= selected_q_idx < len(options)) else 0.0,
        dual_sub=bool(getattr(options[selected_q_idx], "dual_subtitle_enabled", False)) if (options and 0 <= selected_q_idx < len(options)) else False,
        audio_boost=eff_boost,
        chapters=chapters,
        chapter_title=eff_ch_title,
        max_connections=eff_conn,
        external_subtitle_tracks=eff_ext_subs,
    )

    temp_html = os.path.join(tempfile.gettempdir(), f"_sd_preview_{os.getpid()}_{int(time.time()*1000)}.html")
    with open(temp_html, "w", encoding="utf-8") as hf:
        hf.write(html_content)

    launch_uri = target_launch_url if target_launch_url else f"file:///{temp_html.replace(os.sep, '/')}"
    win_size = "920,720" if options else "860,560"

    vpm_mod = sys.modules.get("faqih_downloader.ui.modals.video_preview_modal")

    def _record_proc(proc: subprocess.Popen) -> None:
        process_launcher._ACTIVE_PREVIEW_PROC = proc
        if vpm_mod is not None:
            try: vpm_mod._ACTIVE_PREVIEW_PROC = proc
            except Exception: pass

    # 1. Check pywebview
    pywebview_available = False
    try:
        import webview  # type: ignore
        pywebview_available = True
    except Exception:
        pass

    if pywebview_available:
        try:
            w, h = map(int, win_size.split(","))
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--preview-html", launch_uri]
            else:
                cmd = [
                    sys.executable, "-c",
                    f"import os, sys, webview\n"
                    f"class Api:\n"
                    f"    def close_window(self):\n"
                    f"        try:\n"
                    f"            for w in getattr(webview, 'windows', []): w.destroy()\n"
                    f"        except Exception: pass\n"
                    f"webview.create_window({repr(title)}, {repr(launch_uri)}, width={w}, height={h}, js_api=Api())\n"
                    f"webview.start()\n"
                    f"os._exit(0)\n"
                ]
            cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WINDOWS else 0
            _record_proc(subprocess.Popen(cmd, creationflags=cflags))
            if on_log:
                on_log("[PREVIEW] Launched preview window via pywebview subprocess.")
            return temp_html
        except Exception:
            pass

    # 2. Chromeless native app window (Edge, Chrome, Brave)
    find_browser_fn = getattr(vpm_mod, "_find_chromeless_browser", _find_chromeless_browser) if vpm_mod else _find_chromeless_browser
    browser_exe = find_browser_fn()
    if browser_exe:
        app_arg = f"--app={launch_uri}"
        cmd = [browser_exe, "--new-window", app_arg, f"--window-size={win_size}"]
        try:
            _record_proc(subprocess.Popen(cmd))
            if on_log:
                on_log(f"[PREVIEW] Launched native chromeless preview window via {os.path.basename(browser_exe)}.")
            return temp_html
        except Exception:
            pass

    # 3. Fallback to system default browser
    try:
        webbrowser.open(launch_uri)
        if on_log:
            on_log("[PREVIEW] Opened preview in default web browser.")
    except Exception as exc:
        if on_log:
            on_log(f"[PREVIEW] Failed to open browser: {exc}")

    return temp_html


__all__ = ["open_video_preview"]
