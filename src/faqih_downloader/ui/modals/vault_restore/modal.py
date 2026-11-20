"""
VaultRestoreModal: Selective file restoration modal dialog for Completed Vault in Smart Download (SD).
"""
from __future__ import annotations
import os
from typing import Any, List, Dict, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore

from faqih_downloader.locales.i18n import tr
from faqih_downloader.config import get_resource_path
from faqih_downloader.utils.tk_helpers import _detach_photo_tk
from faqih_downloader.utils.window_effects import enable_dark_titlebar
from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files
from .scroll_mixin import VaultRestoreScrollMixin
from .selection_mixin import VaultRestoreSelectionMixin
from .rows_builder import VaultRestoreRowsMixin
from .actions_mixin import VaultRestoreActionsMixin


class VaultRestoreModal(
    VaultRestoreActionsMixin,
    VaultRestoreRowsMixin,
    VaultRestoreSelectionMixin,
    VaultRestoreScrollMixin,
    tk.Toplevel if tk is not None else object
):
    """
    Selective modal dialog allowing users to scan disk for completed files,
    filter by keyword, select specific files to restore, or browse custom folders and files.
    """

    def __init__(self, gui: Any):
        parent = getattr(gui, "root", None) if hasattr(gui, "root") else gui
        if tk is not None:
            super().__init__(parent)
        self.gui = gui
        self.parent = parent
        self._closing = False
        self._modal_icon_photo = None
        self._display_limit = 40
        self._btn_load_more = None
        self._scroll_steps_remaining = 0
        self._scroll_timer_id = None
        self._scrollregion_pending = False

        # Theme colors
        self.c_bg, self.c_panel, self.c_card = "#0b0e14", "#151a24", "#1c2333"
        self.c_border, self.c_accent, self.c_accent_blue = "#283548", "#19f3ee", "#38bdf8"
        self.c_text_bright, self.c_text_muted = "#f8fafc", "#94a3b8"
        self.c_danger, self.c_success = "#ef4444", "#22c55e"

        if tk is not None:
            self.title(tr("vault_restore_dlg_title", "Restore Files to Completed Vault"))
            self.configure(bg=self.c_bg)

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
            dlg_w, dlg_h = 700, 540
            try:
                px = parent.winfo_rootx() + (parent.winfo_width() - dlg_w) // 2
                py = parent.winfo_rooty() + (parent.winfo_height() - dlg_h) // 2
                px, py = max(10, px), max(10, py)
            except Exception:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                px, py = max(10, (sw - dlg_w) // 2), max(10, (sh - dlg_h) // 2)
            self.geometry(f"{dlg_w}x{dlg_h}+{px}+{py}")
            self.minsize(520, 400)

        # Detect initial scan directory
        from faqih_downloader.config import get_setting, get_base_downloads_dir
        base_dir = str(get_setting("last_download_dir", "") or "").strip()
        if not base_dir or not os.path.isdir(base_dir):
            if hasattr(gui, "_get_base_downloads_dir") and callable(gui._get_base_downloads_dir):
                base_dir = gui._get_base_downloads_dir()
            else:
                base_dir = get_base_downloads_dir()
        self._current_scan_dir = base_dir if (base_dir and os.path.isdir(base_dir)) else None

        # Discovered files data, check states, and widget registry
        self._all_files: List[Dict[str, Any]] = scan_unregistered_disk_files(gui)
        self._item_vars: Dict[str, Any] = {}
        self._row_widgets: Dict[str, Dict[str, Any]] = {}
        for f_info in self._all_files:
            if tk is not None:
                self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=False)
            else:
                self._item_vars[f_info["file_path"]] = None

        if tk is not None:
            self._build_ui()
            enable_dark_titlebar(self)
            self._display_files()

    def grab_set(self): pass  # Eliminates Win32 modal input locks
    def grab_set_global(self): pass

    def destroy(self):
        self._closing = True
        if getattr(self, "_scroll_timer_id", None) is not None:
            try: self.after_cancel(self._scroll_timer_id)
            except Exception: pass
            self._scroll_timer_id = None
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
        lbl_title = tk.Label(hdr, text=tr("vault_restore_dlg_title", "Restore Files to Completed Vault"), font=("Segoe UI", 11, "bold"), bg=self.c_panel, fg=self.c_text_bright)
        lbl_title.pack(side=tk.LEFT)
        btn_close = tk.Label(hdr, text="✕", font=("Segoe UI", 11, "bold"), bg=self.c_panel, fg=self.c_text_muted, cursor="hand2")
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=self.c_danger))
        btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=self.c_text_muted))
        btn_close.bind("<Button-1>", lambda e: self.destroy())

        # ── 2. Search & Select Controls Bar ──────────────────────────────────
        filter_bar = tk.Frame(self, bg=self.c_bg, padx=16, pady=8)
        filter_bar.pack(fill=tk.X)
        self.entry_search = tk.Entry(filter_bar, font=("Segoe UI", 10), bg=self.c_card, fg=self.c_text_bright, insertbackground=self.c_text_bright, relief=tk.FLAT, highlightthickness=1, highlightbackground=self.c_border, highlightcolor=self.c_accent)
        self.entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 10))
        self.entry_search.bind("<KeyRelease>", self._on_search_changed)

        btn_sel = tk.Label(filter_bar, text=tr("vault_select_all", "Select All"), font=("Segoe UI", 9, "bold"), bg=self.c_bg, fg=self.c_accent_blue, cursor="hand2")
        btn_sel.pack(side=tk.LEFT, padx=(0, 8))
        btn_sel.bind("<Button-1>", lambda e: self._toggle_all_selection(True))

        btn_desel = tk.Label(filter_bar, text=tr("vault_deselect_all", "Deselect All"), font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text_muted, cursor="hand2")
        btn_desel.pack(side=tk.LEFT)
        btn_desel.bind("<Button-1>", lambda e: self._toggle_all_selection(False))

        # ── 3. Current Folder Bar ────────────────────────────────────────────
        folder_bar = tk.Frame(self, bg=self.c_panel, padx=16, pady=6)
        folder_bar.pack(fill=tk.X)
        self.btn_browse_folder_top = tk.Button(folder_bar, text=tr("vault_btn_browse_folder", "▤ Browse Folder..."), font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent, activebackground=self.c_border, activeforeground=self.c_accent, relief=tk.FLAT, padx=10, pady=3, cursor="hand2", command=self.browse_folder)
        self.btn_browse_folder_top.pack(side=tk.RIGHT)

        disp_path = self._current_scan_dir or tr("downloads_title", "Downloads")
        self.lbl_current_folder = tk.Label(folder_bar, text=f"📂 {disp_path}", font=("Segoe UI", 9), bg=self.c_panel, fg=self.c_text_muted, anchor="w")
        self.lbl_current_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 4. Bottom Action Buttons Bar (Packed to BOTTOM before list) ──────
        btn_bar = tk.Frame(self, bg=self.c_panel, padx=16, pady=12)
        btn_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_restore_sel = tk.Button(btn_bar, text=tr("vault_btn_restore_selected", "✓ Restore Selected"), font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff", relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.restore_selected)
        self.btn_restore_sel.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_browse_folder = tk.Button(btn_bar, text=tr("vault_btn_browse_folder", "▤ Browse Folder..."), font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent, activebackground=self.c_border, activeforeground=self.c_accent, relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.browse_folder)
        self.btn_browse_folder.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_browse = tk.Button(btn_bar, text=tr("vault_btn_browse_file", "▣ Browse File..."), font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_text_bright, activebackground=self.c_border, activeforeground="#ffffff", relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.browse_files)
        self.btn_browse.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_restore_all = tk.Button(btn_bar, text=tr("vault_btn_restore_all", "↻ Restore All"), font=("Segoe UI", 9), bg=self.c_card, fg=self.c_accent, activebackground=self.c_border, activeforeground=self.c_accent, relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.restore_all)
        self.btn_restore_all.pack(side=tk.RIGHT)

        # ── 5. Scrollable File List Container ────────────────────────────────
        list_outer = tk.Frame(self, bg=self.c_bg, padx=16, pady=4)
        list_outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(list_outer, bg=self.c_bg, highlightthickness=0, bd=0, yscrollincrement=2)
        self.scrollbar = ttk.Scrollbar(list_outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.c_bg)
        self._canvas_win_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._schedule_scrollregion_update)
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self._canvas_win_id, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind("<Enter>", lambda e: not getattr(self, "_closing", False) and self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
