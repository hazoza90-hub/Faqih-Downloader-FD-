"""
KanbanPanelMixin: 3-Column dynamic pipeline workspace for Smart Download (SD) v2.0.2.
"""
from __future__ import annotations

import os
from typing import Optional, Any, List, Dict

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import is_test_environment
from faqih_downloader.utils.file_ops import open_downloaded_file, open_containing_folder
from faqih_downloader.utils.window_effects import draw_rounded_rect, draw_glow_border, RoundedGlassCard
from faqih_downloader.ui.components.led_matrix import LedEqualizerMatrix
from faqih_downloader.ui.panels.kanban_cards import (
    create_empty_state,
    build_queued_card,
    build_vault_card,
    draw_neon_progress_bar,
    build_active_card_shell,
)
from faqih_downloader.ui.panels.kanban_vault_helpers import (
    filter_vault_entries,
    build_vault_filter_pills,
    show_vault_context_menu,
    build_load_more_button,
    setup_vault_scroll_view,
    render_vault_view,
    clear_completed_vault_entries,
    restore_vault_entries_from_disk,
    open_vault_restore_dialog,
    delete_vault_entry_with_confirm,
)
from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin


class KanbanPanelMixin(KanbanActiveColumnMixin):
    """Provides the 3-column Kanban pipeline workspace and 100% dynamic card management."""

    def _build_kanban_pipeline(self, parent: Any):
        """Constructs the 3-column layout."""
        self.kanban_container = tk.Frame(parent, bg="#0b0e14", padx=10, pady=8)
        self.kanban_container.pack(fill=tk.BOTH, expand=True)

        # 3 Columns grid configuration
        self.kanban_container.columnconfigure(0, weight=30, uniform="col")
        self.kanban_container.columnconfigure(1, weight=40, uniform="col")
        self.kanban_container.columnconfigure(2, weight=30, uniform="col")
        self.kanban_container.rowconfigure(0, weight=1)

        # Internal tracking
        self._parsing_links: List[str] = getattr(self, "_parsing_links", [])
        self._staged_links: List[Dict[str, Any]] = getattr(self, "_staged_links", [])
        self._active_stream_live = False
        self._vault_scroll_steps = 0
        self._vault_scroll_timer = None

        # ── Column 1: Queued & Parsing ───────────────────────────────────────
        self._build_col1_queued(self.kanban_container)

        # ── Column 2: Active Turbo Streams ───────────────────────────────────
        self._build_col2_active(self.kanban_container)

        # ── Column 3: Completed Vault ────────────────────────────────────────
        self._build_col3_vault(self.kanban_container)

        # Initial dynamic population
        self.refresh_kanban_col1()
        self.reset_kanban_active_stream()
        self.refresh_kanban_col3()

    # ══════════════════════════════════════════════════════════════════════════
    # COLUMN 1: QUEUED & PARSING (100% Dynamic)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_col1_queued(self, parent: Any):
        col_frame = tk.Frame(parent, bg="#0b0e14", padx=4, pady=2)
        col_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Header
        hdr = tk.Frame(col_frame, bg="#0b0e14")
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.lbl_col1_title = tk.Label(
            hdr,
            text=f"{tr('pipeline_col_queued', 'Queued & Parsing')} (0)",
            font=("Segoe UI", 10, "bold"),
            bg="#0b0e14",
            fg="#94a3b8"
        )
        self.lbl_col1_title.pack(side=tk.LEFT)

        # Cards Container
        self.cards_col1_container = tk.Frame(col_frame, bg="#0b0e14")
        self.cards_col1_container.pack(fill=tk.BOTH, expand=True)

    def refresh_kanban_col1(self):
        """Dynamically re-renders Column 1 based on real parsing tasks, staged links, and download queue."""
        if not hasattr(self, "cards_col1_container") or not self.cards_col1_container.winfo_exists():
            return

        for child in self.cards_col1_container.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        parsing = getattr(self, "_parsing_links", [])
        staged = getattr(self, "_staged_links", [])
        queued = getattr(self, "_download_queue", [])
        total = len(parsing) + len(staged) + len(queued)

        if hasattr(self, "lbl_col1_title") and self.lbl_col1_title.winfo_exists():
            self.lbl_col1_title.configure(text=f"{tr('pipeline_col_queued', 'Queued & Parsing')} ({total})")

        if total == 0:
            create_empty_state(
                self.cards_col1_container,
                icon="⏳",
                title=tr("pipeline_empty_queued", "No queued links"),
                subtitle=tr("status_ready", "Ready"),
                height=140
            )
            return

        from faqih_downloader.ui.panels.kanban_staged_helpers import render_kanban_col1_content
        render_kanban_col1_content(self.cards_col1_container, self, parsing, staged, queued)

    def stage_probed_link_in_col1(self, info_dict: Dict[str, Any]):
        """Adds or updates a probed download link card in Column 1."""
        def _do():
            if not hasattr(self, "_staged_links"):
                self._staged_links = []
            u = info_dict.get("url")
            self._staged_links = [it for it in self._staged_links if it.get("url") != u]
            self._staged_links.insert(0, info_dict)
            self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        elif hasattr(self, "after"):
            self.after(0, _do)
        else:
            _do()

    def remove_staged_link(self, url: str):
        """Removes a staged download link card from Column 1."""
        def _do():
            if hasattr(self, "_staged_links"):
                self._staged_links = [it for it in self._staged_links if it.get("url") != url]
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        elif hasattr(self, "after"):
            self.after(0, _do)
        else:
            _do()

    def add_parsing_link(self, url: str):
        """Notifies Column 1 that a link metadata extraction has commenced."""
        def _do():
            if not hasattr(self, "_parsing_links"):
                self._parsing_links = []
            if url and url not in self._parsing_links:
                self._parsing_links.append(url)
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        else:
            _do()

    def remove_parsing_link(self, url: str):
        """Removes a link from the active parsing indicator list."""
        def _do():
            if hasattr(self, "_parsing_links") and url in self._parsing_links:
                self._parsing_links.remove(url)
                self.refresh_kanban_col1()
        if hasattr(self, "dispatch_to_main_thread") and callable(self.dispatch_to_main_thread):
            self.dispatch_to_main_thread(_do)
        else:
            _do()

    # ══════════════════════════════════════════════════════════════════════════
    # COLUMN 3: COMPLETED VAULT (100% Dynamic from History)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_col3_vault(self, parent: Any):
        col_frame = tk.Frame(parent, bg="#0b0e14", padx=4, pady=2)
        col_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        # Header: "Completed Vault (N)" + Clear Button
        hdr = tk.Frame(col_frame, bg="#0b0e14")
        hdr.pack(fill=tk.X, pady=(0, 4))
        self.lbl_col3_title = tk.Label(
            hdr,
            text=f"{tr('pipeline_col_vault', 'Completed Vault')} (0)",
            font=("Segoe UI", 10, "bold"),
            bg="#0b0e14",
            fg="#94a3b8"
        )
        self.lbl_col3_title.pack(side=tk.LEFT)

        self.btn_clear_vault = tk.Label(
            hdr, text=tr("vault_btn_clear", "✕ Clear"), font=("Segoe UI", 8, "bold"),
            bg="#0b0e14", fg="#64748b", cursor="hand2"
        )
        self.btn_clear_vault.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_clear_vault.bind("<Enter>", lambda e: self.btn_clear_vault.configure(fg="#ef4444"))
        self.btn_clear_vault.bind("<Leave>", lambda e: self.btn_clear_vault.configure(fg="#64748b"))
        self.btn_clear_vault.bind("<Button-1>", lambda e: self._on_clear_completed_vault())

        self.btn_restore_vault = tk.Label(
            hdr, text=tr("vault_btn_restore", "↻ Restore"), font=("Segoe UI", 8, "bold"),
            bg="#0b0e14", fg="#64748b", cursor="hand2"
        )
        self.btn_restore_vault.pack(side=tk.RIGHT, padx=(0, 6))
        self.btn_restore_vault.bind("<Enter>", lambda e: self.btn_restore_vault.configure(fg="#38bdf8"))
        self.btn_restore_vault.bind("<Leave>", lambda e: self.btn_restore_vault.configure(fg="#64748b"))
        self.btn_restore_vault.bind("<Button-1>", lambda e: self._on_restore_vault_from_disk())

        # Category Filter Pills Container
        self.vault_pills_container = tk.Frame(col_frame, bg="#0b0e14")
        self.vault_pills_container.pack(fill=tk.X, pady=(0, 4))

        # Scrollable container setup
        body = tk.Frame(col_frame, bg="#0b0e14")
        body.pack(fill=tk.BOTH, expand=True)
        cv, container = setup_vault_scroll_view(col_frame, body, panel=self)
        self.vault_cards_canvas = cv
        self.vault_cards_container = container

    def refresh_kanban_col3(self):
        """Dynamically populates Column 3 with real completed downloads from DownloadHistoryManager."""
        if not hasattr(self, "vault_cards_container") or not self.vault_cards_container.winfo_exists():
            return

        if hasattr(self, "btn_clear_vault") and self.btn_clear_vault.winfo_exists():
            self.btn_clear_vault.configure(text=tr("vault_btn_clear", "✕ Clear"))
        if hasattr(self, "btn_restore_vault") and self.btn_restore_vault.winfo_exists():
            self.btn_restore_vault.configure(text=tr("vault_btn_restore", "↻ Restore"))

        if hasattr(self, "vault_pills_container") and self.vault_pills_container.winfo_exists():
            for c in self.vault_pills_container.winfo_children():
                try: c.destroy()
                except Exception: pass
            pills = build_vault_filter_pills(
                self.vault_pills_container,
                getattr(self, "_vault_filter_category", "all"),
                self._on_vault_category_select
            )
            pills.pack(fill=tk.X)

        entries = []
        if hasattr(self, "history_manager") and self.history_manager:
            entries = [
                e for e in self.history_manager.get_entries()
                if str(e.get("status", "")).strip().lower() in ("completed", "مكتمل", "success")
            ]

        def _empty(cont):
            create_empty_state(cont, icon="📁", title=tr("pipeline_empty_vault", "No completed downloads yet"), subtitle="", height=140)

        callbacks = {
            "open_file": self._open_vault_file,
            "open_folder": self._open_vault_folder,
            "delete_entry": self._on_delete_vault_entry,
            "context_menu": self._on_vault_context_menu,
            "load_more": self._on_vault_load_more,
        }

        curr_cat = getattr(self, "_vault_filter_category", "all")
        limit = getattr(self, "_vault_display_limit", 25)
        total = render_vault_view(
            self.vault_cards_container, entries, curr_cat, limit, callbacks,
            card_builder=build_vault_card, empty_builder=_empty, load_more_builder=build_load_more_button
        )
        if hasattr(self, "lbl_col3_title") and self.lbl_col3_title.winfo_exists():
            self.lbl_col3_title.configure(text=f"{tr('pipeline_col_vault', 'Completed Vault')} ({total})")

    def _on_vault_category_select(self, cat: str):
        self._vault_filter_category, self._vault_display_limit = cat, 25
        self.refresh_kanban_col3()

    def _on_vault_load_more(self):
        self._vault_display_limit = getattr(self, "_vault_display_limit", 25) + 25
        self.refresh_kanban_col3()

    def _on_vault_context_menu(self, event: Any, entry: Dict[str, Any]):
        callbacks = {
            "open_file": self._open_vault_file, "open_folder": self._open_vault_folder,
            "delete_entry": self._on_delete_vault_entry, "delete_from_disk": self._on_delete_vault_from_disk,
            "redownload": self._on_vault_redownload, "gui": self,
        }
        show_vault_context_menu(event, entry, getattr(self, "root", None), callbacks)

    def _on_vault_redownload(self, url: str):
        if url and hasattr(self, "entry_url") and self.entry_url:
            try:
                self.entry_url.delete(0, tk.END)
                self.entry_url.insert(0, url)
            except Exception: pass
            if hasattr(self, "_on_start_download") and callable(self._on_start_download):
                self._on_start_download()

    def _on_delete_vault_from_disk(self, entry: Dict[str, Any]):
        file_path = entry.get("file_path") or ""
        if file_path:
            try:
                if os.path.isfile(file_path): os.remove(file_path)
            except Exception: pass
        self._on_delete_vault_entry(entry, skip_confirm=True)

    def _on_clear_completed_vault(self):
        clear_completed_vault_entries(self)

    def _on_restore_vault_from_disk(self, open_dialog: bool = False):
        if is_test_environment() and not open_dialog:
            restore_vault_entries_from_disk(self)
        else:
            open_vault_restore_dialog(self)

    def _on_delete_vault_entry(self, entry: Dict[str, Any], skip_confirm: bool = False):
        delete_vault_entry_with_confirm(self, entry, skip_confirm=skip_confirm)

    def _open_vault_file(self, file_path_or_name: str):
        if file_path_or_name: open_downloaded_file(file_path_or_name)

    def _open_vault_folder(self, file_path_or_name: str):
        if file_path_or_name: open_containing_folder(file_path_or_name)

    def on_kanban_download_completed(self, path: str, total_bytes: int):
        """Adds dynamically completed download to Completed Vault and resets active stream."""
        self.reset_kanban_active_stream()
        self.refresh_kanban_col3()

    def _on_vault_mousewheel(self, event: Any):
        """Smoothly scrolls Completed Vault canvas with 10ms eased interpolation."""
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists() or not getattr(event, "delta", None):
            return
        notch = int(-1 * (event.delta / 120))
        if notch == 0:
            return
        steps = getattr(self, "_vault_scroll_steps", 0) + notch * 14
        self._vault_scroll_steps = max(-70, min(70, steps))
        if getattr(self, "_vault_scroll_timer", None) is None:
            self._step_vault_smooth_scroll()

    def _step_vault_smooth_scroll(self):
        """Performs 10ms interpolation step for vault canvas smooth scrolling."""
        self._vault_scroll_timer = None
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists():
            self._vault_scroll_steps = 0
            return
        steps = getattr(self, "_vault_scroll_steps", 0)
        if steps == 0:
            return
        step = int(steps * 0.35)
        if step == 0:
            step = 1 if steps > 0 else -1
        try:
            cv.yview_scroll(step, "units")
            self._vault_scroll_steps -= step
            if self._vault_scroll_steps != 0:
                self._vault_scroll_timer = cv.after(10, self._step_vault_smooth_scroll)
        except Exception:
            self._vault_scroll_steps = 0

    def _on_global_col3_wheel(self, event: Any):
        """Global handler forwarding mousewheel to Completed Vault when pointer is over vault."""
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists() or not getattr(event, "delta", None):
            return
        try:
            target = cv.winfo_containing(event.x_root, event.y_root)
            curr = target
            while curr is not None:
                if curr in (cv, getattr(self, "vault_cards_container", None), getattr(self, "kanban_container", None)):
                    self._on_vault_mousewheel(event)
                    return
                curr = getattr(curr, "master", None)
        except Exception:
            pass


__all__ = ["KanbanPanelMixin", "KanbanActiveColumnMixin"]
