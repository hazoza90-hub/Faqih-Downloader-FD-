"""
Completed Vault helpers: filtering pills, context menus, and pagination controls for Smart Download (SD).
"""
from __future__ import annotations

import os
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore
    messagebox = None  # type: ignore
from typing import Dict, List, Optional, Callable, Any

from faqih_downloader.locales.i18n import tr
from faqih_downloader.config import is_test_environment
from .kanban_vault_ops import (
    clear_completed_vault_entries,
    scan_unregistered_disk_files,
    restore_vault_entries_from_disk,
    open_vault_restore_dialog,
    delete_vault_entry_with_confirm,
)


VAULT_CATEGORIES = [
    ("all", "الكل", "All"),
    ("video", "▶ فيديو", "▶ Video"),
    ("audio", "♪ صوت", "♪ Audio"),
    ("archive", "▣ مضغوط", "▣ Archive"),
    ("docs", "▤ مستندات", "▤ Docs"),
]

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".ts")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus", ".wma")
ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tgz")
DOCS_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".epub", ".rtf")


def get_entry_category(entry: Dict[str, Any]) -> str:
    """Infers the category of a completed history entry from its filename extension or metadata."""
    fn = (entry.get("filename") or entry.get("title") or "").strip().lower()
    ext = os.path.splitext(fn)[1]
    if ext in VIDEO_EXTENSIONS or entry.get("category") == "video":
        return "video"
    if ext in AUDIO_EXTENSIONS or entry.get("category") == "audio":
        return "audio"
    if ext in ARCHIVE_EXTENSIONS or entry.get("category") == "archive":
        return "archive"
    if ext in DOCS_EXTENSIONS or entry.get("category") in ("document", "docs"):
        return "docs"
    return "other"


def filter_vault_entries(entries: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Filters history entries by selected category ('all', 'video', 'audio', 'archive', 'docs')."""
    cat = (category or "all").strip().lower()
    if cat == "all":
        return list(entries)
    return [e for e in entries if get_entry_category(e) == cat]


def build_vault_filter_pills(
    parent: Any,
    current_category: str,
    on_select: Callable[[str], None],
) -> tk.Frame:
    """Constructs a responsive horizontal row of category filter pills for Column 3."""
    row = tk.Frame(parent, bg="#0b0e14")
    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))

    for cat_id, label_ar, label_en in VAULT_CATEGORIES:
        is_active = (cat_id == current_category)
        lbl_text = label_ar if is_ar else label_en
        bg_col = "#19f3ee" if is_active else "#151a24"
        fg_col = "#0b0e14" if is_active else "#94a3b8"

        pill = tk.Label(
            row,
            text=lbl_text,
            font=("Segoe UI", 8, "bold" if is_active else "normal"),
            bg=bg_col,
            fg=fg_col,
            padx=4,
            pady=1,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground="#19f3ee" if is_active else "#263043",
        )
        pill.pack(side=tk.LEFT, padx=(0, 3), pady=(0, 6))

        def _make_handler(cid: str):
            return lambda e: on_select(cid)

        pill.bind("<Button-1>", _make_handler(cat_id))

    return row


def show_vault_context_menu(
    event: Any,
    entry: Dict[str, Any],
    root: Any,
    callbacks: Dict[str, Callable],
):
    """
    Renders an elegant dark themed context menu on right-click over a vault card.
    Supports Open File, Open Folder, Copy URL, Re-download, Remove, and Delete from Disk.
    """
    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))

    menu = tk.Menu(
        root,
        tearoff=0,
        bg="#151a24",
        fg="#f8fafc",
        activebackground="#19f3ee",
        activeforeground="#0b0e14",
        activeborderwidth=0,
        bd=1,
        relief="flat",
        font=("Segoe UI", 9)
    )

    file_path = entry.get("file_path") or ""
    source_url = entry.get("url") or ""

    # 1. Open File
    lbl_open = "▶ تشغيل الملف" if is_ar else "▶ Open File"
    menu.add_command(
        label=lbl_open,
        command=lambda: callbacks.get("open_file", lambda p: None)(file_path)
    )

    # 2. Open Containing Folder
    lbl_folder = "📁 فتح مجلد الملف" if is_ar else "📁 Open Containing Folder"
    menu.add_command(
        label=lbl_folder,
        command=lambda: callbacks.get("open_folder", lambda p: None)(file_path)
    )

    # 3. Copy Source URL
    lbl_copy = "🔗 نسخ الرابط الأصلي" if is_ar else "🔗 Copy Source URL"
    def _copy_url():
        if source_url and root:
            try:
                root.clipboard_clear()
                root.clipboard_append(source_url)
            except Exception:
                pass
    menu.add_command(label=lbl_copy, command=_copy_url)

    # 4. Re-download with Quality Selection
    lbl_redownload = "🔄 إعادة التحميل بجودة أخرى" if is_ar else "🔄 Re-download with Quality Selection"
    def _redownload():
        cb = callbacks.get("redownload")
        if callable(cb):
            cb(source_url)
    menu.add_command(label=lbl_redownload, command=_redownload)

    # 5. File & Link Info
    lbl_info = tr("ctx_file_info", "ℹ معلومات الملف والرابط" if is_ar else "ℹ File & Link Info")
    def _show_info():
        from faqih_downloader.ui.modals.file_info_modal import open_file_info_modal
        open_file_info_modal(root, item_data=entry)
    menu.add_command(label=lbl_info, command=_show_info)

    menu.add_separator(background="#263043")

    # 6. Remove from List only
    lbl_remove = "🗑 حذف من القائمة فقط" if is_ar else "🗑 Remove from List"
    menu.add_command(
        label=lbl_remove,
        command=lambda: callbacks.get("delete_entry", lambda e: None)(entry)
    )

    # 6. Delete File from Disk entirely
    lbl_delete_disk = "✕ حذف الملف من الجهاز نهائياً" if is_ar else "✕ Delete File from Disk"
    def _delete_disk():
        title = "تأكيد الحذف النهائي" if is_ar else "Confirm Permanent Deletion"
        prompt = (
            f"هل تريد بالتأكيد حذف الملف نهائياً من القرص؟\n{entry.get('filename', '')}"
            if is_ar
            else f"Are you sure you want to permanently delete this file from disk?\n{entry.get('filename', '')}"
        )
        gui = callbacks.get("gui") or getattr(root, "gui", None) or getattr(root, "_gui", None) or root
        confirmed = False
        if gui and hasattr(gui, "safe_ask_yes_no") and callable(gui.safe_ask_yes_no):
            confirmed = gui.safe_ask_yes_no(title, prompt)
        elif messagebox:
            try:
                confirmed = messagebox.askyesno(title, prompt, icon="warning", parent=root)
            except Exception:
                confirmed = False
        if confirmed:
            cb = callbacks.get("delete_from_disk")
            if callable(cb):
                cb(entry)
            else:
                try:
                    if file_path and os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
                callbacks.get("delete_entry", lambda e: None)(entry)

    menu.add_command(label=lbl_delete_disk, command=_delete_disk)

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def build_load_more_button(
    parent: Any,
    remaining: int,
    on_load_more: Callable[[], None],
) -> tk.Widget:
    """Builds an elegant load-more button indicating how many additional downloads remain."""
    is_ar = (tr("locale_lang", "") == "ar" or tr("app_title", "").startswith("فقيه"))
    btn_text = f"⬇ عرض المزيد ({remaining})" if is_ar else f"⬇ Load More ({remaining})"

    frame = tk.Frame(parent, bg="#0b0e14", pady=6)
    frame.pack(fill=tk.X)

    btn = tk.Button(
        frame,
        text=btn_text,
        font=("Segoe UI", 9, "bold"),
        bg="#1e293b",
        fg="#38bdf8",
        activebackground="#0284c7",
        activeforeground="#ffffff",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=12,
        pady=5,
        command=on_load_more
    )
    btn.pack(anchor="center")
    return frame


def setup_vault_scroll_view(col_frame: Any, body: Any, panel: Any = None) -> tuple[tk.Canvas, tk.Frame]:
    """Configures scrollable Canvas with ttk.Scrollbar and hierarchy-aware mousewheel scrolling."""
    cv = tk.Canvas(body, bg="#0b0e14", bd=0, highlightthickness=0, yscrollincrement=2)
    sb_col3 = ttk.Scrollbar(body, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb_col3.set)
    sb_col3.pack(side=tk.RIGHT, fill=tk.Y)
    cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    container = tk.Frame(cv, bg="#0b0e14")
    win_id = cv.create_window(0, 0, window=container, anchor="nw")

    cv._scrollregion_pending = False

    def _schedule_vault_scrollregion(e=None):
        if getattr(cv, "_scrollregion_pending", False):
            return
        cv._scrollregion_pending = True

        def _apply():
            cv._scrollregion_pending = False
            if cv.winfo_exists():
                cv.configure(scrollregion=cv.bbox("all"))

        cv.after_idle(_apply)

    cv._schedule_vault_scrollregion = _schedule_vault_scrollregion
    container.bind("<Configure>", _schedule_vault_scrollregion)
    def _on_cv_configure(e):
        if cv.winfo_exists() and e.width > 10 and e.width != getattr(cv, "_last_win_w", 0):
            cv._last_win_w = e.width
            cv.itemconfigure(win_id, width=e.width)

    cv.bind("<Configure>", _on_cv_configure)

    def _is_vault_target(w):
        curr = w
        while curr is not None:
            if curr in (cv, container, col_frame, body):
                return True
            curr = getattr(curr, "master", None)
        return False

    cv._vault_scroll_steps = 0
    cv._vault_scroll_timer = None

    def _get_cv_bounds():
        try:
            top, btm = cv.yview()
            return float(top), float(btm)
        except Exception:
            return 0.0, 1.0

    def _step_cv_smooth_scroll():
        cv._vault_scroll_timer = None
        if not cv.winfo_exists():
            cv._vault_scroll_steps = 0
            return
        top, btm = _get_cv_bounds()
        if top <= 0.0 and btm >= 1.0:
            cv._vault_scroll_steps = 0
            return
        steps = cv._vault_scroll_steps
        if steps == 0:
            return
        step = int(steps * 0.35)
        if step == 0:
            step = 1 if steps > 0 else -1
        if (step < 0 and top <= 0.0) or (step > 0 and btm >= 1.0):
            cv._vault_scroll_steps = 0
            return
        try:
            cv.yview_scroll(step, "units")
            cv._vault_scroll_steps -= step
            if cv._vault_scroll_steps != 0:
                cv._vault_scroll_timer = cv.after(10, _step_cv_smooth_scroll)
        except Exception:
            cv._vault_scroll_steps = 0

    def _on_wheel(e):
        if not cv.winfo_exists() or not getattr(e, "delta", None):
            return
        try:
            target = cv.winfo_containing(e.x_root, e.y_root) or getattr(e, "widget", None)
            if target is not None:
                top_win = target.winfo_toplevel()
                if top_win is not cv.winfo_toplevel() and hasattr(top_win, "_on_mousewheel"):
                    top_win._on_mousewheel(e)
                    return
            if _is_vault_target(target):
                if panel and hasattr(panel, "_on_vault_mousewheel"):
                    panel._on_vault_mousewheel(e)
                else:
                    top, btm = _get_cv_bounds()
                    if top <= 0.0 and btm >= 1.0:
                        cv._vault_scroll_steps = 0
                        return
                    notch = int(-1 * (e.delta / 120))
                    if notch == 0:
                        return
                    if (notch < 0 and cv._vault_scroll_steps > 0) or (notch > 0 and cv._vault_scroll_steps < 0):
                        cv._vault_scroll_steps = 0
                    if (notch < 0 and top <= 0.0) or (notch > 0 and btm >= 1.0):
                        cv._vault_scroll_steps = 0
                        return
                    cv._vault_scroll_steps = max(-70, min(70, cv._vault_scroll_steps + notch * 14))
                    if cv._vault_scroll_timer is None:
                        _step_cv_smooth_scroll()
        except Exception:
            pass

    cv.bind_all("<MouseWheel>", _on_wheel)
    return cv, container


def render_vault_view(
    container: tk.Frame,
    entries: List[Dict[str, Any]],
    category: str,
    limit: int,
    callbacks: Dict[str, Callable],
    card_builder: Callable,
    empty_builder: Callable,
    load_more_builder: Callable,
) -> int:
    """Renders filtered vault cards with pagination and returns total filtered count."""
    for child in container.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass

    filtered = filter_vault_entries(entries, category)
    total = len(filtered)
    if total == 0:
        empty_builder(container)
        return 0

    for entry in filtered[:limit]:
        card_builder(
            container,
            entry=entry,
            on_open_file=callbacks.get("open_file"),
            on_open_folder=callbacks.get("open_folder"),
            on_delete_entry=callbacks.get("delete_entry"),
            on_context_menu=callbacks.get("context_menu")
        )

    if total > limit:
        load_more_builder(container, total - limit, callbacks.get("load_more"))

    return total


def __getattr__(name: str):
    if name == "VaultRestoreModal":
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        return VaultRestoreModal
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_entry_category",
    "filter_vault_entries",
    "build_vault_filter_pills",
    "show_vault_context_menu",
    "build_load_more_button",
    "setup_vault_scroll_view",
    "render_vault_view",
    "clear_completed_vault_entries",
    "scan_unregistered_disk_files",
    "restore_vault_entries_from_disk",
    "open_vault_restore_dialog",
    "delete_vault_entry_with_confirm",
    "VaultRestoreModal",
]





