"""
VaultRestoreModal: Selective file restoration modal dialog for Completed Vault in Smart Download (SD).
"""
from __future__ import annotations

import os
try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore
from typing import Any, List, Dict, Optional

from smart_download.locales.i18n import tr
from smart_download.config import get_resource_path
from smart_download.utils.tk_helpers import _detach_photo_tk
from smart_download.ui.panels.kanban_vault_ops import scan_unregistered_disk_files


def _format_size(size_bytes: int) -> str:
    """Formats raw bytes into human-readable unit string."""
    if size_bytes <= 0:
        return "0 B"
    s = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024:
            return f"{s:.1f} {unit}" if unit != "B" else f"{int(s)} B"
        s /= 1024.0
    return f"{s:.1f} PB"


class VaultRestoreModal(tk.Toplevel if tk is not None else object):
    """
    Selective modal dialog allowing users to scan disk for completed files,
    filter by keyword, select specific files to restore, or browse custom files.
    """

    def __init__(self, gui: Any):
        parent = getattr(gui, "root", None) if hasattr(gui, "root") else gui
        super().__init__(parent)
        self.gui = gui
        self.parent = parent
        self._closing = False
        self._modal_icon_photo = None

        # Theme colors
        self.c_bg = "#0b0e14"
        self.c_panel = "#151a24"
        self.c_card = "#1c2333"
        self.c_border = "#283548"
        self.c_accent = "#19f3ee"
        self.c_accent_blue = "#38bdf8"
        self.c_text_bright = "#f8fafc"
        self.c_text_muted = "#94a3b8"
        self.c_danger = "#ef4444"
        self.c_success = "#22c55e"

        self.title(tr("vault_restore_dlg_title", "Restore Files to Completed Vault"))
        self.configure(bg=self.c_bg)
        try:
            self.attributes("-alpha", 0.96)
        except Exception:
            pass

        # Set safe window icon
        ico_path = get_resource_path("app_icon.png")
        if os.path.isfile(ico_path):
            try:
                from PIL import ImageTk
                self._modal_icon_photo = ImageTk.PhotoImage(file=ico_path, master=self)
                self.iconphoto(False, self._modal_icon_photo)
            except Exception:
                pass

        # Center on screen or parent
        dlg_w, dlg_h = 680, 520
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
            px = max(10, px)
            py = max(10, py)
        except Exception:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            px = max(10, (sw - dlg_w) // 2)
            py = max(10, (sh - dlg_h) // 2)
        self.geometry(f"{dlg_w}x{dlg_h}+{px}+{py}")
        self.minsize(500, 380)

        # Discovered files data and check states
        self._all_files: List[Dict[str, Any]] = scan_unregistered_disk_files(gui)
        self._item_vars: Dict[str, tk.BooleanVar] = {}
        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(value=False)

        self._build_ui()
        self._display_files()

    def grab_set(self):
        """No-op: Eliminates Win32 modal input locks."""
        pass

    def grab_set_global(self):
        """No-op: Eliminates Win32 modal input locks."""
        pass

    def destroy(self):
        self._closing = True
        try:
            self.unbind_all("<MouseWheel>")
        except Exception:
            pass
        if hasattr(self, "gui") and self.gui:
            wheel_cb = getattr(self.gui, "_on_global_col3_wheel", None)
            root = getattr(self.gui, "root", None) or self.gui
            if wheel_cb and hasattr(root, "bind_all"):
                try:
                    root.bind_all("<MouseWheel>", wheel_cb)
                except Exception:
                    pass
        try:
            super().destroy()
        finally:
            _detach_photo_tk(self)

    def _build_ui(self):
        # ── 1. Top Header Bar ────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=self.c_panel, padx=16, pady=12)
        hdr.pack(fill=tk.X)

        lbl_icon = tk.Label(hdr, text="↻", font=("Segoe UI", 13, "bold"), bg=self.c_panel, fg=self.c_accent)
        lbl_icon.pack(side=tk.LEFT, padx=(0, 8))

        lbl_title = tk.Label(
            hdr,
            text=tr("vault_restore_dlg_title", "Restore Files to Completed Vault"),
            font=("Segoe UI", 11, "bold"),
            bg=self.c_panel,
            fg=self.c_text_bright
        )
        lbl_title.pack(side=tk.LEFT)

        btn_close = tk.Label(
            hdr, text="✕", font=("Segoe UI", 11, "bold"), bg=self.c_panel, fg=self.c_text_muted, cursor="hand2"
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=self.c_danger))
        btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=self.c_text_muted))
        btn_close.bind("<Button-1>", lambda e: self.destroy())

        # ── 2. Search & Select Controls ──────────────────────────────────────
        filter_bar = tk.Frame(self, bg=self.c_bg, padx=16, pady=8)
        filter_bar.pack(fill=tk.X)

        self.entry_search = tk.Entry(
            filter_bar,
            font=("Segoe UI", 10),
            bg=self.c_card,
            fg=self.c_text_bright,
            insertbackground=self.c_text_bright,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.c_border,
            highlightcolor=self.c_accent
        )
        self.entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 10))
        self.entry_search.bind("<KeyRelease>", lambda e: self._display_files())

        btn_sel_all = tk.Label(
            filter_bar,
            text=tr("vault_select_all", "Select All"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_accent_blue,
            cursor="hand2"
        )
        btn_sel_all.pack(side=tk.LEFT, padx=(0, 8))
        btn_sel_all.bind("<Button-1>", lambda e: self._toggle_all_selection(True))

        btn_desel_all = tk.Label(
            filter_bar,
            text=tr("vault_deselect_all", "Deselect All"),
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_text_muted,
            cursor="hand2"
        )
        btn_desel_all.pack(side=tk.LEFT)
        btn_desel_all.bind("<Button-1>", lambda e: self._toggle_all_selection(False))

        # ── 3. Scrollable File List Container ────────────────────────────────
        list_outer = tk.Frame(self, bg=self.c_bg, padx=16, pady=4)
        list_outer.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(list_outer, bg=self.c_bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.c_bg)
        self._canvas_win_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._canvas_win_id, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # ── 4. Bottom Action Buttons Bar ─────────────────────────────────────
        btn_bar = tk.Frame(self, bg=self.c_panel, padx=16, pady=12)
        btn_bar.pack(fill=tk.X)

        # Button 1: Restore Selected
        self.btn_restore_sel = tk.Button(
            btn_bar,
            text=tr("vault_btn_restore_selected", "✓ Restore Selected"),
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.restore_selected
        )
        self.btn_restore_sel.pack(side=tk.LEFT, padx=(0, 8))

        # Button 2: Browse File from Disk
        self.btn_browse = tk.Button(
            btn_bar,
            text=tr("vault_btn_browse_file", "▣ Browse File..."),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_card,
            fg=self.c_text_bright,
            activebackground=self.c_border,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.browse_files
        )
        self.btn_browse.pack(side=tk.LEFT, padx=(0, 8))

        # Button 3: Restore All
        self.btn_restore_all = tk.Button(
            btn_bar,
            text=tr("vault_btn_restore_all", "↻ Restore All"),
            font=("Segoe UI", 9),
            bg=self.c_card,
            fg=self.c_accent,
            activebackground=self.c_border,
            activeforeground=self.c_accent,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.restore_all
        )
        self.btn_restore_all.pack(side=tk.RIGHT)

    def _on_mousewheel(self, event):
        """Scrolls the canvas with mouse wheel if window exists."""
        if getattr(self, "_closing", False):
            return
        try:
            if self.winfo_exists() and hasattr(self, "canvas") and self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _toggle_all_selection(self, select: bool):
        """Sets all checkboxes to either checked or unchecked."""
        for var in self._item_vars.values():
            var.set(select)

    def _display_files(self):
        """Renders file rows in scrollable frame, filtering by search query."""
        for child in self.scrollable_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        query = self.entry_search.get().strip().lower() if hasattr(self, "entry_search") else ""
        filtered = [
            f for f in self._all_files
            if not query or query in f["filename"].lower()
        ]

        if not filtered:
            lbl_empty = tk.Label(
                self.scrollable_frame,
                text=tr("vault_no_unregistered_files", "No unregistered files found on disk"),
                font=("Segoe UI", 10),
                bg=self.c_bg,
                fg=self.c_text_muted,
                pady=40
            )
            lbl_empty.pack(fill=tk.BOTH, expand=True)
            return

        for f_info in filtered:
            path = f_info["file_path"]
            var = self._item_vars.get(path)
            if var is None:
                var = tk.BooleanVar(value=False)
                self._item_vars[path] = var

            row = tk.Frame(self.scrollable_frame, bg=self.c_card, padx=10, pady=8)
            row.pack(fill=tk.X, pady=2)

            cb = tk.Checkbutton(
                row,
                variable=var,
                bg=self.c_card,
                activebackground=self.c_card,
                selectcolor=self.c_panel,
                cursor="hand2"
            )
            cb.pack(side=tk.LEFT, padx=(0, 8))

            name_lbl = tk.Label(
                row,
                text=f_info["filename"],
                font=("Segoe UI", 9, "bold"),
                bg=self.c_card,
                fg=self.c_text_bright,
                anchor="w"
            )
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            cat_lbl = tk.Label(
                row,
                text=f"[{f_info.get('category', 'general').upper()}]",
                font=("Segoe UI", 8),
                bg=self.c_card,
                fg=self.c_accent
            )
            cat_lbl.pack(side=tk.RIGHT, padx=(6, 0))

            size_lbl = tk.Label(
                row,
                text=_format_size(f_info.get("size_bytes", 0)),
                font=("Segoe UI", 9),
                bg=self.c_card,
                fg=self.c_text_muted
            )
            size_lbl.pack(side=tk.RIGHT, padx=(6, 6))

    def restore_selected(self) -> int:
        """Restores only files with active checkbox checked."""
        history_mgr = getattr(self.gui, "history_manager", None)
        if not history_mgr:
            self.destroy()
            return 0

        restored_count = 0
        for f_info in self._all_files:
            path = f_info["file_path"]
            var = self._item_vars.get(path)
            if var and var.get():
                history_mgr.add_or_update_entry(
                    url="",
                    file_path=path,
                    size_bytes=f_info.get("size_bytes", 0),
                    status="Completed"
                )
                restored_count += 1

        self._finalize_and_close()
        return restored_count

    def restore_all(self) -> int:
        """Restores all discovered files regardless of filter or checkbox state."""
        history_mgr = getattr(self.gui, "history_manager", None)
        if not history_mgr:
            self.destroy()
            return 0

        restored_count = 0
        for f_info in self._all_files:
            history_mgr.add_or_update_entry(
                url="",
                file_path=f_info["file_path"],
                size_bytes=f_info.get("size_bytes", 0),
                status="Completed"
            )
            restored_count += 1

        self._finalize_and_close()
        return restored_count

    def browse_files(self) -> int:
        """Prompts user to select arbitrary files from disk and adds them to history."""
        history_mgr = getattr(self.gui, "history_manager", None)
        if not history_mgr:
            return 0

        selected_files = filedialog.askopenfilenames(
            parent=self,
            title=tr("vault_btn_browse_file", "▣ Browse File...")
        )
        if not selected_files:
            return 0

        restored_count = 0
        for path in selected_files:
            if os.path.isfile(path):
                try:
                    sz = os.path.getsize(path)
                except Exception:
                    sz = 0
                history_mgr.add_or_update_entry(
                    url="",
                    file_path=path,
                    size_bytes=sz,
                    status="Completed"
                )
                restored_count += 1

        if restored_count > 0:
            self._finalize_and_close()
        return restored_count

    def _finalize_and_close(self):
        """Refreshes Column 3 and history table, then cleanly destroys modal dialog."""
        if hasattr(self.gui, "refresh_history_table") and callable(self.gui.refresh_history_table):
            try:
                self.gui.refresh_history_table()
            except Exception:
                pass
        if hasattr(self.gui, "refresh_kanban_col3") and callable(self.gui.refresh_kanban_col3):
            try:
                self.gui.refresh_kanban_col3()
            except Exception:
                pass
        self.destroy()


__all__ = ["VaultRestoreModal", "scan_unregistered_disk_files"]
