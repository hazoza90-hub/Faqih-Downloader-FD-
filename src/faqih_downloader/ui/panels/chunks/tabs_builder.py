"""
ChunksTabsBuilderMixin: Tabbed consoles (Chunks table, Activity Log, Download History) and resize management.
"""
from __future__ import annotations
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from faqih_downloader.i18n import tr


class ChunksTabsBuilderMixin:
    """Provides methods for constructing the notebook container and handling column auto-resizing."""

    def _build_tabs_card(self, parent):
        """Dual Tab View: Detailed Chunk Table and Activity Console."""
        notebook = ttk.Notebook(parent, style="Custom.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Chunk Details Table
        tab_chunks = tk.Frame(notebook, bg=self.c_panel, bd=0, highlightthickness=1, highlightbackground=self.c_border, highlightcolor=self.c_border)
        notebook.add(tab_chunks, text=tr("tab_chunks", "  ▦ Chunk Segments  "))

        cols = ("id", "range", "size", "downloaded", "pct", "status")
        self.tree_chunks = ttk.Treeview(tab_chunks, columns=cols, show="headings", style="Custom.Treeview")
        self.tree_chunks.heading("id", text=tr("col_chunk_id", "ID"))
        self.tree_chunks.heading("range", text=tr("col_chunk_range", "Byte Offset Range"))
        self.tree_chunks.heading("size", text=tr("col_chunk_size", "Total Span"))
        self.tree_chunks.heading("downloaded", text=tr("col_chunk_downloaded", "Downloaded"))
        self.tree_chunks.heading("pct", text=tr("col_chunk_pct", "Progress"))
        self.tree_chunks.heading("status", text=tr("col_chunk_status", "Status"))

        scale = getattr(self, "dpi_scale", 1.0)
        self.tree_chunks.column("id", width=max(50, int(60 * scale)), minwidth=40, anchor="center", stretch=True)
        self.tree_chunks.column("range", width=max(200, int(250 * scale)), minwidth=180, anchor="w", stretch=True)
        self.tree_chunks.column("size", width=max(90, int(110 * scale)), minwidth=80, anchor="e", stretch=True)
        self.tree_chunks.column("downloaded", width=max(90, int(110 * scale)), minwidth=80, anchor="e", stretch=True)
        self.tree_chunks.column("pct", width=max(80, int(90 * scale)), minwidth=70, anchor="center", stretch=True)
        self.tree_chunks.column("status", width=max(100, int(120 * scale)), minwidth=90, anchor="center", stretch=True)

        scroll_tree = ttk.Scrollbar(tab_chunks, orient="vertical", command=self.tree_chunks.yview)
        self.tree_chunks.configure(yscrollcommand=scroll_tree.set)
        self.tree_chunks.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_tree.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_tree_context_menu()
        self.tree_chunks.bind("<Button-3>", self._show_tree_context_menu)
        self.tree_chunks.bind("<Button-2>", self._show_tree_context_menu)
        self.tree_chunks.bind("<Configure>", self._on_tree_chunks_configure)

        # Tab 2: Activity Console Log
        tab_logs = tk.Frame(notebook, bg=self.c_panel, bd=0, highlightthickness=1, highlightbackground=self.c_border, highlightcolor=self.c_border)
        notebook.add(tab_logs, text=tr("tab_logs", "  ▤ Live Activity Log  "))

        self.txt_log = tk.Text(
            tab_logs,
            bg=self.c_input_bg,
            fg=self.c_text_bright,
            insertbackground=self.c_accent,
            font=("Consolas", 9),
            relief="flat",
            wrap="word",
            padx=8,
            pady=8
        )
        scroll_log = ttk.Scrollbar(tab_logs, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll_log.set)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_log.pack(side=tk.RIGHT, fill=tk.Y)

        self.notebook = notebook

        # Tab 3: Download History Manager
        tab_history = tk.Frame(notebook, bg=self.c_panel, bd=0, highlightthickness=1, highlightbackground=self.c_border, highlightcolor=self.c_border)
        notebook.add(tab_history, text=tr("tab_history", "  ☰ Download History  "))

        # Top Toolbar
        hist_toolbar = tk.Frame(tab_history, bg=self.c_panel, padx=8, pady=6)
        hist_toolbar.pack(side=tk.TOP, fill=tk.X)

        self.lbl_filter = tk.Label(hist_toolbar, text=tr("lbl_filter"), font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_text_bright)
        self.lbl_filter.pack(side=tk.LEFT, padx=(0, 6))

        categories = [
            tr("cat_all", "All Categories"),
            tr("cat_video", "Video"),
            tr("cat_audio", "Audio"),
            tr("cat_programs", "Programs"),
            tr("cat_compressed", "Compressed"),
            tr("cat_documents", "Documents"),
            tr("cat_images", "Images"),
            tr("cat_general", "General"),
        ]
        self.combo_history_filter = ttk.Combobox(
            hist_toolbar,
            values=categories,
            state="readonly",
            width=15
        )
        self.combo_history_filter.set(categories[0])
        self.combo_history_filter.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_history_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_history_table())

        btn_font = ("Segoe UI", 8)
        self.btn_hist_open = tk.Button(
            hist_toolbar,
            text=tr("btn_hist_open", "↗ Open File"),
            command=self._history_open_selected_file,
            font=btn_font,
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_open.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hist_folder = tk.Button(
            hist_toolbar,
            text=tr("btn_hist_folder", "⋯ Open Folder"),
            command=self._history_open_selected_folder,
            font=btn_font,
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_folder.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hist_redownload = tk.Button(
            hist_toolbar,
            text=tr("btn_hist_redownload", "↻ Resume / Retry"),
            command=self._history_redownload_selected,
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light,
            fg=self.c_accent,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_redownload.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hist_quality = tk.Button(
            hist_toolbar,
            text=tr("ctx_redownload_quality", "⚙ Re-Download Quality"),
            command=self._history_redownload_with_quality,
            font=btn_font,
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_quality.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hist_remove = tk.Button(
            hist_toolbar,
            text=tr("btn_hist_remove", "✕ Remove"),
            command=self._history_remove_selected,
            font=btn_font,
            bg=self.c_panel_light,
            fg=self.c_text_muted,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_remove.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hist_clear = tk.Button(
            hist_toolbar,
            text=tr("btn_hist_clear", "⌫ Clear All"),
            command=self._history_clear_all,
            font=btn_font,
            bg=self.c_panel_light,
            fg="#ef4444",
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=8,
            pady=2
        )
        self.btn_hist_clear.pack(side=tk.LEFT, padx=(0, 6))

        # History Treeview Frame
        tree_hist_frame = tk.Frame(tab_history, bg=self.c_panel)
        tree_hist_frame.pack(fill=tk.BOTH, expand=True)

        cols_hist = ("category", "filename", "size", "status", "date", "path")
        self.tree_history = ttk.Treeview(tree_hist_frame, columns=cols_hist, show="headings", style="Custom.Treeview")
        self.tree_history.heading("category", text=tr("col_hist_category", "Category"))
        self.tree_history.heading("filename", text=tr("col_hist_filename", "File Name"))
        self.tree_history.heading("size", text=tr("col_hist_size", "Size"))
        self.tree_history.heading("status", text=tr("col_hist_status", "Status"))
        self.tree_history.heading("date", text=tr("col_hist_date", "Date Added"))
        self.tree_history.heading("path", text=tr("col_hist_path", "Saved Location"))

        self.tree_history.column("category", width=max(80, int(95 * scale)), minwidth=70, anchor="center", stretch=True)
        self.tree_history.column("filename", width=max(180, int(220 * scale)), minwidth=140, anchor="w", stretch=True)
        self.tree_history.column("size", width=max(80, int(90 * scale)), minwidth=70, anchor="e", stretch=True)
        self.tree_history.column("status", width=max(80, int(90 * scale)), minwidth=70, anchor="center", stretch=True)
        self.tree_history.column("date", width=max(120, int(135 * scale)), minwidth=100, anchor="center", stretch=True)
        self.tree_history.column("path", width=max(220, int(260 * scale)), minwidth=180, anchor="w", stretch=True)

        scroll_hist = ttk.Scrollbar(tree_hist_frame, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=scroll_hist.set)
        self.tree_history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_hist.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_history_context_menu()
        self.tree_history.bind("<Button-3>", self._show_history_context_menu)
        self.tree_history.bind("<Button-2>", self._show_history_context_menu)
        self.tree_history.bind("<Double-Button-1>", lambda e: self._history_open_selected_file())
        self.tree_history.bind("<Configure>", self._on_tree_history_configure)

        self._refresh_history_table()

    def _on_tree_chunks_configure(self, event):
        """Proportionally distributes tree_chunks table width across columns when enlarged or maximized."""
        w = getattr(event, "width", 0)
        if w > 600:
            if getattr(self, "_last_chunks_configured_w", None) == w:
                return
            self._last_chunks_configured_w = w
            avail_w = w - 4
            self.tree_chunks.column("id", width=max(50, int(avail_w * 0.08)))
            self.tree_chunks.column("range", width=max(200, int(avail_w * 0.34)))
            self.tree_chunks.column("size", width=max(90, int(avail_w * 0.15)))
            self.tree_chunks.column("downloaded", width=max(90, int(avail_w * 0.15)))
            self.tree_chunks.column("pct", width=max(80, int(avail_w * 0.12)))
            self.tree_chunks.column("status", width=max(100, int(avail_w * 0.16)))
        else:
            self._last_chunks_configured_w = None

    def _on_tree_history_configure(self, event):
        """Proportionally distributes tree_history table width across columns when enlarged or maximized."""
        w = getattr(event, "width", 0)
        if w > 600:
            if getattr(self, "_last_history_configured_w", None) == w:
                return
            self._last_history_configured_w = w
            avail_w = w - 4
            self.tree_history.column("category", width=max(80, int(avail_w * 0.10)))
            self.tree_history.column("filename", width=max(180, int(avail_w * 0.25)))
            self.tree_history.column("size", width=max(80, int(avail_w * 0.10)))
            self.tree_history.column("status", width=max(80, int(avail_w * 0.10)))
            self.tree_history.column("date", width=max(120, int(avail_w * 0.15)))
            self.tree_history.column("path", width=max(220, int(avail_w * 0.30)))
        else:
            self._last_history_configured_w = None
