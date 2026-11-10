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

from faqih_downloader.locales.i18n import tr
from faqih_downloader.config import get_resource_path
from faqih_downloader.utils.tk_helpers import _detach_photo_tk
from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files


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
    filter by keyword, select specific files to restore, or browse custom folders and files.
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
        self._item_vars: Dict[str, tk.BooleanVar] = {}
        self._row_widgets: Dict[str, Dict[str, Any]] = {}
        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=False)

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
            hdr, text=tr("vault_restore_dlg_title", "Restore Files to Completed Vault"),
            font=("Segoe UI", 11, "bold"), bg=self.c_panel, fg=self.c_text_bright
        )
        lbl_title.pack(side=tk.LEFT)

        btn_close = tk.Label(
            hdr, text="✕", font=("Segoe UI", 11, "bold"), bg=self.c_panel, fg=self.c_text_muted, cursor="hand2"
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=self.c_danger))
        btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=self.c_text_muted))
        btn_close.bind("<Button-1>", lambda e: self.destroy())

        # ── 2. Search & Select Controls Bar ──────────────────────────────────
        filter_bar = tk.Frame(self, bg=self.c_bg, padx=16, pady=8)
        filter_bar.pack(fill=tk.X)

        self.entry_search = tk.Entry(
            filter_bar, font=("Segoe UI", 10), bg=self.c_card, fg=self.c_text_bright,
            insertbackground=self.c_text_bright, relief=tk.FLAT, highlightthickness=1,
            highlightbackground=self.c_border, highlightcolor=self.c_accent
        )
        self.entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 10))
        self.entry_search.bind("<KeyRelease>", lambda e: self._display_files())

        btn_sel_all = tk.Label(
            filter_bar, text=tr("vault_select_all", "Select All"),
            font=("Segoe UI", 9, "bold"), bg=self.c_bg, fg=self.c_accent_blue, cursor="hand2"
        )
        btn_sel_all.pack(side=tk.LEFT, padx=(0, 8))
        btn_sel_all.bind("<Button-1>", lambda e: self._toggle_all_selection(True))

        btn_desel_all = tk.Label(
            filter_bar, text=tr("vault_deselect_all", "Deselect All"),
            font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text_muted, cursor="hand2"
        )
        btn_desel_all.pack(side=tk.LEFT)
        btn_desel_all.bind("<Button-1>", lambda e: self._toggle_all_selection(False))

        # ── 3. Current Folder Bar ────────────────────────────────────────────
        folder_bar = tk.Frame(self, bg=self.c_panel, padx=16, pady=6)
        folder_bar.pack(fill=tk.X)

        self.btn_browse_folder_top = tk.Button(
            folder_bar, text=tr("vault_btn_browse_folder", "📁 Browse Folder..."),
            font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent,
            activebackground=self.c_border, activeforeground=self.c_accent,
            relief=tk.FLAT, padx=10, pady=3, cursor="hand2", command=self.browse_folder
        )
        self.btn_browse_folder_top.pack(side=tk.RIGHT)

        disp_path = self._current_scan_dir or tr("downloads_title", "Downloads")
        self.lbl_current_folder = tk.Label(
            folder_bar, text=f"📂 {disp_path}", font=("Segoe UI", 9),
            bg=self.c_panel, fg=self.c_text_muted, anchor="w"
        )
        self.lbl_current_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 4. Bottom Action Buttons Bar (Packed to BOTTOM before list) ──────
        btn_bar = tk.Frame(self, bg=self.c_panel, padx=16, pady=12)
        btn_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_restore_sel = tk.Button(
            btn_bar, text=tr("vault_btn_restore_selected", "✓ Restore Selected"),
            font=("Segoe UI", 9, "bold"), bg="#2563eb", fg="#ffffff",
            activebackground="#1d4ed8", activeforeground="#ffffff",
            relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.restore_selected
        )
        self.btn_restore_sel.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_browse_folder = tk.Button(
            btn_bar, text=tr("vault_btn_browse_folder", "📁 Browse Folder..."),
            font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent,
            activebackground=self.c_border, activeforeground=self.c_accent,
            relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.browse_folder
        )
        self.btn_browse_folder.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_browse = tk.Button(
            btn_bar, text=tr("vault_btn_browse_file", "▣ Browse File..."),
            font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_text_bright,
            activebackground=self.c_border, activeforeground="#ffffff",
            relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.browse_files
        )
        self.btn_browse.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_restore_all = tk.Button(
            btn_bar, text=tr("vault_btn_restore_all", "↻ Restore All"),
            font=("Segoe UI", 9), bg=self.c_card, fg=self.c_accent,
            activebackground=self.c_border, activeforeground=self.c_accent,
            relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.restore_all
        )
        self.btn_restore_all.pack(side=tk.RIGHT)

        # ── 5. Scrollable File List Container ────────────────────────────────
        list_outer = tk.Frame(self, bg=self.c_bg, padx=16, pady=4)
        list_outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(list_outer, bg=self.c_bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.c_bg)
        self._canvas_win_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(self._canvas_win_id, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

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
        """Sets all checkboxes to either checked or unchecked and refreshes visuals."""
        for var in self._item_vars.values():
            var.set(select)
        self._refresh_selection_visuals()

    def _toggle_item(self, path: str):
        """Toggles check state for a file, updating visuals and restore button counter."""
        var = self._item_vars.get(path)
        if var is not None:
            var.set(not var.get())
        self._update_row_visual(path)
        self._update_restore_btn_text()

    def _on_cb_toggle(self, path: str):
        """Called when user clicks directly on the tk.Checkbutton."""
        self._update_row_visual(path)
        self._update_restore_btn_text()

    def _update_row_visual(self, path: str):
        """Updates row background, border, and indicator icon to reflect selection state."""
        widgets = getattr(self, "_row_widgets", {}).get(path)
        if not widgets:
            return
        var = self._item_vars.get(path)
        is_selected = bool(var.get()) if var else False

        bg = "#1e3a5f" if is_selected else self.c_card
        border = "#38bdf8" if is_selected else self.c_border
        icon = "☑" if is_selected else "☐"
        icon_fg = self.c_accent if is_selected else "#64748b"

        try:
            widgets["row"].configure(bg=bg, highlightbackground=border)
            widgets["indicator"].configure(text=icon, bg=bg, fg=icon_fg)
            widgets["cb"].configure(bg=bg, activebackground=bg)
            widgets["name"].configure(bg=bg)
            widgets["cat"].configure(bg=bg)
            widgets["size"].configure(bg=bg)
        except Exception:
            pass

    def _refresh_selection_visuals(self):
        """Refreshes all visible row visuals and the restore button text."""
        if hasattr(self, "_row_widgets"):
            for path in self._row_widgets:
                self._update_row_visual(path)
        self._update_restore_btn_text()

    def _update_restore_btn_text(self):
        """Updates text on btn_restore_sel to display the count of selected files."""
        if not hasattr(self, "btn_restore_sel") or not self.btn_restore_sel:
            return
        sel_count = sum(1 for v in self._item_vars.values() if v.get())
        base_text = tr("vault_btn_restore_selected", "✓ Restore Selected")
        self.btn_restore_sel.configure(text=f"{base_text} ({sel_count})" if sel_count > 0 else base_text)

    def _display_files(self):
        """Renders file rows in scrollable frame, filtering by search query."""
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()

        for child in self.scrollable_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        query = self.entry_search.get().strip().lower() if hasattr(self, "entry_search") else ""
        filtered = [f for f in self._all_files if not query or query in f["filename"].lower()]

        if not filtered:
            lbl_empty = tk.Label(
                self.scrollable_frame, text=tr("vault_no_unregistered_files", "No unregistered files found on disk"),
                font=("Segoe UI", 10), bg=self.c_bg, fg=self.c_text_muted, pady=40
            )
            lbl_empty.pack(fill=tk.BOTH, expand=True)
            self._update_restore_btn_text()
            return

        for f_info in filtered:
            path = f_info["file_path"]
            var = self._item_vars.get(path)
            if var is None:
                var = tk.BooleanVar(master=self, value=False)
                self._item_vars[path] = var

            is_selected = bool(var.get())
            bg_color = "#1e3a5f" if is_selected else self.c_card
            border_color = "#38bdf8" if is_selected else self.c_border
            icon_text = "☑" if is_selected else "☐"
            icon_fg = self.c_accent if is_selected else "#64748b"

            row = tk.Frame(
                self.scrollable_frame, bg=bg_color, padx=10, pady=8,
                highlightthickness=1, highlightbackground=border_color, cursor="hand2"
            )
            row.pack(fill=tk.X, pady=2)

            lbl_indicator = tk.Label(
                row, text=icon_text, font=("Segoe UI", 12, "bold"),
                bg=bg_color, fg=icon_fg, cursor="hand2"
            )
            lbl_indicator.pack(side=tk.LEFT, padx=(0, 4))

            cb = tk.Checkbutton(
                row, variable=var, bg=bg_color, activebackground=bg_color,
                selectcolor="#0f172a", fg=self.c_accent, activeforeground=self.c_accent,
                cursor="hand2", command=lambda p=path: self._on_cb_toggle(p)
            )
            cb.pack(side=tk.LEFT, padx=(0, 8))

            name_lbl = tk.Label(
                row, text=f_info["filename"], font=("Segoe UI", 9, "bold"),
                bg=bg_color, fg=self.c_text_bright, anchor="w", cursor="hand2"
            )
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            cat_lbl = tk.Label(
                row, text=f"[{f_info.get('category', 'general').upper()}]",
                font=("Segoe UI", 8), bg=bg_color, fg=self.c_accent, cursor="hand2"
            )
            cat_lbl.pack(side=tk.RIGHT, padx=(6, 0))

            size_lbl = tk.Label(
                row, text=_format_size(f_info.get("size_bytes", 0)),
                font=("Segoe UI", 9), bg=bg_color, fg=self.c_text_muted, cursor="hand2"
            )
            size_lbl.pack(side=tk.RIGHT, padx=(6, 6))

            self._row_widgets[path] = {
                "row": row, "indicator": lbl_indicator, "cb": cb,
                "name": name_lbl, "cat": cat_lbl, "size": size_lbl,
            }

            for w in (row, lbl_indicator, name_lbl, cat_lbl, size_lbl):
                w.bind("<Button-1>", lambda e, p=path: self._toggle_item(p))
                w.bind("<MouseWheel>", self._on_mousewheel)
            cb.bind("<MouseWheel>", self._on_mousewheel)

        self._update_restore_btn_text()

    def browse_folder(self) -> int:
        """Prompts user to select a folder from disk and loads unregistered files from it."""
        selected_dir = filedialog.askdirectory(
            parent=self, title=tr("vault_btn_browse_folder", "📁 Browse Folder...")
        )
        if not selected_dir or not os.path.isdir(selected_dir):
            return 0

        self._current_scan_dir = selected_dir
        if hasattr(self, "lbl_current_folder") and self.lbl_current_folder:
            self.lbl_current_folder.configure(text=f"📂 {selected_dir}")

        self._all_files = scan_unregistered_disk_files(self.gui, custom_dir=selected_dir)
        self._item_vars.clear()
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()

        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=True)

        self._display_files()
        return len(self._all_files)

    def restore_selected(self) -> int:
        """Restores only files with active checkbox checked."""
        history_mgr = getattr(self.gui, "history_manager", None)
        if not history_mgr:
            self.destroy()
            return 0
        restored_count = 0
        for f_info in self._all_files:
            var = self._item_vars.get(f_info["file_path"])
            if var and var.get():
                history_mgr.add_or_update_entry(
                    url="", file_path=f_info["file_path"],
                    size_bytes=f_info.get("size_bytes", 0), status="Completed"
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
                url="", file_path=f_info["file_path"],
                size_bytes=f_info.get("size_bytes", 0), status="Completed"
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
            parent=self, title=tr("vault_btn_browse_file", "▣ Browse File...")
        )
        if not selected_files:
            return 0
        restored_count = 0
        for path in selected_files:
            if os.path.isfile(path):
                try: sz = os.path.getsize(path)
                except Exception: sz = 0
                history_mgr.add_or_update_entry(
                    url="", file_path=path, size_bytes=sz, status="Completed"
                )
                restored_count += 1
        if restored_count > 0:
            self._finalize_and_close()
        return restored_count

    def _finalize_and_close(self):
        """Refreshes Column 3 and history table, then cleanly destroys modal dialog."""
        if hasattr(self.gui, "_vault_filter_category"):
            self.gui._vault_filter_category = "all"
        if hasattr(self.gui, "refresh_history_table") and callable(self.gui.refresh_history_table):
            try: self.gui.refresh_history_table()
            except Exception: pass
        if hasattr(self.gui, "_refresh_history_table") and callable(self.gui._refresh_history_table):
            try: self.gui._refresh_history_table(force=True)
            except TypeError:
                try: self.gui._refresh_history_table()
                except Exception: pass
            except Exception: pass
        if hasattr(self.gui, "refresh_kanban_col3") and callable(self.gui.refresh_kanban_col3):
            try: self.gui.refresh_kanban_col3()
            except Exception: pass
        self.destroy()


__all__ = ["VaultRestoreModal", "scan_unregistered_disk_files"]
