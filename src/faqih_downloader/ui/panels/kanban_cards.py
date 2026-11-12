"""
Kanban Card Widgets and Rounded Glass Builders for Smart Download (SD) v2.0.2.
Provides authentic rounded glass Canvas cards for:
- Column 1: Queued & Parsing cards and Empty State.
- Column 2: Active Turbo Stream card and Engine Ready Idle State.
- Column 3: Completed Vault item cards (Video, Audio, Archive, Document) and Empty State.
"""
from __future__ import annotations

import os
import hashlib
import threading
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_config_dir
from faqih_downloader.utils.window_effects import draw_rounded_rect, draw_glow_border, RoundedGlassCard
from faqih_downloader.ui.components.led_matrix import LedEqualizerMatrix
from faqih_downloader.ui.components.arc_spinner import ArcSpinnerCanvas
from faqih_downloader.ui.components.waveform_visualizer import WaveformVisualizerCanvas
from .kanban_card_graphics import (
    _THUMB_SEMAPHORE,
    _THUMB_EXTRACT_SEMAPHORE,
    _VIDEO_THUMB_CACHE,
    _draw_video_play_overlay,
    _draw_default_video_thumbnail,
    _draw_deleted_video_placeholder,
    _extract_and_load_video_thumbnail,
    _draw_video_thumbnail,
    _draw_archive_box,
    _draw_doc_icon,
    _draw_generic_file_icon,
    draw_neon_progress_bar,
)


def _truncate_title(filename: str, max_len: int = 28) -> str:
    """Truncates long titles safely without inverting Arabic ellipsis or breaking BiDi layout."""
    if not filename or len(filename) <= max_len:
        return filename
    is_rtl = any('\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\u08A0' <= ch <= '\u08FF' for ch in filename)
    truncated = filename[:max_len - 1]
    if is_rtl:
        return f"\u200F{truncated}…\u200F"
    return f"{truncated}…"


def create_empty_state(
    parent: Any,
    icon: str,
    title: str,
    subtitle: str = "",
    bg: str = "#0b0e14",
    card_bg: str = "#151a24",
    border_color: str = "#233042",
    glow_color: Optional[str] = None,
    height: int = 150,
) -> tk.Canvas:
    """
    Renders an elegant rounded frosted glass Empty State card on a Canvas.
    """
    cv = tk.Canvas(parent, bg=bg, height=height, bd=0, highlightthickness=0)
    cv.pack(fill=tk.X, pady=(4, 6))
    cv._last_size = None
    cv._redraw_job = None

    def _flush_draw():
        cv._redraw_job = None
        if not getattr(cv, "winfo_exists", lambda: False)():
            return
        _render()

    def _render():
        w = max(100, cv._last_size[0] if cv._last_size else cv.winfo_width())
        h = max(60, cv._last_size[1] if cv._last_size else cv.winfo_height())
        cv.delete("all")

        # Rounded Glass Card background
        if glow_color:
            draw_glow_border(cv, 3, 3, w - 3, h - 3, radius=12, glow_color=glow_color, inner_fill=card_bg, tags="bg")
        else:
            draw_rounded_rect(cv, 2, 2, w - 2, h - 2, radius=12, fill=card_bg, outline=border_color, width=1, tags="bg")

        # Icon
        cy = h // 2 - (14 if subtitle else 0)
        cv.create_text(w // 2, cy - 18, text=icon, font=("Segoe UI", 20), fill="#475569")
        # Title text
        cv.create_text(w // 2, cy + 10, text=title, font=("Segoe UI", 9, "bold"), fill="#94a3b8")
        # Subtitle text (increased vertical distance to 26px to prevent Arabic font collision)
        if subtitle:
            cv.create_text(w // 2, cy + 36, text=subtitle, font=("Segoe UI", 8), fill="#64748b")

    def _draw(event=None):
        if not getattr(cv, "winfo_exists", lambda: False)():
            return
        w = event.width if (event and getattr(event, "width", 0) > 10) else cv.winfo_width()
        h = event.height if (event and getattr(event, "height", 0) > 10) else cv.winfo_height()
        if (w, h) == getattr(cv, "_last_size", None):
            return
        cv._last_size = (w, h)

        top = None
        try: top = cv.winfo_toplevel()
        except Exception: pass
        if top and getattr(top, "_is_resizing_window", False):
            if getattr(cv, "_redraw_job", None) is None:
                cv._redraw_job = cv.after(16, _flush_draw)
        else:
            if getattr(cv, "_redraw_job", None) is not None:
                try: cv.after_cancel(cv._redraw_job)
                except Exception: pass
                cv._redraw_job = None
            _render()

    cv.bind("<Configure>", _draw)
    return cv


def build_queued_card(
    parent: Any,
    url: str,
    badge: str = "PARSING",
    badge_bg: str = "#d4a12a",
    status_text: str = "",
    is_active: bool = True,
    title: str = "",
) -> Any:
    """
    Builds a real rounded frosted glass Canvas card for a queued or parsing URL in Column 1.
    """
    card = RoundedGlassCard(
        parent,
        radius=12,
        bg="#0b0e14",
        card_bg="#151a24",
        border_color="#283548",
        height=125 if title else 115,
        inner_padx=12,
        inner_pady=10,
    )
    card.pack(fill=tk.X, pady=(0, 10))

    # Top row: Title / URL + Badge inside card.inner
    top_row = tk.Frame(card.inner, bg="#151a24")
    top_row.pack(fill=tk.X)

    if title:
        clean_title = title if len(title) <= 28 else (title[:25] + "...")
        lbl_head = tk.Label(top_row, text=clean_title, font=("Segoe UI", 8, "bold"), bg="#151a24", fg="#f8fafc")
    else:
        clean_url = url if len(url) <= 30 else (url[:27] + "...")
        lbl_head = tk.Label(top_row, text=clean_url, font=("Segoe UI", 8), bg="#151a24", fg="#94a3b8")
    lbl_head.pack(side=tk.LEFT)

    lbl_badge = tk.Label(
        top_row,
        text=badge,
        font=("Segoe UI", 8, "bold"),
        bg=badge_bg,
        fg="#ffffff",
        padx=6,
        pady=1
    )
    lbl_badge.pack(side=tk.RIGHT)

    if title:
        clean_sub = url if len(url) <= 34 else (url[:31] + "...")
        lbl_sub = tk.Label(card.inner, text=clean_sub, font=("Segoe UI", 7), bg="#151a24", fg="#64748b", anchor="w")
        lbl_sub.pack(fill=tk.X, pady=(1, 0))

    # Middle: Arc Spinner
    spin_box = tk.Frame(card.inner, bg="#151a24")
    spin_box.pack(pady=(6 if title else 10, 6 if title else 8))
    mode = "active" if is_active else "dim"
    spinner = ArcSpinnerCanvas(spin_box, size=36, bg="#151a24", mode=mode)
    spinner.pack()

    # Bottom: Status
    lbl_status = tk.Label(
        card.inner,
        text=status_text or tr("parsing_metadata", "Parsing video metadata..."),
        font=("Segoe UI", 8),
        bg="#151a24",
        fg="#64748b"
    )
    lbl_status.pack()

    card._spinner = spinner
    card._status = lbl_status
    return card


def build_vault_card(
    parent: Any,
    entry: Dict[str, Any],
    on_open_file: Callable[[str], None],
    on_open_folder: Callable[[str], None],
    on_delete_entry: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_context_menu: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
) -> Any:
    """
    Builds a dynamic completed vault card with rounded glass styling and tailored visuals.
    """
    filename = entry.get("filename") or "download.bin"
    file_path = entry.get("file_path") or ""
    size_bytes = entry.get("size_bytes", 0)

    # Human-readable size
    if size_bytes >= 1024**3:
        sz_str = f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        sz_str = f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        sz_str = f"{size_bytes / 1024:.1f} KB"
    elif size_bytes > 0:
        sz_str = f"{size_bytes} B"
    else:
        sz_str = ""

    ext = os.path.splitext(filename)[1].lower()
    card_h = 124 if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv") else 110

    card = RoundedGlassCard(
        parent,
        radius=12,
        bg="#0b0e14",
        card_bg="#151a24",
        border_color="#283548",
        height=card_h,
        inner_padx=12,
        inner_pady=10,
    )
    card.pack(fill=tk.X, pady=(0, 8))

    # Top row: Checkmark + Filename + Size inside card.inner
    top = tk.Frame(card.inner, bg="#151a24")
    top.pack(fill=tk.X, pady=(0, 4))

    lbl_chk = tk.Label(top, text="✔", font=("Segoe UI", 9, "bold"), bg="#151a24", fg="#22c55e")
    lbl_chk.pack(side=tk.LEFT, padx=(0, 6))

    if on_delete_entry:
        btn_del = tk.Label(top, text="✕", font=("Segoe UI", 8, "bold"), bg="#151a24", fg="#64748b", cursor="hand2")
        btn_del.pack(side=tk.RIGHT, padx=(4, 0))
        btn_del.bind("<Enter>", lambda e: btn_del.configure(fg="#ef4444"))
        btn_del.bind("<Leave>", lambda e: btn_del.configure(fg="#64748b"))
        btn_del.bind("<Button-1>", lambda e: on_delete_entry(entry))

    info = tk.Frame(top, bg="#151a24")
    info.pack(side=tk.LEFT, fill=tk.X, expand=True)

    clean_title = _truncate_title(filename, max_len=38)
    lbl_fn = tk.Label(
        info,
        text=clean_title,
        font=("Segoe UI", 9, "bold"),
        bg="#151a24",
        fg="#f8fafc",
        anchor="w"
    )
    lbl_fn.pack(anchor="w")

    if sz_str:
        lbl_sz = tk.Label(info, text=sz_str, font=("Segoe UI", 8), bg="#151a24", fg="#64748b", anchor="w")
        lbl_sz.pack(anchor="w")

    # Bottom row / visual row
    bot = tk.Frame(card.inner, bg="#151a24")
    bot.pack(fill=tk.X, pady=(4, 0))

    target_ref = file_path if file_path else filename

    # Media preview dispatcher
    if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"):
        # Video preview thumbnail (width=116, height=52)
        thumb = tk.Canvas(bot, width=116, height=52, bg="#1a2e22", bd=0, highlightthickness=0, cursor="hand2")
        thumb.pack(side=tk.LEFT)
        _draw_video_thumbnail(thumb, target_ref)
        thumb.bind("<Button-1>", lambda e: on_open_file(target_ref))
    elif ext in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg", ".opus"):
        # Audio waveform
        wave = WaveformVisualizerCanvas(bot, height=36, bg="#151a24")
        wave.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        if wave.canvas:
            wave.canvas.configure(cursor="hand2")
            wave.canvas.bind("<Button-1>", lambda e: on_open_file(target_ref))
    elif ext in (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".iso"):
        # Isometric archive package
        cv_box = tk.Canvas(bot, width=44, height=38, bg="#151a24", bd=0, highlightthickness=0, cursor="hand2")
        cv_box.pack(side=tk.LEFT, padx=(2, 0))
        _draw_archive_box(cv_box)
        cv_box.bind("<Button-1>", lambda e: on_open_file(target_ref))
    elif ext in (".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".epub"):
        # PDF / Document icon
        cv_doc = tk.Canvas(bot, width=40, height=38, bg="#151a24", bd=0, highlightthickness=0, cursor="hand2")
        cv_doc.pack(side=tk.LEFT, padx=(2, 0))
        _draw_doc_icon(cv_doc, is_pdf=(ext == ".pdf"))
        cv_doc.bind("<Button-1>", lambda e: on_open_file(target_ref))
    else:
        # General file icon
        cv_gen = tk.Canvas(bot, width=40, height=38, bg="#151a24", bd=0, highlightthickness=0, cursor="hand2")
        cv_gen.pack(side=tk.LEFT, padx=(2, 0))
        _draw_generic_file_icon(cv_gen, ext.upper().lstrip(".") or "BIN")
        cv_gen.bind("<Button-1>", lambda e: on_open_file(target_ref))

    btn_open = tk.Button(
        bot,
        text=tr("btn_open_folder", "Open Folder"),
        font=("Segoe UI", 8, "bold"),
        bg="#252f42",
        fg="#cbd5e1",
        activebackground="#333d52",
        activeforeground="#19f3ee",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=10,
        pady=3,
        command=lambda: on_open_folder(target_ref)
    )
    btn_open.pack(side=tk.RIGHT, pady=(10 if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv") else 2))

    if on_context_menu:
        def _bind_ctx(w):
            w.bind("<Button-3>", lambda e: on_context_menu(e, entry), add="+")
            for ch in getattr(w, "winfo_children", lambda: [])():
                _bind_ctx(ch)
        _bind_ctx(card)
        if hasattr(card, "inner"):
            _bind_ctx(card.inner)

    return card


def build_active_card_shell(card: Any, parent_app: Any) -> Dict[str, Any]:
    """Constructs the active stream card inner widgets and returns widget dict."""
    row1 = tk.Frame(card, bg="#151a24")
    row1.pack(fill=tk.X, pady=(0, 4))

    lbl_fn = tk.Label(row1, text="", font=("Segoe UI", 9, "bold"), bg="#151a24", fg="#f8fafc")
    lbl_fn.pack(side=tk.LEFT)

    btn_menu = tk.Label(row1, text="•••", font=("Segoe UI", 10, "bold"), bg="#151a24", fg="#94a3b8", cursor="hand2")
    btn_menu.pack(side=tk.RIGHT)
    btn_menu.bind("<Button-1>", lambda e: parent_app._show_active_card_menu(btn_menu))

    row2 = tk.Frame(card, bg="#151a24")
    row2.pack(fill=tk.X, pady=(0, 6))

    lbl_pct = tk.Label(row2, text="0%", font=("Segoe UI", 9, "bold"), bg="#151a24", fg="#f8fafc", width=5, anchor="w")
    lbl_pct.pack(side=tk.LEFT)

    lbl_spd = tk.Label(row2, text="0.0 MB/s", font=("Segoe UI", 9, "bold"), bg="#151a24", fg="#38bdf8", anchor="e")
    lbl_spd.pack(side=tk.RIGHT)

    cv_prog = tk.Canvas(row2, width=40, height=6, bg="#1c2533", bd=0, highlightthickness=0)
    cv_prog.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

    row3 = tk.Frame(card, bg="#151a24")
    row3.pack(fill=tk.X, pady=(0, 6))

    lbl_size = tk.Label(row3, text="0.0 MB / 0.0 MB", font=("Segoe UI", 8, "bold"), bg="#151a24", fg="#cbd5e1", anchor="w")
    lbl_size.pack(side=tk.LEFT)

    lbl_eta = tk.Label(row3, text="", font=("Segoe UI", 8), bg="#151a24", fg="#94a3b8", anchor="e")
    lbl_eta.pack(side=tk.RIGHT)

    matrix = LedEqualizerMatrix(card, height=52, bg="#151a24")
    matrix.pack(fill=tk.X, pady=(2, 0))

    return {
        "lbl_filename": lbl_fn,
        "btn_menu": btn_menu,
        "lbl_pct": lbl_pct,
        "canvas_prog": cv_prog,
        "lbl_speed": lbl_spd,
        "lbl_size": lbl_size,
        "lbl_eta": lbl_eta,
        "matrix": matrix,
    }


__all__ = [
    "create_empty_state",
    "build_queued_card",
    "build_vault_card",
    "draw_neon_progress_bar",
    "build_active_card_shell",
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
]

