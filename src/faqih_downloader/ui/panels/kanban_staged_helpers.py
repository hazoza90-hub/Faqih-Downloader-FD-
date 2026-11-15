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

from faqih_downloader.locales.i18n import tr
from faqih_downloader.utils.url_utils import derive_download_filename
from faqih_downloader.utils.file_ops import get_file_category_and_icon, resolve_categorized_path
from faqih_downloader.utils.window_effects import RoundedGlassCard
from faqih_downloader.ui.panels.kanban_cards import _truncate_title
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
    category = info.get("category", "")
    is_media = bool(info.get("media_context") or str(category).lower() in ("video", "audio") or info.get("selected_opt"))
    if is_media and "quality" in callbacks:
        menu.add_command(label=tr("staged_btn_quality", "⚙ Quality & Dub"), command=lambda: callbacks.get("quality", lambda i: None)(info))
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
    if tk is None:
        return None
    file_name = info.get("file_name") or derive_download_filename(info.get("url", "")) or "download.bin"
    file_size = int(info.get("file_size") or 0)
    category = info.get("category") or "file"
    badge = info.get("badge") or os.path.splitext(file_name)[1].upper().lstrip(".") or "LINK"
    supports_resume = info.get("supports_resume", True)
    final_dest = info.get("final_dest") or ""

    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
    pad_side = tk.RIGHT if is_ar else tk.LEFT
    opp_side = tk.LEFT if is_ar else tk.RIGHT
    is_media = bool(info.get("media_context") or str(category).lower() in ("video", "audio") or info.get("selected_opt"))

    card_h = 228 if is_media else 156
    card = RoundedGlassCard(
        parent, radius=12, bg="#0b0e14", card_bg="#151a24", border_color="#283548",
        height=card_h, inner_padx=12, inner_pady=10
    )
    card.pack(fill=tk.X, pady=(0, 10))

    # Top Row: Filename + Badge (pack badge first so filename never collides or clips)
    top_row = tk.Frame(card.inner, bg="#151a24"); top_row.pack(fill=tk.X)
    has_ar_fn = any('\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\u08A0' <= ch <= '\u08FF' for ch in str(file_name))
    tk.Label(top_row, text=badge, font=("Segoe UI", 8, "bold"), bg="#0284c7", fg="#ffffff", padx=6, pady=1).pack(side=opp_side, padx=(6, 0) if not is_ar else (0, 6))
    tk.Label(
        top_row,
        text=_truncate_title(file_name, 24 if has_ar_fn else 28),
        font=("Segoe UI", 9, "bold"),
        bg="#151a24",
        fg="#f8fafc",
        anchor="e" if has_ar_fn else "w",
    ).pack(side=pad_side, fill=tk.X, expand=True)

    # Second Row: Format / Audio / Subtitle / Size Details (dedicated full-width row to avoid overlap)
    meta_row = tk.Frame(card.inner, bg="#151a24"); meta_row.pack(fill=tk.X, pady=(3, 0))
    if is_media:
        opt = info.get("selected_opt")
        if not opt and isinstance(info.get("media_context"), dict):
            opt = info["media_context"].get("selected_option") or info["media_context"].get("selected_opt")
        audio_lbl, sub_lbl = "", ""
        at = getattr(opt, "selected_audio_track", None) if opt else None
        if not at and isinstance(info.get("media_context"), dict):
            at = info["media_context"].get("selected_audio_track")
        if isinstance(at, dict):
            a_name = at.get("language_label") or at.get("label") or at.get("language", "")
            audio_lbl = a_name.split(" - ")[0].strip() if " - " in a_name else a_name.strip()
        st = getattr(opt, "selected_subtitle_track", None) if opt else None
        if not st and isinstance(info.get("media_context"), dict):
            st = info["media_context"].get("selected_subtitle_track")
        if isinstance(st, dict):
            s_name = st.get("language_label") or st.get("label") or st.get("language", "")
            sub_lbl = s_name.split(" - ")[0].strip() if " - " in s_name else s_name.strip()
            sub_mode = getattr(opt, "subtitle_embed_mode", "") if opt else (info.get("media_context", {}).get("subtitle_embed_mode", ""))
            if sub_mode == "hard_burn":
                sub_lbl += " (Burn)"
        q_summary = getattr(opt, "resolution_label", "") or getattr(opt, "format_note", "") or badge or "Video"
        a_summary = f"🔊 {audio_lbl}" if audio_lbl else ("🔊 " + tr("media_opt_audio_default", "الصوت الافتراضي" if is_ar else "Default Audio"))
        s_summary = f"💬 {sub_lbl}" if sub_lbl else ("💬 " + tr("sub_none", "بدون ترجمة" if is_ar else "No Sub"))
        parts = [q_summary, a_summary, s_summary]
        ext_subs = getattr(opt, "external_subtitle_tracks", None) if opt else None
        if not ext_subs and isinstance(info.get("media_context"), dict):
            ext_subs = info["media_context"].get("external_subtitle_tracks")
        if ext_subs:
            ext_codes = []
            for et in ext_subs:
                if isinstance(et, dict) and str(et.get("sub_id") or "").lower() != "none":
                    c = str(et.get("language") or et.get("sub_id") or "").split("-")[0].split("_")[0].upper()
                    if c and c not in ext_codes:
                        ext_codes.append(c)
            if ext_codes:
                parts.append(f"❏ SRT: {', '.join(ext_codes)}")
        if file_size > 0:
            parts.append(_format_size(file_size))
        desc_txt = " • ".join(parts)
        tk.Label(
            meta_row,
            text=desc_txt,
            font=("Segoe UI", 8),
            bg="#151a24",
            fg="#38bdf8",
            anchor="e" if is_ar else "w",
            justify="right" if is_ar else "left",
            wraplength=260,
        ).pack(fill=tk.X)
    else:
        tk.Label(
            meta_row,
            text=f"{_format_size(file_size)}  •  {str(category).capitalize()}",
            font=("Segoe UI", 8),
            bg="#151a24",
            fg="#94a3b8",
            anchor="e" if is_ar else "w",
        ).pack(fill=tk.X)

    # Row 2b: Resume status separated cleanly onto its own row
    resume_row = tk.Frame(card.inner, bg="#151a24"); resume_row.pack(fill=tk.X, pady=(2, 0))
    res_txt = tr("info_resumable", "✓ Resumable") if supports_resume else tr("info_not_resumable", "✕ Non-resumable")
    tk.Label(
        resume_row,
        text=res_txt,
        font=("Segoe UI", 8),
        bg="#151a24",
        fg=("#22c55e" if supports_resume else "#ef4444"),
        anchor="e" if is_ar else "w",
    ).pack(fill=tk.X)

    # Third Row: Destination Path
    path_row = tk.Frame(card.inner, bg="#151a24"); path_row.pack(fill=tk.X, pady=(2, 0))
    tk.Label(path_row, text=f"📁 {_truncate_title(final_dest, 34) if final_dest else '—'}", font=("Segoe UI", 7), bg="#151a24", fg="#64748b", anchor="e" if is_ar else "w").pack(fill=tk.X)

    # Fourth Row: Dedicated Quality & Dubbing Button (for Media) - packed above btn_row
    q_row = None
    if is_media and "quality" in callbacks:
        q_row = tk.Frame(card.inner, bg="#151a24")
        tk.Button(
            q_row, text=tr("staged_btn_quality", "⚙ الجودة والدبلجة والترجمة" if is_ar else "⚙ Quality, Dubbing & Subtitles"),
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b", fg="#38bdf8", activebackground="#0284c7", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
            command=lambda: callbacks.get("quality", lambda i: None)(info)
        ).pack(fill=tk.X)

    # Fifth Row: Action Buttons (packed with side=BOTTOM first so multi-line text never clips them)
    btn_row = tk.Frame(card.inner, bg="#151a24"); btn_row.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
    tk.Button(
        btn_row, text=tr("staged_btn_start", "▶ Start Download"), font=("Segoe UI", 8, "bold"),
        bg="#059669", fg="#ffffff", activebackground="#047857", activeforeground="#ffffff",
        relief="flat", bd=0, cursor="hand2", padx=10, pady=4,
        command=lambda: callbacks.get("start", lambda i: None)(info)
    ).pack(side=pad_side, padx=(0, 6) if not is_ar else (6, 0))

    if not is_media and "quality" in callbacks:
        tk.Button(
            btn_row, text=tr("staged_btn_quality", "⚙ Quality & Dub"), font=("Segoe UI", 8, "bold"),
            bg="#1e293b", fg="#38bdf8", activebackground="#0284c7", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
            command=lambda: callbacks.get("quality", lambda i: None)(info)
        ).pack(side=pad_side, padx=(0, 6) if not is_ar else (6, 0))

    tk.Button(
        btn_row, text=tr("staged_btn_info", "ℹ Info"), font=("Segoe UI", 8, "bold"),
        bg="#1e293b", fg="#94a3b8", activebackground="#0284c7", activeforeground="#ffffff",
        relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
        command=lambda: callbacks.get("info", lambda i: None)(info)
    ).pack(side=pad_side, padx=(0, 6) if not is_ar else (6, 0))
    tk.Button(
        btn_row, text="✕", font=("Segoe UI", 8, "bold"), bg="#1e293b", fg="#94a3b8",
        activebackground="#ef4444", activeforeground="#ffffff", relief="flat", bd=0, cursor="hand2",
        padx=8, pady=4, command=lambda: callbacks.get("remove", lambda i: None)(info)
    ).pack(side=opp_side)

    if q_row is not None:
        q_row.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

    try:
        card.inner.update_idletasks()
        req_h = max(card_h, int(card.inner.winfo_reqheight() or 0) + 22)
        if req_h != card_h:
            card.configure(height=req_h)
            if hasattr(card, "_last_size"):
                card._last_size = None
            if hasattr(card, "_on_resize"):
                card._on_resize()
    except Exception:
        pass

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
    if tk is None:
        return
    from faqih_downloader.ui.modals.file_info_modal import open_file_info_modal

    def _on_info(info: Dict[str, Any]):
        open_file_info_modal(gui.root if hasattr(gui, "root") else container, item_data=info)

    def _on_remove(info: Dict[str, Any]):
        url = info.get("url", "")
        if hasattr(gui, "remove_staged_link"):
            gui.remove_staged_link(url)

    def _on_quality(info: Dict[str, Any]):
        url = info.get("url", "")
        dest = info.get("final_dest", "")
        end_val = tk.END if tk else "end"
        if hasattr(gui, "entry_url") and gui.entry_url and url:
            gui.entry_url.delete(0, end_val); gui.entry_url.insert(0, url)
        if hasattr(gui, "entry_dest") and gui.entry_dest and dest:
            gui.entry_dest.delete(0, end_val); gui.entry_dest.insert(0, dest)
        ext_tracks = None
        for src in (
            info.get("external_subtitle_tracks"),
            info["media_context"].get("external_subtitle_tracks") if isinstance(info.get("media_context"), dict) else None,
            getattr(info.get("selected_opt"), "external_subtitle_tracks", None),
        ):
            if src is not None:
                ext_tracks = [dict(t) for t in src if isinstance(t, dict)]
                if ext_tracks:
                    break
        if not ext_tracks and isinstance(getattr(gui, "_pending_media_context", None), dict) and gui._pending_media_context.get("url") == url:
            cur_ext = gui._pending_media_context.get("external_subtitle_tracks")
            if isinstance(cur_ext, list) and cur_ext:
                ext_tracks = [dict(t) for t in cur_ext if isinstance(t, dict)]
        if ext_tracks is None:
            ext_tracks = []
        if info.get("media_context"):
            gui._pending_media_context = dict(info["media_context"])
        elif info.get("selected_opt") is not None:
            gui._pending_media_context = {
                "url": url,
                "info": info.get("stream_info") if isinstance(info.get("stream_info"), dict) else {},
                "selected_option": info.get("selected_opt"),
                "selected_opt": info.get("selected_opt"),
                "final_dest": dest,
            }
        ctx = getattr(gui, "_pending_media_context", None)
        if isinstance(ctx, dict):
            if info.get("selected_opt") is not None:
                ctx["selected_option"] = info.get("selected_opt")
                ctx["selected_opt"] = info.get("selected_opt")
            ctx["external_subtitle_tracks"] = [dict(t) for t in ext_tracks]
            for opt_item in (ctx.get("options") or []):
                try:
                    opt_item.external_subtitle_tracks = [dict(t) for t in ext_tracks]
                except Exception:
                    pass
            sel_item = ctx.get("selected_option") or ctx.get("selected_opt")
            if sel_item is not None:
                try:
                    sel_item.external_subtitle_tracks = [dict(t) for t in ext_tracks]
                except Exception:
                    pass
        gui._main_external_subtitle_tracks = [dict(t) for t in ext_tracks]
        if hasattr(gui, "populate_main_media_bar") and ctx and ctx.get("options"):
            gui.populate_main_media_bar(
                ctx.get("info"), ctx.get("options"), ctx.get("audio_tracks", []),
                ctx.get("subtitle_tracks", []), selected_option=ctx.get("selected_option"),
                url=url, dest=dest, external_subtitle_tracks=ext_tracks
            )
        if hasattr(gui, "_reopen_media_quality_modal"):
            gui._reopen_media_quality_modal()

    callbacks = {
        "start": lambda item: getattr(sys.modules.get("faqih_downloader.ui.panels.kanban_staged_helpers"), "_start_staged_download", _start_staged_download)(gui, item),
        "quality": _on_quality,
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
    if tk is None:
        return
    from faqih_downloader.ui.panels.kanban_cards import build_queued_card

    # 1. Parsing links
    for url in parsing:
        build_queued_card(
            container,
            url=url,
            badge=tr("badge_parsing", "PARSING"),
            badge_bg="#b45309",
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
