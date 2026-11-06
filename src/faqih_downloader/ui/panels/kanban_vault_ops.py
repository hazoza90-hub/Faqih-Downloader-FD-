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
    if hasattr(gui, "refresh_history_table") and callable(gui.refresh_history_table):
        gui.refresh_history_table()
    return True


def scan_unregistered_disk_files(gui: Any) -> List[Dict[str, Any]]:
    """
    Scans the base downloads directory and subfolders for completed files
    that are not currently registered in DownloadHistoryManager.
    """
    history_mgr = getattr(gui, "history_manager", None)
    if not history_mgr:
        return []

    from faqih_downloader.config import get_setting, get_base_downloads_dir
    base_dir = str(get_setting("last_download_dir", "") or "").strip()
    if not base_dir or not os.path.isdir(base_dir):
        if hasattr(gui, "_get_base_downloads_dir") and callable(gui._get_base_downloads_dir):
            base_dir = gui._get_base_downloads_dir()
        else:
            base_dir = get_base_downloads_dir()

    if not base_dir or not os.path.isdir(base_dir):
        return []

    sub_dirs = ["", "Video", "Music", "Audio", "Compressed", "Documents", "Programs"]
    ignored_suffixes = (".part", ".ytdl", ".tmp", ".sd_parts", ".json", ".ini")
    ignored_names = {"desktop.ini", "thumbs.db", ".ds_store"}

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

    # Get entry category helper from vault helpers if present
    mod = sys.modules.get("faqih_downloader.ui.panels.kanban_vault_helpers")
    cat_fn = getattr(mod, "get_entry_category", None)
    if cat_fn is None:
        from faqih_downloader.ui.panels.kanban_vault_helpers import get_entry_category as cat_fn

    results = []
    seen_paths = set()
    for sub in sub_dirs:
        scan_dir = os.path.join(base_dir, sub) if sub else base_dir
        if not os.path.isdir(scan_dir):
            continue
        try:
            with os.scandir(scan_dir) as it:
                for item in it:
                    if not item.is_file():
                        continue
                    name = item.name
                    lower_name = name.lower()
                    if lower_name in ignored_names or any(lower_name.endswith(sfx) for sfx in ignored_suffixes):
                        continue
                    try:
                        abs_path = os.path.normcase(os.path.abspath(item.path))
                    except Exception:
                        abs_path = item.path

                    if abs_path in existing_paths or lower_name in existing_names or abs_path in seen_paths:
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

    return results


def restore_vault_entries_from_disk(gui: Any) -> int:
    """Scans disk and directly restores all unrecorded files into history_manager."""
    history_mgr = getattr(gui, "history_manager", None)
    if not history_mgr:
        return 0

    files = scan_unregistered_disk_files(gui)
    restored_count = 0
    for f_info in files:
        history_mgr.add_or_update_entry(
            url="",
            file_path=f_info["file_path"],
            size_bytes=f_info["size_bytes"],
            status="Completed"
        )
        restored_count += 1

    if restored_count > 0:
        if hasattr(gui, "refresh_history_table") and callable(gui.refresh_history_table):
            try:
                gui.refresh_history_table()
            except Exception:
                pass
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
        if hasattr(gui, "refresh_history_table") and callable(gui.refresh_history_table):
            gui.refresh_history_table()
    return True


__all__ = [
    "clear_completed_vault_entries",
    "scan_unregistered_disk_files",
    "restore_vault_entries_from_disk",
    "open_vault_restore_dialog",
    "delete_vault_entry_with_confirm",
]
