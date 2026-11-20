"""
ChunksContextMenuMixin: Right-click context menus for chunk treeview and download action routing.
"""
from __future__ import annotations
import os
import sys
import subprocess

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr


class ChunksContextMenuMixin:
    """Provides methods for constructing and showing right-click context menus on chunk rows."""

    def _build_tree_context_menu(self):
        """Constructs right-click context menu for download task & chunk view."""
        self.tree_context_menu = tk.Menu(
            self.tree_chunks,
            tearoff=0,
            bg=self.c_panel,
            fg=self.c_text_bright,
            activebackground=self.c_accent_dark,
            activeforeground="white",
            relief="flat",
            bd=1
        )
        self.tree_context_menu.add_command(
            label=tr("ctx_refresh_address", "↻ Refresh Download Address..."),
            command=self._open_refresh_link_dialog
        )
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(
            label=tr("ctx_resume_download", "▶ Resume Download"),
            command=self._menu_resume
        )
        self.tree_context_menu.add_command(
            label=tr("ctx_pause_download", "|| Pause Download"),
            command=self._menu_pause
        )
        self.tree_context_menu.add_command(
            label=tr("ctx_cancel_download", "✕ Cancel Download"),
            command=self._on_cancel_download
        )
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(
            label=tr("ctx_copy_download_url", "⎘ Copy Download URL"),
            command=self._copy_current_url
        )
        self.tree_context_menu.add_command(
            label=tr("ctx_open_folder", "⋯ Open Containing Folder"),
            command=self._open_download_folder
        )

    def _show_tree_context_menu(self, event):
        """Displays right-click context menu on treeview."""
        self._build_tree_context_menu()
        try:
            iid = self.tree_chunks.identify_row(event.y)
            if iid:
                self.tree_chunks.selection_set(iid)
                self.tree_chunks.focus(iid)
        except Exception:
            pass
        try:
            self.tree_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.tree_context_menu.grab_release()
            except Exception:
                pass

    def _menu_resume(self):
        if getattr(self, "engine", None) and self.engine.is_paused:
            self._on_pause_resume()
        elif getattr(self, "engine", None) and not self.engine.is_running:
            self.engine.resume_transfer()
            self.btn_start.configure(state="disabled")
            self.btn_pause.configure(state="normal", text=tr("btn_pause", "|| Pause"), bg=self.c_panel_light)
            self.btn_cancel.configure(state="normal")
            if hasattr(self, "btn_refresh_link"):
                self.btn_refresh_link.configure(state="normal")

    def _menu_pause(self):
        if getattr(self, "engine", None) and self.engine.is_running and not self.engine.is_paused:
            self._on_pause_resume()

    def _copy_current_url(self):
        url = (self.engine.url if getattr(self, "engine", None) else self.entry_url.get()).strip()
        if url:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                if hasattr(self, "log") and callable(self.log):
                    self.log(f"Copied download URL to clipboard: {url}")
            except Exception:
                pass

    def _open_download_folder(self):
        dest = self.entry_dest.get().strip() if hasattr(self, "entry_dest") else ""
        folder = os.path.dirname(dest) if dest else os.path.expanduser("~")
        if os.path.isdir(folder):
            try:
                if sys.platform.startswith("win"):
                    os.startfile(folder)
                elif sys.platform.startswith("darwin"):
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                if hasattr(self, "log") and callable(self.log):
                    self.log(f"Failed to open folder: {e}")
