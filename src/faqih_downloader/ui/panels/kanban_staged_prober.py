"""
kanban_staged_prober.py: Staged URL probers and download launch workers
for Column 1 (Queued & Parsing / Staged Links) in Smart Download (SD).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, List, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.locales.i18n import tr
from faqih_downloader.utils.url_utils import derive_download_filename
from faqih_downloader.utils.file_ops import get_file_category_and_icon, resolve_categorized_path


def stage_media_option_in_col1(
    gui: Any,
    url: str,
    raw_title: str,
    selected_opt: Any,
    final_dest: str,
    duration: int = 0
) -> None:
    """
    Constructs video/audio format metadata and stages it into Column 1 without auto-starting download.
    """
    if not gui:
        return
    try:
        from faqih_downloader.services.youtube_models import extract_media_platform
    except Exception:
        extract_media_platform = lambda u: "Media"

    file_name = os.path.basename(final_dest) if final_dest else (raw_title or "video.mp4")
    file_size = getattr(selected_opt, "filesize", 0) or getattr(selected_opt, "filesize_approx", 0) or 0
    is_audio = bool(getattr(selected_opt, "is_audio_only", False))
    badge = getattr(selected_opt, "resolution_label", "") or getattr(selected_opt, "quality_label", "") or (getattr(selected_opt, "ext", "MP4") or "MP4").upper()
    category = "Audio" if is_audio else "Video"
    platform = extract_media_platform(url)

    target = gui
    if not hasattr(target, "stage_probed_link_in_col1"):
        target = getattr(gui, "parent_app", None) or getattr(gui, "gui", None) or getattr(gui, "master", None) or gui

    media_ctx = getattr(target, "_pending_media_context", None)
    info_dict = {
        "url": url,
        "file_name": file_name,
        "file_size": file_size,
        "badge": badge,
        "category": category,
        "icon": "🎵" if is_audio else "🎬",
        "supports_resume": True,
        "final_dest": final_dest,
        "duration": duration,
        "platform": platform,
        "selected_opt": selected_opt,
        "stream_info": media_ctx.get("info") if isinstance(media_ctx, dict) else None,
        "media_context": dict(media_ctx) if isinstance(media_ctx, dict) else None,
    }

    if hasattr(target, "stage_probed_link_in_col1"):
        target.stage_probed_link_in_col1(info_dict)


def _start_staged_download(gui: Any, item_or_url: Any) -> None:
    """Launches download for a staged card, properly preserving media context if present."""
    try:
        if isinstance(item_or_url, dict):
            info = item_or_url
            url = info.get("url", "")
        else:
            url = str(item_or_url or "")
            staged = getattr(gui, "_staged_links", [])
            info = next((it for it in staged if it.get("url") == url), {"url": url})

        dest = info.get("final_dest", "")
        max_conn = int(info.get("conn_count", 8))
        speed_limit = float(info.get("speed_limit", 0.0))

        if hasattr(gui, "entry_url") and gui.entry_url:
            gui.entry_url.delete(0, tk.END)
            gui.entry_url.insert(0, url)
        if hasattr(gui, "entry_dest") and gui.entry_dest and dest:
            gui.entry_dest.delete(0, tk.END)
            gui.entry_dest.insert(0, dest)
        if hasattr(gui, "conn_var"):
            gui.conn_var.set(str(max_conn))
        if hasattr(gui, "entry_custom_speed") and gui.entry_custom_speed:
            gui.entry_custom_speed.delete(0, tk.END)
            if speed_limit > 0:
                gui.entry_custom_speed.insert(0, str(int(speed_limit / 1024.0)))

        # Ensure latest choices from main media bar are read if this is the active media URL
        cur_ctx = getattr(gui, "_pending_media_context", None)
        if isinstance(cur_ctx, dict) and cur_ctx.get("url") == url:
            if hasattr(gui, "_sync_media_bar_state"):
                try: gui._sync_media_bar_state()
                except Exception: pass
        elif info.get("media_context"):
            gui._pending_media_context = dict(info["media_context"])
        elif info.get("selected_opt") is not None:
            gui._pending_media_context = {
                "url": url,
                "info": info.get("stream_info") if isinstance(info.get("stream_info"), dict) else {},
                "selected_option": info.get("selected_opt"),
                "selected_opt": info.get("selected_opt"),
                "final_dest": dest
            }

        if hasattr(gui, "remove_staged_link"):
            gui.remove_staged_link(url)

        if hasattr(gui, "_on_start_download"):
            gui._on_start_download()
        elif hasattr(gui, "start_download"):
            gui.start_download()
    except Exception:
        pass


def _probe_media_worker(gui: Any, url_clean: str, base_dir: str, conn_count: int, speed_limit: float):
    from faqih_downloader.services.youtube_models import extract_media_platform
    from faqih_downloader.services.youtube_service import YouTubeResolver, sanitize_filename
    from faqih_downloader.config import get_setting

    cookies_browser = get_setting("cookies_browser", "none") or "none"
    resolver = YouTubeResolver(cookies_from_browser=cookies_browser, on_log=getattr(gui, "log", None))

    stream_info, raw_info, opts_list, best_opt, raw_title, dur, ext = None, None, [], None, "", 0, "mp4"
    try:
        # Try extract_format_options FIRST (real YouTubeResolver method returning (info_dict, opts))
        if hasattr(resolver, "extract_format_options"):
            try:
                raw_info, opts_list = resolver.extract_format_options(url_clean)
                if opts_list:
                    best_opt = opts_list[0]
                    stream_info = raw_info
            except Exception:
                raw_info, opts_list = None, []

        if not best_opt and hasattr(resolver, "extract_stream_info"):
            try:
                stream_info = resolver.extract_stream_info(url_clean)
            except Exception:
                stream_info = None

        if not best_opt and not stream_info and hasattr(resolver, "extract_info"):
            try:
                stream_info = resolver.extract_info(url_clean)
            except Exception:
                stream_info = None
    except Exception:
        stream_info = None

    if stream_info or raw_info or best_opt:
        meta_src = raw_info if isinstance(raw_info, dict) else (stream_info if isinstance(stream_info, dict) else {})
        raw_title = getattr(stream_info, "title", None) or meta_src.get("title") or ""
        dur = getattr(stream_info, "duration", None) or meta_src.get("duration") or 0
        formats = getattr(stream_info, "formats", None) or getattr(stream_info, "options", None) or meta_src.get("formats") or opts_list
        if formats and not best_opt:
            best_opt = formats[0]
            opts_list = formats

        file_size = getattr(best_opt, "filesize", None) or getattr(best_opt, "filesize_approx", None) or getattr(stream_info, "video_size", 0) or (best_opt.get("filesize", 0) if isinstance(best_opt, dict) else 0) or 0
        badge = getattr(best_opt, "resolution_label", None) or getattr(best_opt, "quality_label", None) or getattr(stream_info, "video_resolution", None) or (getattr(best_opt, "ext", "MP4") if best_opt else "MP4")
        badge = str(badge).upper() if badge else "MP4"
        is_audio = bool(getattr(best_opt, "is_audio_only", False) or getattr(stream_info, "is_audio_only", False))
        ext = getattr(best_opt, "ext", None) or getattr(stream_info, "video_ext", None) or ("mp3" if is_audio else "mp4")
    else:
        from faqih_downloader.utils.url_utils import derive_download_filename
        raw_title = derive_download_filename(url_clean) or "media_stream"
        file_size, badge, is_audio, ext = 0, "MEDIA", False, "mp4"

    ext = str(ext or "mp4").lstrip(".")
    clean_title = sanitize_filename(raw_title) if raw_title else "video"
    dest_filename = f"{clean_title}.{ext}"
    try:
        auto_cat = getattr(gui, "auto_categorize_folders", True)
        final_dest = resolve_categorized_path(base_dir, dest_filename, auto_categorize=auto_cat, create_dir=False)
    except Exception:
        final_dest = os.path.join(base_dir, dest_filename)

    category = "Audio" if is_audio else "Video"
    platform = extract_media_platform(url_clean)

    audio_tracks, subtitle_tracks = [], []
    info_dict_meta = raw_info if isinstance(raw_info, dict) else (stream_info if isinstance(stream_info, dict) else {})
    if info_dict_meta:
        try:
            from faqih_downloader.services.youtube_tracks import extract_audio_tracks, extract_subtitle_tracks
            audio_tracks = extract_audio_tracks(info_dict_meta) or []
            subtitle_tracks = extract_subtitle_tracks(info_dict_meta) or []
        except Exception:
            audio_tracks, subtitle_tracks = [], []

    if best_opt is not None:
        gui._pending_media_context = {
            "url": url_clean, "raw_title": raw_title,
            "info": info_dict_meta, "stream_info": stream_info, "options": opts_list,
            "selected_opt": best_opt, "selected_option": best_opt, "option": best_opt,
            "audio_tracks": audio_tracks, "subtitle_tracks": subtitle_tracks,
            "resolver": resolver, "final_dest": final_dest, "dest": final_dest,
            "cookies_browser": cookies_browser, "referer": ""
        }
        def _sync_main_gui():
            if hasattr(gui, "entry_dest") and gui.entry_dest and tk:
                cur_u = gui.entry_url.get().strip() if (hasattr(gui, "entry_url") and gui.entry_url) else url_clean
                if not cur_u or cur_u == url_clean:
                    try:
                        gui.entry_dest.delete(0, tk.END)
                        gui.entry_dest.insert(0, final_dest)
                    except Exception:
                        pass
            if hasattr(gui, "populate_main_media_bar") and isinstance(info_dict_meta, dict) and opts_list:
                try:
                    gui.populate_main_media_bar(
                        url=url_clean, dest=final_dest, info=info_dict_meta,
                        options=opts_list, selected_opt=best_opt,
                        audio_tracks=audio_tracks, subtitle_tracks=subtitle_tracks,
                        resolver=resolver
                    )
                except Exception:
                    pass

        if hasattr(gui, "dispatch_to_main_thread") and callable(gui.dispatch_to_main_thread):
            gui.dispatch_to_main_thread(_sync_main_gui)
        elif hasattr(gui, "after") and callable(gui.after):
            gui.after(0, _sync_main_gui)
        else:
            _sync_main_gui()
    else:
        gui._pending_media_context = None

    info_dict = {
        "url": url_clean, "file_name": dest_filename, "file_size": file_size, "badge": badge,
        "category": category, "icon": "🎵" if is_audio else "🎬", "supports_resume": True,
        "final_dest": final_dest, "duration": dur, "platform": platform,
        "conn_count": conn_count, "speed_limit": speed_limit,
        "selected_opt": best_opt, "stream_info": stream_info,
        "media_context": dict(gui._pending_media_context) if gui._pending_media_context else None
    }
    if hasattr(gui, "stage_probed_link_in_col1"):
        gui.stage_probed_link_in_col1(info_dict)


def _probe_file_worker(gui: Any, url_clean: str, base_dir: str, conn_count: int, speed_limit: float):
    filename = derive_download_filename(url_clean)
    category, icon = get_file_category_and_icon(filename or url_clean)
    badge = os.path.splitext(filename)[1].upper().lstrip(".") or category.upper()
    file_size, supports_resume, resolved_url = 0, True, url_clean
    try:
        from faqih_downloader.core.html_resolver import resolve_real_download_url
        probe_res = resolve_real_download_url(url_clean, timeout=6.0)
        if probe_res.get("resolved") and probe_res.get("url"):
            resolved_url = probe_res["url"]
        if probe_res.get("filename"):
            filename = probe_res["filename"]
            category, icon = get_file_category_and_icon(filename)
            badge = os.path.splitext(filename)[1].upper().lstrip(".") or category.upper()
        if probe_res.get("size"):
            file_size = int(probe_res["size"])
    except Exception:
        pass

    try:
        auto_cat = getattr(gui, "auto_categorize_folders", True)
        final_dest = resolve_categorized_path(base_dir, filename, auto_categorize=auto_cat, create_dir=False)
    except Exception:
        final_dest = os.path.join(base_dir, filename)

    info_dict = {
        "url": resolved_url, "file_name": filename, "file_size": file_size,
        "category": category, "badge": badge, "supports_resume": supports_resume,
        "final_dest": final_dest, "conn_count": conn_count, "speed_limit": speed_limit
    }
    if hasattr(gui, "stage_probed_link_in_col1"):
        gui.stage_probed_link_in_col1(info_dict)


def probe_and_stage_pasted_url(gui: Any, url: str) -> None:
    """
    Background worker probing a pasted URL for filename, size, resume support,
    and staging it into Column 1 without immediately launching download.
    For media URLs, uses YouTubeResolver and displays a parsing indicator.
    """
    url_clean = str(url or "").strip()
    if not url_clean or not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return

    is_media = False
    try:
        from faqih_downloader.services.youtube_models import is_youtube_url, is_social_media_url
        from faqih_downloader.services.youtube_service import is_media_url
        if is_youtube_url(url_clean) or is_social_media_url(url_clean) or is_media_url(url_clean):
            is_media = True
    except Exception:
        pass

    if is_media and hasattr(gui, "add_parsing_link"):
        gui.add_parsing_link(url_clean)

    def _worker():
        try:
            base_dir = ""
            try:
                if hasattr(gui, "entry_dest") and gui.entry_dest.get().strip():
                    base_dir = os.path.dirname(gui.entry_dest.get().strip())
            except Exception:
                pass
            if not base_dir or not os.path.isdir(base_dir):
                try:
                    from faqih_downloader.config import get_base_downloads_dir
                    base_dir = get_base_downloads_dir()
                except Exception:
                    base_dir = os.path.expanduser("~/Downloads")

            conn_count = 8
            try:
                if hasattr(gui, "conn_var"):
                    conn_count = int(gui.conn_var.get())
            except Exception:
                pass

            speed_limit = 0.0
            try:
                if hasattr(gui, "entry_custom_speed"):
                    kb = float(gui.entry_custom_speed.get().strip())
                    speed_limit = kb * 1024.0 if kb > 0 else 0.0
            except Exception:
                pass

            if is_media:
                _probe_media_worker(gui, url_clean, base_dir, conn_count, speed_limit)
            else:
                _probe_file_worker(gui, url_clean, base_dir, conn_count, speed_limit)
        finally:
            if is_media and hasattr(gui, "remove_parsing_link"):
                gui.remove_parsing_link(url_clean)

    threading.Thread(target=_worker, daemon=True).start()


__all__ = [
    "stage_media_option_in_col1",
    "_start_staged_download",
    "_probe_media_worker",
    "_probe_file_worker",
    "probe_and_stage_pasted_url",
]
