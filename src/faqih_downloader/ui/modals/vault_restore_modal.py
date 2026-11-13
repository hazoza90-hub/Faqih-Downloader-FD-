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
from typing import Any, List, Dict, Optional, Tuple

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
        self._item_vars: Dict[str, tk.BooleanVar] = {}
        self._row_widgets: Dict[str, Dict[str, Any]] = {}
        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=False)

        self._build_ui()
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

    def _schedule_scrollregion_update(self, event=None):
        """Debounces canvas scrollregion updates so rapid additions batch bbox('all')."""
        if getattr(self, "_scrollregion_pending", False):
            return
        self._scrollregion_pending = True
        try:
            self.after_idle(self._apply_scrollregion)
        except Exception:
            self._scrollregion_pending = False

    def _apply_scrollregion(self):
        self._scrollregion_pending = False
        if getattr(self, "_closing", False):
            return
        try:
            if self.winfo_exists() and hasattr(self, "canvas") and self.canvas.winfo_exists():
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _get_scroll_bounds(self) -> Tuple[float, float]:
        try:
            if hasattr(self, "canvas") and self.canvas.winfo_exists() and hasattr(self.canvas, "yview"):
                t, b = self.canvas.yview()
                return float(t), float(b)
            if hasattr(self, "scrollbar") and self.scrollbar.winfo_exists():
                t, b = self.scrollbar.get()
                return float(t), float(b)
        except Exception:
            pass
        return 0.0, 1.0

    def _on_mousewheel(self, event):
        """Scrolls canvas smoothly with instant direction reversal and edge clamping."""
        if getattr(self, "_closing", False):
            return
        try:
            if not self.winfo_exists() or not hasattr(self, "canvas") or not self.canvas.winfo_exists():
                return
            top, btm = self._get_scroll_bounds()
            if top <= 0.0 and btm >= 1.0:
                self._scroll_steps_remaining = 0
                return
            notch = int(-1 * (event.delta / 120))
            if notch == 0:
                return
            if (notch < 0 and self._scroll_steps_remaining > 0) or (notch > 0 and self._scroll_steps_remaining < 0):
                self._scroll_steps_remaining = 0
            if (notch < 0 and top <= 0.0) or (notch > 0 and btm >= 1.0):
                self._scroll_steps_remaining = 0
                return
            self._scroll_steps_remaining = max(-90, min(90, self._scroll_steps_remaining + notch * 18))
            if self._scroll_timer_id is None:
                self._step_smooth_scroll()
        except Exception:
            pass

    def _step_smooth_scroll(self):
        """Executes smooth 10ms eased interpolation step for mousewheel scrolling."""
        self._scroll_timer_id = None
        if getattr(self, "_closing", False):
            self._scroll_steps_remaining = 0
            return
        try:
            if not self.winfo_exists() or not hasattr(self, "canvas") or not self.canvas.winfo_exists():
                self._scroll_steps_remaining = 0
                return
            top, btm = self._get_scroll_bounds()
            if top <= 0.0 and btm >= 1.0 or self._scroll_steps_remaining == 0:
                self._scroll_steps_remaining = 0
                return
            step = int(self._scroll_steps_remaining * 0.35) or (1 if self._scroll_steps_remaining > 0 else -1)
            if (step < 0 and top <= 0.0) or (step > 0 and btm >= 1.0):
                self._scroll_steps_remaining = 0
                return
            self.canvas.yview_scroll(step, "units")
            self._scroll_steps_remaining -= step
            if self._scroll_steps_remaining != 0:
                self._scroll_timer_id = self.after(10, self._step_smooth_scroll)
        except Exception:
            self._scroll_steps_remaining = 0

    def _on_search_changed(self, event=None):
        """Reset pagination limit and re-render files on live search query edit."""
        self._display_limit = 40
        self._display_files()

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
        """Updates row background, border, and checkbox to reflect selection state."""
        widgets = getattr(self, "_row_widgets", {}).get(path)
        if not widgets:
            return
        var = self._item_vars.get(path)
        is_selected = bool(var.get()) if var else False
        bg = "#1e3a5f" if is_selected else self.c_card
        border = "#38bdf8" if is_selected else self.c_border
        try:
            widgets["row"].configure(bg=bg, highlightbackground=border)
            widgets["cb"].configure(bg=bg, activebackground=bg)
            for k in ("name", "cat", "size"):
                widgets[k].configure(bg=bg)
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

    def _append_file_rows(self, files_slice: List[Dict[str, Any]]):
        """Renders a batch of file rows in scrollable frame."""
        for f_info in files_slice:
            path = f_info["file_path"]
            var = self._item_vars.get(path)
            if var is None:
                var = tk.BooleanVar(master=self, value=False)
                self._item_vars[path] = var

            is_selected = bool(var.get())
            bg_color = "#1e3a5f" if is_selected else self.c_card
            border_color = "#38bdf8" if is_selected else self.c_border

            row = tk.Frame(
                self.scrollable_frame, bg=bg_color, padx=10, pady=8,
                highlightthickness=1, highlightbackground=border_color, cursor="hand2"
            )
            row.pack(fill=tk.X, pady=2)

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
                "row": row, "cb": cb, "name": name_lbl, "cat": cat_lbl, "size": size_lbl,
            }

            for w in (row, name_lbl, cat_lbl, size_lbl):
                w.bind("<Button-1>", lambda e, p=path: self._toggle_item(p))

    def _create_load_more_button(self, filtered: List[Dict[str, Any]], remaining: int):
        """Creates an elegant load more button at the bottom of the scrollable frame."""
        btn_txt = f"⬇ {tr('vault_load_more', 'Show More')} ({remaining} {tr('vault_remaining', 'remaining')})"
        self._btn_load_more = tk.Button(
            self.scrollable_frame, text=btn_txt, font=("Segoe UI", 9, "bold"),
            bg=self.c_card, fg=self.c_accent_blue, activebackground=self.c_border,
            activeforeground="#ffffff", relief=tk.FLAT, padx=14, pady=8, cursor="hand2",
            command=lambda: self._on_load_more(filtered)
        )
        self._btn_load_more.pack(fill=tk.X, pady=6)

    def _on_load_more(self, filtered: List[Dict[str, Any]]):
        """Loads and appends the next batch of files without recreating previous rows."""
        if hasattr(self, "_btn_load_more") and self._btn_load_more:
            try:
                self._btn_load_more.destroy()
            except Exception:
                pass
            self._btn_load_more = None

        old_limit = self._display_limit
        self._display_limit += 40
        next_slice = filtered[old_limit:self._display_limit]
        self._append_file_rows(next_slice)

        remaining = len(filtered) - self._display_limit
        if remaining > 0:
            self._create_load_more_button(filtered, remaining)

        self._schedule_scrollregion_update()

    def _display_files(self):
        """Renders paginated file rows in scrollable frame, filtering by search query."""
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()

        for child in self.scrollable_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._btn_load_more = None

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

        visible = filtered[:self._display_limit]
        self._append_file_rows(visible)

        remaining = len(filtered) - self._display_limit
        if remaining > 0:
            self._create_load_more_button(filtered, remaining)

        self._update_restore_btn_text()
        self._schedule_scrollregion_update()

    def browse_folder(self) -> int:
        """Prompts user to select a folder from disk and loads unregistered files from it."""
        selected_dir = filedialog.askdirectory(parent=self, title=tr("vault_btn_browse_folder", "▤ Browse Folder..."))
        if not selected_dir or not os.path.isdir(selected_dir):
            return 0
        self._current_scan_dir = selected_dir
        if hasattr(self, "lbl_current_folder") and self.lbl_current_folder:
            self.lbl_current_folder.configure(text=f"📂 {selected_dir}")
            try: self.update_idletasks()
            except Exception: pass

        self._all_files = scan_unregistered_disk_files(self.gui, custom_dir=selected_dir)
        self._item_vars.clear()
        if hasattr(self, "_row_widgets"):
            self._row_widgets.clear()
        for f_info in self._all_files:
            self._item_vars[f_info["file_path"]] = tk.BooleanVar(master=self, value=False)
        self._display_limit = 40
        self._display_files()
        return len(self._all_files)

    def _batch_add_entries(self, items: List[Tuple[str, int]]) -> int:
        """Adds a batch of files to history_manager efficiently with a single flush."""
        hm = getattr(self.gui, "history_manager", None)
        if not hm or not items:
            return 0
        added = 0
        for path, sz in items:
            try:
                hm.add_or_update_entry(url="", file_path=path, size_bytes=sz, status="Completed", save=False)
            except TypeError:
                hm.add_or_update_entry(url="", file_path=path, size_bytes=sz, status="Completed")
            added += 1
        for s_fn in ("_save_entries", "save_entries", "save"):
            fn = getattr(hm, s_fn, None)
            if callable(fn):
                try: fn(); break
                except Exception: pass
        return added

    def restore_selected(self) -> int:
        """Restores only files with active checkbox checked."""
        items = [
            (f["file_path"], f.get("size_bytes", 0))
            for f in self._all_files
            if self._item_vars.get(f["file_path"]) and self._item_vars[f["file_path"]].get()
        ]
        count = self._batch_add_entries(items)
        self._finalize_and_close()
        return count

    def restore_all(self) -> int:
        """Restores all discovered files regardless of filter or checkbox state."""
        items = [(f["file_path"], f.get("size_bytes", 0)) for f in self._all_files]
        count = self._batch_add_entries(items)
        self._finalize_and_close()
        return count

    def browse_files(self) -> int:
        """Prompts user to select arbitrary files from disk and adds them to history."""
        selected = filedialog.askopenfilenames(parent=self, title=tr("vault_btn_browse_file", "▣ Browse File..."))
        if not selected:
            return 0
        items = [(p, os.path.getsize(p) if os.path.isfile(p) else 0) for p in selected if os.path.isfile(p)]
        count = self._batch_add_entries(items)
        if count > 0:
            self._finalize_and_close()
        return count

    def _finalize_and_close(self):
        """Refreshes Column 3 and history table, then cleanly destroys modal dialog."""
        if hasattr(self.gui, "_vault_filter_category"):
            self.gui._vault_filter_category = "all"
        for fn_name in ("refresh_history_table", "refresh_kanban_col3"):
            fn = getattr(self.gui, fn_name, None)
            if callable(fn):
                try: fn()
                except Exception: pass
        if hasattr(self.gui, "_refresh_history_table") and callable(self.gui._refresh_history_table):
            try: self.gui._refresh_history_table(force=True)
            except Exception:
                try: self.gui._refresh_history_table()
                except Exception: pass
        self.destroy()


__all__ = ["VaultRestoreModal", "scan_unregistered_disk_files"]
