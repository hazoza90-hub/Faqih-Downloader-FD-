"""
ConfirmModalWidgetsMixin: UI component builders for DownloadConfirmationModal.
Constructs confirmation and progress views, headers, cards, and button panels.
"""
from __future__ import annotations

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from ...locales.i18n import tr


class ConfirmModalWidgetsMixin:
    """Mixin containing UI structure builders for DownloadConfirmationModal."""

    def _build_ui(self):
        # Outer border
        outer = tk.Frame(self, bg=self.c_border, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self.body = tk.Frame(outer, bg=self.c_bg, padx=18, pady=16)
        self.body.pack(fill=tk.BOTH, expand=True)

        # Build sub-views
        self._build_confirmation_view()
        self._build_progress_view()

    def _build_confirmation_view(self):
        """View 1: Download Confirmation View (Initial View)."""
        self.frame_confirmation = tk.Frame(self.body, bg=self.c_bg)
        self.frame_confirmation.pack(fill=tk.BOTH, expand=True)

        # Header Title row
        hdr_frame = tk.Frame(self.frame_confirmation, bg=self.c_bg)
        hdr_frame.pack(fill=tk.X, pady=(0, 10))

        lbl_icon = tk.Label(hdr_frame, text="⬇", font=("Segoe UI", 16), bg=self.c_bg, fg=self.c_accent)
        lbl_icon.pack(side=tk.LEFT, padx=(0, 8))

        lbl_title = tk.Label(
            hdr_frame, text=tr("modal_confirm_title_header", "DOWNLOAD FILE INFO"),
            font=("Segoe UI", 11, "bold"), bg=self.c_bg, fg=self.c_accent, anchor="w"
        )
        lbl_title.pack(side=tk.LEFT)

        lbl_sub = tk.Label(
            hdr_frame, text=tr("modal_confirm_sub", "SD Smart Interception"),
            font=("Segoe UI", 8), bg=self.c_bg, fg=self.c_text_muted, anchor="e"
        )
        lbl_sub.pack(side=tk.RIGHT)

        # Details Card
        card = tk.Frame(self.frame_confirmation, bg=self.c_panel, padx=14, pady=10, highlightbackground=self.c_border, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # 1. URL Row
        url_frame = tk.Frame(card, bg=self.c_panel)
        url_frame.pack(fill=tk.X, pady=(0, 6))

        lbl_url = tk.Label(url_frame, text=tr("lbl_url", "URL:"), font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_text_muted, width=9, anchor="w")
        lbl_url.pack(side=tk.LEFT)

        self.entry_url = tk.Entry(
            url_frame, font=("Segoe UI", 9), bg=self.c_input_bg, fg=self.c_text_bright,
            insertbackground=self.c_accent, relief="flat", highlightbackground=self.c_border, highlightthickness=1
        )
        self.entry_url.insert(0, self.url)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # 2. File details row: Category and Filename
        info_row = tk.Frame(card, bg=self.c_panel)
        info_row.pack(fill=tk.X, pady=(0, 6))

        cat_box = tk.Frame(info_row, bg=self.c_panel_light, padx=8, pady=3, highlightbackground=self.c_border, highlightthickness=1)
        cat_box.pack(side=tk.LEFT, padx=(0, 12))

        self.lbl_category_val = tk.Label(
            cat_box, text=f"{self.icon}  {self.category}", font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light, fg=self.c_accent
        )
        self.lbl_category_val.pack()

        fn_frame = tk.Frame(info_row, bg=self.c_panel)
        fn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_fn_title = tk.Label(fn_frame, text=tr("modal_file_name", "File Name:"), font=("Segoe UI", 8), bg=self.c_panel, fg=self.c_text_muted, anchor="w")
        lbl_fn_title.pack(anchor="w")

        self.lbl_filename_val = tk.Label(
            fn_frame, text=self.file_name, font=("Segoe UI", 9, "bold"),
            bg=self.c_panel, fg=self.c_text_bright, anchor="w"
        )
        self.lbl_filename_val.pack(anchor="w")

        # 3. Save Destination Row
        dest_frame = tk.Frame(card, bg=self.c_panel)
        dest_frame.pack(fill=tk.X, pady=(0, 6))

        lbl_dest = tk.Label(dest_frame, text=tr("modal_save_to", "Save To:"), font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_text_muted, width=9, anchor="w")
        lbl_dest.pack(side=tk.LEFT)

        self.entry_dest = tk.Entry(
            dest_frame, font=("Segoe UI", 9), bg=self.c_input_bg, fg=self.c_text_bright,
            insertbackground=self.c_accent, relief="flat", highlightbackground=self.c_border, highlightthickness=1
        )
        self.entry_dest.insert(0, self.dest_path)
        self.entry_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)
        self.entry_dest.bind("<KeyRelease>", self._on_dest_key_release)

        self.btn_browse = tk.Button(
            dest_frame, text=tr("modal_btn_browse", "⋯ Browse..."), font=("Segoe UI", 9),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_accent_dark,
            cursor="hand2", padx=12, pady=3, command=self._on_browse
        )
        self.btn_browse.pack(side=tk.RIGHT)

        # 4. Settings Row: Connections & Speed Limiter
        cfg_row = tk.Frame(card, bg=self.c_panel)
        cfg_row.pack(fill=tk.X, pady=(4, 0))

        conn_frame = tk.Frame(cfg_row, bg=self.c_panel)
        conn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_conn = tk.Label(conn_frame, text=tr("modal_threads", "Connections / Threads:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_muted)
        lbl_conn.pack(anchor="w", pady=(0, 2))

        self.combo_threads = ttk.Combobox(conn_frame, values=["1", "2", "4", "8", "16", "32"], state="readonly", width=10, font=("Segoe UI", 9))
        def_conn_str = str(self.default_connections) if str(self.default_connections) in ["1", "2", "4", "8", "16", "32"] else "8"
        self.combo_threads.set(def_conn_str)
        self.combo_threads.pack(anchor="w")

        spd_frame = tk.Frame(cfg_row, bg=self.c_panel)
        spd_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        lbl_spd = tk.Label(spd_frame, text=tr("modal_speed_limiter", "Speed Limiter:"), font=("Segoe UI", 8, "bold"), bg=self.c_panel, fg=self.c_text_muted)
        lbl_spd.pack(anchor="w", pady=(0, 2))

        self.combo_speed = ttk.Combobox(
            spd_frame, values=[tr("lbl_unlimited", "Unlimited"), "256 KB/s", "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "20 MB/s"],
            width=16, font=("Segoe UI", 9)
        )
        if self.default_speed_limit > 0:
            spd_str = f"{self.default_speed_limit / (1024*1024):.0f} MB/s" if self.default_speed_limit >= 1024*1024 else f"{self.default_speed_limit / 1024:.0f} KB/s"
            self.combo_speed.set(spd_str)
        else:
            self.combo_speed.set(tr("lbl_unlimited", "Unlimited"))
        self.combo_speed.pack(anchor="w")

        # Bottom Buttons Row
        btn_row = tk.Frame(self.frame_confirmation, bg=self.c_bg)
        btn_row.pack(fill=tk.X)

        lbl_hint = tk.Label(btn_row, text=tr("modal_confirm_hint", "⏎ Press Enter to start, Esc to cancel"), font=("Segoe UI", 8), bg=self.c_bg, fg=self.c_text_muted)
        lbl_hint.pack(side=tk.LEFT)

        self.btn_cancel = tk.Button(
            btn_row, text=tr("modal_btn_cancel", "✕ Cancel"), font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light, fg=self.c_text_muted, relief="flat", activebackground=self.c_border,
            cursor="hand2", padx=14, pady=6, command=self._on_close
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_open_app = tk.Button(
            btn_row, text=tr("modal_btn_open_in_main", "❐ Open in Main App"), font=("Segoe UI", 9),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_border,
            cursor="hand2", padx=14, pady=6, command=self._on_open_in_main
        )
        self.btn_open_app.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_start = tk.Button(
            btn_row, text=tr("modal_btn_start", "▶ Start Download"), font=("Segoe UI", 9, "bold"),
            bg=self.c_success, fg="white", relief="flat", activebackground="#059669",
            cursor="hand2", padx=16, pady=6, command=self._on_start_in_window
        )
        self.btn_start.pack(side=tk.RIGHT)

    def _build_progress_view(self):
        """View 2: Compact Download Progress View (Transitions on start)."""
        self.frame_progress = tk.Frame(self.body, bg=self.c_bg)

        prog_hdr = tk.Frame(self.frame_progress, bg=self.c_bg)
        prog_hdr.pack(fill=tk.X, pady=(0, 8))

        self.lbl_prog_icon = tk.Label(prog_hdr, text=self.icon, font=("Segoe UI", 16), bg=self.c_bg, fg=self.c_accent)
        self.lbl_prog_icon.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_prog_filename = tk.Label(
            prog_hdr, text=self.file_name, font=("Segoe UI", 10, "bold"),
            bg=self.c_bg, fg=self.c_text_bright, anchor="w"
        )
        self.lbl_prog_filename.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_prog_cat = tk.Label(
            prog_hdr, text=f"{self.icon}  {self.category}", font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light, fg=self.c_accent, padx=6, pady=2
        )
        self.lbl_prog_cat.pack(side=tk.RIGHT)

        # Progress Card
        prog_card = tk.Frame(self.frame_progress, bg=self.c_panel, padx=14, pady=10, highlightbackground=self.c_border, highlightthickness=1)
        prog_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.lbl_status = tk.Label(
            prog_card, text=tr("modal_status_connecting", "Status: Connecting..."),
            font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_accent, anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, pady=(0, 4))

        m_row1 = tk.Frame(prog_card, bg=self.c_panel)
        m_row1.pack(fill=tk.X, pady=(0, 2))

        self.lbl_prog_size = tk.Label(m_row1, text="Transferred: 0 B / 0 B (0.0%)", font=("Segoe UI", 9), bg=self.c_panel, fg=self.c_text_bright, anchor="w")
        self.lbl_prog_size.pack(side=tk.LEFT)

        self.lbl_prog_speed = tk.Label(m_row1, text="Speed: 0.0 KB/s", font=("Segoe UI", 9, "bold"), bg=self.c_panel, fg=self.c_success, anchor="e")
        self.lbl_prog_speed.pack(side=tk.RIGHT)

        m_row2 = tk.Frame(prog_card, bg=self.c_panel)
        m_row2.pack(fill=tk.X, pady=(0, 6))

        self.lbl_prog_eta = tk.Label(m_row2, text="Time Left: --:--:--", font=("Segoe UI", 8), bg=self.c_panel, fg=self.c_text_muted, anchor="w")
        self.lbl_prog_eta.pack(side=tk.LEFT)

        self.lbl_prog_threads = tk.Label(m_row2, text=f"Threads: {self.get_max_connections()} Active", font=("Segoe UI", 8), bg=self.c_panel, fg=self.c_text_muted, anchor="e")
        self.lbl_prog_threads.pack(side=tk.RIGHT)

        self.canvas_prog = tk.Canvas(prog_card, bg=self.c_input_bg, highlightthickness=0, height=int(24 * self.dpi_scale))
        self.canvas_prog.pack(fill=tk.X, pady=(2, 0))
        self.canvas_prog.bind("<Configure>", lambda e: self._draw_modal_progress(getattr(self, "_last_pct", 0.0)))

        # Progress Buttons Row
        self.prog_btn_row = tk.Frame(self.frame_progress, bg=self.c_bg)
        self.prog_btn_row.pack(fill=tk.X)

        self.btn_open_app_prog = tk.Button(
            self.prog_btn_row, text=tr("modal_btn_open_in_main", "❐ Open in Main App"), font=("Segoe UI", 9),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_border,
            cursor="hand2", padx=12, pady=5, command=self._on_open_in_main
        )
        self.btn_open_app_prog.pack(side=tk.LEFT)

        self.btn_cancel_prog = tk.Button(
            self.prog_btn_row, text=tr("modal_btn_cancel", "✕ Cancel"), font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light, fg=self.c_text_muted, relief="flat", activebackground=self.c_border,
            cursor="hand2", padx=14, pady=5, command=self._on_close
        )
        self.btn_cancel_prog.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_pause_resume = tk.Button(
            self.prog_btn_row, text=tr("btn_pause", "|| Pause"), font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_accent_dark,
            cursor="hand2", padx=14, pady=5, command=self._on_pause_resume
        )
        self.btn_pause_resume.pack(side=tk.RIGHT)

        self.btn_close_prog = tk.Button(
            self.prog_btn_row, text=tr("browser_btn_close", "Close"), font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_border,
            cursor="hand2", padx=14, pady=5, command=self.destroy
        )

        self.btn_open_folder = tk.Button(
            self.prog_btn_row, text=tr("btn_hist_folder", "⋯ Open Folder"), font=("Segoe UI", 9),
            bg=self.c_panel_light, fg=self.c_text_bright, relief="flat", activebackground=self.c_accent_dark,
            cursor="hand2", padx=12, pady=5, command=self._on_open_folder
        )

        self.btn_open_file = tk.Button(
            self.prog_btn_row, text=tr("btn_hist_open", "↗ Open File"), font=("Segoe UI", 9, "bold"),
            bg=self.c_success, fg="white", relief="flat", activebackground="#059669",
            cursor="hand2", padx=14, pady=5, command=self._on_open_file
        )


__all__ = ["ConfirmModalWidgetsMixin"]
