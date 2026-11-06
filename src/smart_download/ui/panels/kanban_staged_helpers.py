"""
kanban_staged_helpers.py: Staged Link Card builder, context menu, and URL probing
for Column 1 (Queued & Parsing / Staged Links) in Faqih Downloader (FD) v2.0.2.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from smart_download.locales.i18n import tr
from smart_download.utils.url_utils import derive_download_filename
from smart_download.utils.file_ops import get_file_category_and_icon, resolve_categorized_path
from smart_download.utils.window_effects import RoundedGlassCard
from smart_download.ui.panels.kanban_cards import _truncate_title
from .kanban_staged_prober import (
    stage_media_option_in_col1,
    _start_staged_download,
    _probe_media_worker,
    _probe_file_worker,
    probe_and_stage_pasted_url,
)


def _format_size(size_bytes: int) -> str:
    """Formats raw bytes into human-readable unit string."""
    if size_bytes <= 0:
        return "—"
    s = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024:
            return f"{s:.1f} {unit}" if unit != "B" else f"{int(s)} B"
        s /= 1024.0
    return f"{s:.1f} PB"


def show_staged_context_menu(event: Any, info: Dict[str, Any], root: Any, callbacks: Dict[str, Callable]) -> None:
    """Renders dark context menu for a staged link card."""
    if tk is None: return
    menu = tk.Menu(root, tearoff=0, bg="#151a24", fg="#f8fafc", activebackground="#19f3ee", activeforeground="#0b0e14", activeborderwidth=0, bd=1, relief="flat", font=("Segoe UI", 9))
    url = info.get("url", "")
    menu.add_command(label=tr("staged_btn_start", "▶ Start Download"), command=lambda: callbacks.get("start", lambda i: None)(info))
    menu.add_command(label=tr("ctx_file_info", "ℹ File & Link Info"), command=lambda: callbacks.get("info", lambda i: None)(info))
    def _copy_url():
        if url and root:
            try: root.clipboard_clear(); root.clipboard_append(url)
            except Exception: pass
    menu.add_command(label=tr("menu_copy_url", "⎘ Copy URL"), command=_copy_url)
    menu.add_separator(background="#263043")
    menu.add_command(label=tr("staged_btn_remove", "✕ Remove"), command=lambda: callbacks.get("remove", lambda i: None)(info))
    try: menu.tk_popup(event.x_root, event.y_root)
    finally:
        try: menu.grab_release()
        except Exception: pass


def build_staged_link_card(parent: Any, info: Dict[str, Any], callbacks: Dict[str, Callable]) -> Any:
    """Builds a rounded glass Canvas card for a staged/probed link in Column 1."""
    file_name = info.get("file_name") or derive_download_filename(info.get("url", "")) or "download.bin"
    file_size = int(info.get("file_size") or 0)
    category = info.get("category") or "file"
    badge = info.get("badge") or os.path.splitext(file_name)[1].upper().lstrip(".") or "LINK"
    supports_resume = info.get("supports_resume", True)
    final_dest = info.get("final_dest") or ""

    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
    pad_side = tk.RIGHT if is_ar else tk.LEFT
    opp_side = tk.LEFT if is_ar else tk.RIGHT

    card = RoundedGlassCard(
        parent, radius=12, bg="#0b0e14", card_bg="#151a24", border_color="#283548",
        height=134, inner_padx=12, inner_pady=10
    )
    card.pack(fill=tk.X, pady=(0, 10))

    # Top Row: Filename + Badge
    top_row = tk.Frame(card.inner, bg="#151a24"); top_row.pack(fill=tk.X)
    tk.Label(top_row, text=_truncate_title(file_name, 28), font=("Segoe UI", 9, "bold"), bg="#151a24", fg="#f8fafc").pack(side=pad_side)
    tk.Label(top_row, text=badge, font=("Segoe UI", 8, "bold"), bg="#0284c7", fg="#ffffff", padx=6, pady=1).pack(side=opp_side)

    # Second Row: Size, Category, Resume
    meta_row = tk.Frame(card.inner, bg="#151a24"); meta_row.pack(fill=tk.X, pady=(3, 0))
    tk.Label(meta_row, text=f"{_format_size(file_size)}  •  {str(category).capitalize()}", font=("Segoe UI", 8), bg="#151a24", fg="#94a3b8").pack(side=pad_side)
    res_txt = tr("info_resumable", "✓ Resumable") if supports_resume else tr("info_not_resumable", "✕ Non-resumable")
    tk.Label(meta_row, text=res_txt, font=("Segoe UI", 8), bg="#151a24", fg=("#22c55e" if supports_resume else "#ef4444")).pack(side=opp_side)

    # Third Row: Destination Path
    path_row = tk.Frame(card.inner, bg="#151a24"); path_row.pack(fill=tk.X, pady=(2, 0))
    tk.Label(path_row, text=f"📁 {_truncate_title(final_dest, 36) if final_dest else '—'}", font=("Segoe UI", 7), bg="#151a24", fg="#64748b").pack(side=pad_side)

    # Fourth Row: Action Buttons
    btn_row = tk.Frame(card.inner, bg="#151a24"); btn_row.pack(fill=tk.X, pady=(6, 0))
    tk.Button(
        btn_row, text=tr("staged_btn_start", "▶ Start Download"), font=("Segoe UI", 8, "bold"),
        bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
        relief="flat", bd=0, cursor="hand2", padx=10, pady=3,
        command=lambda: callbacks.get("start", lambda i: None)(info)
    ).pack(side=pad_side, padx=(0, 6) if not is_ar else (6, 0))
    tk.Button(
        btn_row, text=tr("staged_btn_info", "ℹ Info"), font=("Segoe UI", 8, "bold"),
        bg="#1e293b", fg="#38bdf8", activebackground="#0284c7", activeforeground="#ffffff",
        relief="flat", bd=0, cursor="hand2", padx=8, pady=3,
        command=lambda: callbacks.get("info", lambda i: None)(info)
    ).pack(side=pad_side, padx=(0, 6) if not is_ar else (6, 0))
    tk.Button(
        btn_row, text="✕", font=("Segoe UI", 8, "bold"), bg="#1e293b", fg="#94a3b8",
        activebackground="#ef4444", activeforeground="#ffffff", relief="flat", bd=0, cursor="hand2",
        padx=8, pady=3, command=lambda: callbacks.get("remove", lambda i: None)(info)
    ).pack(side=opp_side)

    # Context Menu Binding
    def _popup(e): show_staged_context_menu(e, info, parent.winfo_toplevel(), callbacks)
    def _bind_all(w):
        w.bind("<Button-3>", _popup)
        for child in w.winfo_children(): _bind_all(child)
    card.bind("<Button-3>", _popup)
    _bind_all(card.inner)
    return card


def render_col1_staged_cards(
    container: Any,
    gui: Any,
    staged_links: List[Dict[str, Any]]
) -> None:
    """Builds and packs all staged link cards into container."""
    from smart_download.ui.modals.file_info_modal import open_file_info_modal

    def _on_info(info: Dict[str, Any]):
        open_file_info_modal(gui.root if hasattr(gui, "root") else container, item_data=info)

    def _on_remove(info: Dict[str, Any]):
        url = info.get("url", "")
        if hasattr(gui, "remove_staged_link"):
            gui.remove_staged_link(url)

    callbacks = {
        "start": lambda item: getattr(sys.modules.get("smart_download.ui.panels.kanban_staged_helpers"), "_start_staged_download", _start_staged_download)(gui, item),
        "info": _on_info,
        "remove": _on_remove
    }

    for item in staged_links:
        build_staged_link_card(container, item, callbacks)


def render_kanban_col1_content(
    container: Any,
    gui: Any,
    parsing: List[str],
    staged: List[Dict[str, Any]],
    queued: List[Any]
) -> None:
    """Renders active parsing tasks, staged links, and queued downloads in Column 1."""
    from smart_download.ui.panels.kanban_cards import build_queued_card

    # 1. Parsing links
    for url in parsing:
        build_queued_card(
            container,
            url=url,
            badge="PARSING",
            badge_bg="#d4a12a",
            status_text=tr("parsing_metadata", "Parsing video metadata..."),
            is_active=True
        )

    # 2. Staged links
    if staged:
        render_col1_staged_cards(container, gui, staged)

    # 3. Queued links
    q_meta_map = getattr(gui, "_queued_metadata", {})
    for task in queued:
        if callable(task):
            q_url = getattr(task, "url", "Queued Media Stream")
        elif isinstance(task, (list, tuple)) and len(task) > 0:
            q_url = str(task[0])
        else:
            q_url = str(task)
        meta = q_meta_map.get(q_url, {})
        title = meta.get("title", "")
        badge = meta.get("badge", "")
        if not title and isinstance(task, (list, tuple)) and len(task) > 1:
            title = os.path.basename(str(task[1]))
        if not badge and isinstance(task, (list, tuple)) and len(task) > 1:
            badge = os.path.splitext(str(task[1]))[1].upper().lstrip(".")
        badge = badge or "QUEUED"
        badge_bg = meta.get("badge_bg", "#2563eb")
        build_queued_card(
            container,
            url=q_url,
            badge=badge,
            badge_bg=badge_bg,
            status_text=tr("pending_queue", "Pending queue..."),
            is_active=False,
            title=title
        )


__all__ = [
    "probe_and_stage_pasted_url",
    "stage_media_option_in_col1",
    "_start_staged_download",
    "_probe_media_worker",
    "_probe_file_worker",
    "show_staged_context_menu",
    "build_staged_link_card",
    "render_col1_staged_cards",
    "render_kanban_col1_content"
]
