"""
SettingsModalLayoutMixin: Builds the visual layout and tab notebook for SettingsModal.
"""
from __future__ import annotations
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.ui.modals.quality_modal_helpers import build_quality_title_bar


class SettingsModalLayoutMixin:
    """Provides _build_ui constructing header, tabs notebook, and close footer."""

    def _build_ui(self):
        outer = tk.Frame(self, bg=self.c_border, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self.title_bar = build_quality_title_bar(
            self, outer, self.theme, tr("settings_modal_title", "⚙ Application Settings — Faqih Downloader"), self._on_close
        )
        body = tk.Frame(outer, bg=self.c_bg, padx=14, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        try:
            st = ttk.Style(self)
            st.theme_use("clam")
            st.layout("Custom.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
            st.configure("Custom.TNotebook", background=self.c_bg, borderwidth=0, tabmargins=[0, 2, 0, 0])
            st.configure(
                "Custom.TNotebook.Tab",
                background=self.c_panel,
                foreground=self.c_text_muted,
                bordercolor=self.c_border,
                lightcolor=self.c_panel,
                darkcolor=self.c_panel,
                focuscolor=self.c_panel,
                padding=[14, 6],
                font=("Segoe UI", 9, "bold"),
            )
            st.map(
                "Custom.TNotebook.Tab",
                background=[("selected", "#1a2030"), ("active", "#252f42")],
                foreground=[("selected", "#19f3ee"), ("active", "#f8fafc")],
                bordercolor=[("selected", "#19f3ee"), ("active", self.c_border)],
            )
        except Exception:
            pass

        nb = ttk.Notebook(body, style="Custom.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Build tabs with border styling strictly matching test assertions
        def _make_tab(name: str):
            f = tk.Frame(
                nb,
                bg=self.c_bg,
                padx=12,
                pady=10,
                bd=0,
                highlightthickness=1,
                highlightbackground=self.c_border,
                highlightcolor=self.c_border,
            )
            nb.add(f, text=name)
            return f

        tab_sniffer = _make_tab(tr("settings_tab_sniffer", " ⚙ Sniffer "))
        tab_downloads = _make_tab(tr("settings_tab_downloads", " ❖ Downloads "))
        tab_limiter = _make_tab(tr("settings_tab_limiter", " ⚡ Speed Limiter "))
        tab_system = _make_tab(tr("settings_tab_system", " ⚡ System "))
        tab_log = _make_tab(tr("settings_tab_log", " ▤ Engine Log "))

        self._build_sniffer_tab(tab_sniffer)
        self._build_downloads_tab(tab_downloads)
        self._build_limiter_tab(tab_limiter)
        self._build_system_tab(tab_system)
        self._build_log_tab(tab_log)

        footer = tk.Frame(body, bg=self.c_bg)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(
            footer,
            text=tr("settings_btn_save_close", "Close"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            activebackground=self.c_accent_dark,
            activeforeground="white",
            cursor="hand2",
            padx=18,
            pady=4,
            command=self._on_close,
        ).pack(side=tk.RIGHT)
