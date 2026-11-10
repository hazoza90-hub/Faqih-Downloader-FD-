"""
kanban_vault_ops.py: Completed Vault filesystem operations, disk scanning,
and restoration logic for Smart Download (SD).
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Callable, Any

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None  # type: ignore
    messagebox = None  # type: ignore

from faqih_downloader.locales.i18n import tr
from faqih_downloader.config import is_test_environment


def _safe_refresh_history(gui: Any) -> None:
    """Invokes either refresh_history_table or _refresh_history_table safely."""
    if hasattr(gui, "refresh_history_table") and callable(gui.refresh_history_table):
        try:
            gui.refresh_history_table()
        except Exception:
            pass
    if hasattr(gui, "_refresh_history_table") and callable(gui._refresh_history_table):
        try:
            gui._refresh_history_table(force=True)
        except TypeError:
            try:
                gui._refresh_history_table()
            except Exception:
                pass
        except Exception:
            pass


def clear_completed_vault_entries(gui: Any) -> bool:
    """Prompts user for confirmation and clears completed downloads from UI and history."""
    title = tr("vault_clear_confirm_title", "Confirm Clear List")
    msg = tr("vault_clear_confirm_msg", "Clear completed list from UI? (Files on your disk will NOT be deleted)")
    confirmed = False
    if hasattr(gui, "safe_ask_yes_no") and callable(gui.safe_ask_yes_no):
        confirmed = gui.safe_ask_yes_no(title, msg)
    elif messagebox:
        try:
            confirmed = bool(messagebox.askyesno(title, msg, parent=getattr(gui, "root", None)))
        except Exception:
            confirmed = False

    if not confirmed:
        return False

    history_mgr = getattr(gui, "history_manager", None)
    if history_mgr:
        for e in list(history_mgr.get_entries()):
            if str(e.get("status", "")).strip().lower() in ("completed", "مكتمل", "success"):
                history_mgr.remove_entry(e.get("id"))

    if hasattr(gui, "refresh_kanban_col3") and callable(gui.refresh_kanban_col3):
        gui.refresh_kanban_col3()
    _safe_refresh_history(gui)
    return True


def scan_unregistered_disk_files(
    gui: Any,
    custom_dir: Optional[str] = None,
    max_results: int = 300
) -> List[Dict[str, Any]]:
    """
    Fast, non-blocking scan of the base downloads directory or custom_dir using
    depth-limited os.scandir (max depth 2, max results capped) to prevent UI freezing.
    """
    history_mgr = getattr(gui, "history_manager", None)
    if not history_mgr:
        return []

    from faqih_downloader.config import get_setting, get_base_downloads_dir
    is_custom = bool(custom_dir and os.path.isdir(custom_dir))
    if is_custom:
        base_dir = os.path.abspath(custom_dir)  # type: ignore
    else:
        base_dir = str(get_setting("last_download_dir", "") or "").strip()
        if not base_dir or not os.path.isdir(base_dir):
            if hasattr(gui, "_get_base_downloads_dir") and callable(gui._get_base_downloads_dir):
                base_dir = gui._get_base_downloads_dir()
            else:
                base_dir = get_base_downloads_dir()

    if not base_dir or not os.path.isdir(base_dir):
        return []

    ignored_suffixes = (".part", ".ytdl", ".tmp", ".sd_parts", ".json", ".ini")
    ignored_names = {"desktop.ini", "thumbs.db", ".ds_store"}
    ignored_dirs = {
        "windows", "program files", "program files (x86)", "programdata",
        "appdata", "node_modules", ".git", ".venv", "venv", "__pycache__",
        "$recycle.bin", "system volume information", "library", "cargo", "rustup"
    }

    existing_paths = set()
    existing_names = set()
    for entry in history_mgr.get_entries():
        fp = entry.get("file_path")
        if fp:
            try:
                existing_paths.add(os.path.normcase(os.path.abspath(fp)))
            except Exception:
                pass
        fn = entry.get("filename")
        if fn:
            existing_names.add(fn.lower())

    mod = sys.modules.get("faqih_downloader.ui.panels.kanban_vault_helpers")
    cat_fn = getattr(mod, "get_entry_category", None)
    if cat_fn is None:
        from faqih_downloader.ui.panels.kanban_vault_helpers import get_entry_category as cat_fn

    results: List[Dict[str, Any]] = []
    seen_paths = set()
    queue = [(base_dir, 0)]  # (directory_path, depth)

    while queue and len(results) < max_results:
        cur_dir, depth = queue.pop(0)
        try:
            with os.scandir(cur_dir) as it:
                for item in it:
                    if len(results) >= max_results:
                        break
                    try:
                        if item.is_dir(follow_symlinks=False):
                            name_lower = item.name.lower()
                            if depth < 2 and name_lower not in ignored_dirs and not item.name.startswith("."):
                                queue.append((item.path, depth + 1))
                        elif item.is_file(follow_symlinks=False):
                            name = item.name
                            lower_name = name.lower()
                            if lower_name in ignored_names or any(lower_name.endswith(sfx) for sfx in ignored_suffixes):
                                continue
                            try:
                                abs_path = os.path.normcase(os.path.abspath(item.path))
                            except Exception:
                                abs_path = item.path

                            if abs_path in existing_paths or abs_path in seen_paths:
                                continue
                            if not is_custom and lower_name in existing_names:
                                continue

                            seen_paths.add(abs_path)
                            try:
                                size_bytes = item.stat().st_size
                            except Exception:
                                size_bytes = 0

                            cat = cat_fn({"filename": name})
                            results.append({
                                "filename": name,
                                "file_path": item.path,
                                "size_bytes": size_bytes,
                                "category": cat
                            })
                    except Exception:
                        pass
        except Exception:
            pass

    return results


def restore_vault_entries_from_disk(gui: Any) -> int:
    """Scans disk and directly restores all unrecorded files into history_manager."""
    history_mgr = getattr(gui, "history_manager", None)
    if not history_mgr:
        return 0

    files = scan_unregistered_disk_files(gui)
    restored_count = 0
    for f_info in files:
        try:
            history_mgr.add_or_update_entry(
                url="",
                file_path=f_info["file_path"],
                size_bytes=f_info["size_bytes"],
                status="Completed",
                save=False
            )
        except TypeError:
            history_mgr.add_or_update_entry(
                url="",
                file_path=f_info["file_path"],
                size_bytes=f_info["size_bytes"],
                status="Completed"
            )
        restored_count += 1

    if restored_count > 0:
        for s_fn in ("_save_entries", "save_entries", "save"):
            fn = getattr(history_mgr, s_fn, None)
            if callable(fn):
                try:
                    fn()
                    break
                except Exception:
                    pass
        if hasattr(gui, "_vault_filter_category"):
            gui._vault_filter_category = "all"
        _safe_refresh_history(gui)
        if hasattr(gui, "refresh_kanban_col3") and callable(gui.refresh_kanban_col3):
            gui.refresh_kanban_col3()

    return restored_count


def open_vault_restore_dialog(gui: Any):
    """Opens VaultRestoreModal for selective file restoration."""
    mod = sys.modules.get("faqih_downloader.ui.panels.kanban_vault_helpers")
    modal_cls = getattr(mod, "VaultRestoreModal", None) if mod else None
    if modal_cls is None:
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal as modal_cls
    return modal_cls(gui)


def delete_vault_entry_with_confirm(
    gui: Any,
    entry: Dict[str, Any],
    skip_confirm: bool = False
) -> bool:
    """
    Prompts confirmation before removing an item from the Completed Vault,
    then deletes it from history_manager if confirmed.
    """
    if not entry:
        return False
    filename = entry.get("filename") or os.path.basename(entry.get("file_path") or "") or "download.bin"
    if not skip_confirm:
        title = tr("vault_remove_item_title", "Confirm Remove Item")
        msg = tr(
            "vault_remove_item_msg",
            "Remove this item from Completed Vault? (The file on your disk will NOT be deleted)\n{filename}"
        ).replace("{filename}", filename)
        confirmed = False
        if hasattr(gui, "safe_ask_yes_no") and callable(gui.safe_ask_yes_no):
            confirmed = gui.safe_ask_yes_no(title, msg)
        elif is_test_environment():
            confirmed = True
        elif messagebox:
            try:
                confirmed = messagebox.askyesno(title, msg, parent=getattr(gui, "root", None))
            except Exception:
                confirmed = False
        if not confirmed:
            return False

    if hasattr(gui, "history_manager") and gui.history_manager:
        entry_id = entry.get("id")
        if entry_id:
            gui.history_manager.remove_entry(entry_id)
        if hasattr(gui, "refresh_kanban_col3") and callable(gui.refresh_kanban_col3):
            gui.refresh_kanban_col3()
        _safe_refresh_history(gui)
    return True


__all__ = [
    "clear_completed_vault_entries",
    "scan_unregistered_disk_files",
    "restore_vault_entries_from_disk",
    "open_vault_restore_dialog",
    "delete_vault_entry_with_confirm",
]
