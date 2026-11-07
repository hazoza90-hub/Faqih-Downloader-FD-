"""
kanban_card_graphics.py: Thumbnail extraction, icon drawing, and progress bar graphics
for Kanban cards in Smart Download (SD).
"""
from __future__ import annotations

import os
import sys
import hashlib
import threading
import subprocess
from typing import Any, Dict, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_config_dir
from faqih_downloader.services.youtube_models import find_ffmpeg_bin
from faqih_downloader.utils.file_ops import resolve_existing_download_path

_THUMB_SEMAPHORE = threading.BoundedSemaphore(2)
_THUMB_EXTRACT_SEMAPHORE = _THUMB_SEMAPHORE
_VIDEO_THUMB_CACHE: Dict[str, Any] = {}


def _draw_video_play_overlay(canvas: tk.Canvas):
    """Draws a centered play circle and play triangle without clipping bottom pixels."""
    cx, cy = 58, 26
    canvas.create_oval(cx - 13, cy - 13, cx + 13, cy + 13, fill="#0f172a", outline="#19f3ee", width=1.5)
    canvas.create_polygon(
        cx - 4, cy - 6,
        cx - 4, cy + 6,
        cx + 6, cy,
        fill="#ffffff", outline=""
    )


def _draw_default_video_thumbnail(canvas: tk.Canvas):
    """Draws rich dark landscape placeholder thumbnail with play button overlay."""
    canvas.delete("all")
    w, h = 116, 52
    canvas.create_rectangle(0, 0, w, h // 2, fill="#233e28", outline="")
    canvas.create_rectangle(0, h // 2, w, h, fill="#182c1d", outline="")
    _draw_video_play_overlay(canvas)


def _draw_deleted_video_placeholder(canvas: tk.Canvas):
    """Draws clear placeholder on thumbnail when video file has been moved or deleted from disk."""
    canvas.delete("all")
    w, h = 116, 52
    canvas.create_rectangle(0, 0, w, h, fill="#1c1917", outline="#292524")
    cx, cy = w // 2, h // 2
    canvas.create_text(cx, cy - 8, text="⚠️", font=("Segoe UI", 11), fill="#f59e0b")
    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
    label = "الملف محذوف" if is_ar else "Moved"
    canvas.create_text(cx, cy + 10, text=label, font=("Segoe UI", 8, "bold"), fill="#a8a29e")


def _extract_and_load_video_thumbnail(canvas: tk.Canvas, video_path: Optional[str] = None):
    """
    Renders a video thumbnail on canvas. If video_path points to an existing video file,
    extracts a real video frame at 00:00:02 (or 00:00:00 fallback) in background via ffmpeg,
    caches it in thumbnails_cache, and displays it with a centered play overlay.
    """
    if not video_path:
        _draw_deleted_video_placeholder(canvas)
        return

    resolved = resolve_existing_download_path(video_path)
    target_file = resolved if (resolved and os.path.isfile(resolved)) else (video_path if os.path.isfile(video_path) else None)
    if not target_file:
        _draw_deleted_video_placeholder(canvas)
        return

    _draw_default_video_thumbnail(canvas)

    cache_dir = os.path.join(get_config_dir(), "thumbnails_cache")
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        pass

    try:
        mtime = os.path.getmtime(target_file)
        size = os.path.getsize(target_file)
        h_str = f"{target_file}_{mtime}_{size}"
    except Exception:
        h_str = target_file
    hash_key = hashlib.md5(h_str.encode("utf-8", errors="ignore")).hexdigest()
    thumb_path = os.path.join(cache_dir, f"{hash_key}.jpg")

    def _apply_thumb() -> bool:
        if not getattr(canvas, "winfo_exists", lambda: False)():
            return False
        try:
            from PIL import Image, ImageTk
            with Image.open(thumb_path) as im:
                resized = im.resize((116, 52), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas._photo = photo
            _draw_video_play_overlay(canvas)
            return True
        except Exception:
            try:
                if os.path.isfile(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass
            _draw_default_video_thumbnail(canvas)
            return False

    if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
        if _apply_thumb():
            return

    ffmpeg_bin = find_ffmpeg_bin()
    if not ffmpeg_bin:
        return

    mod = sys.modules.get("faqih_downloader.ui.panels.kanban_cards")
    semaphore = getattr(mod, "_THUMB_SEMAPHORE", _THUMB_SEMAPHORE)

    def _worker():
        try:
            with semaphore:
                flags = 0x08000000 if os.name == "nt" else 0
                cmd = [
                    ffmpeg_bin, "-y", "-ss", "00:00:02", "-i", target_file,
                    "-frames:v", "1",
                    "-vf", "scale=116:52:force_original_aspect_ratio=increase,crop=116:52",
                    "-q:v", "3", thumb_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
                if res.returncode != 0 or not os.path.isfile(thumb_path) or os.path.getsize(thumb_path) == 0:
                    cmd[3] = "00:00:00"
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)

                if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
                    try:
                        canvas.after(0, _apply_thumb)
                    except Exception:
                        pass
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True, name="VideoThumbExtract")
    t.start()


def _draw_video_thumbnail(canvas: tk.Canvas, video_path: Optional[str] = None):
    """Draws rich dark landscape thumbnail with circular play button."""
    _extract_and_load_video_thumbnail(canvas, video_path)


def _draw_archive_box(canvas: tk.Canvas):
    """Draws isometric cardboard archive box."""
    canvas.delete("all")
    canvas.create_polygon(5, 10, 20, 3, 35, 10, 20, 17, fill="#d97706", outline="#92400e")
    canvas.create_polygon(5, 10, 20, 17, 20, 31, 5, 24, fill="#b45309", outline="#78350f")
    canvas.create_polygon(20, 17, 35, 10, 35, 24, 20, 31, fill="#d97706", outline="#92400e")
    canvas.create_polygon(14, 7, 26, 7, 26, 14, 14, 14, fill="#fef08a", outline="")


def _draw_doc_icon(canvas: tk.Canvas, is_pdf: bool = True):
    """Draws realistic document icon with dog-ear fold and badge."""
    canvas.delete("all")
    canvas.create_polygon(6, 2, 24, 2, 32, 10, 32, 31, 6, 31, fill="#f8fafc", outline="#cbd5e1")
    canvas.create_polygon(24, 2, 24, 10, 32, 10, fill="#e2e8f0", outline="#94a3b8")
    badge_color = "#ef4444" if is_pdf else "#2563eb"
    label = "PDF" if is_pdf else "DOC"
    canvas.create_rectangle(6, 20, 32, 31, fill=badge_color, outline="")
    canvas.create_text(19, 25, text=label, font=("Segoe UI", 6, "bold"), fill="#ffffff")


def _draw_generic_file_icon(canvas: tk.Canvas, tag: str = "BIN"):
    """Draws generic file capsule with extension label."""
    canvas.delete("all")
    canvas.create_polygon(6, 2, 24, 2, 32, 10, 32, 31, 6, 31, fill="#1e293b", outline="#334155")
    canvas.create_polygon(24, 2, 24, 10, 32, 10, fill="#334155", outline="#475569")
    canvas.create_text(19, 22, text=tag[:4], font=("Segoe UI", 6, "bold"), fill="#38bdf8")


def draw_neon_progress_bar(canvas: tk.Canvas, ratio: float):
    """Draws glowing cyan progress line on canvas with sleek rounded caps."""
    if not canvas or not getattr(canvas, "winfo_exists", lambda: False)():
        return
    w = canvas.winfo_width()
    if w <= 10:
        w = 160
    h = 6
    canvas.delete("all")
    canvas.create_line(3, h / 2, max(4, w - 3), h / 2, fill="#1c2533", width=h, capstyle=tk.ROUND)
    fill_w = max(0.0, min(float(w), ratio * float(w)))
    if fill_w >= 6:
        canvas.create_line(3, h / 2, fill_w - 3, h / 2, fill="#19f3ee", width=h, capstyle=tk.ROUND)
    elif fill_w > 0:
        canvas.create_oval(1, 1, 5, 5, fill="#19f3ee", outline="")


__all__ = [
    "_THUMB_SEMAPHORE",
    "_THUMB_EXTRACT_SEMAPHORE",
    "_VIDEO_THUMB_CACHE",
    "_draw_video_play_overlay",
    "_draw_default_video_thumbnail",
    "_draw_deleted_video_placeholder",
    "_extract_and_load_video_thumbnail",
    "_draw_video_thumbnail",
    "_draw_archive_box",
    "_draw_doc_icon",
    "_draw_generic_file_icon",
    "draw_neon_progress_bar",
]
