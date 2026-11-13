"""
SettingsModalTabsMixin: Tab building logic for SettingsModal in Smart Download (SD).
Implements Tabs for:
1. Clipboard Sniffer & per-platform toggles
2. Downloads, folders, threads (1-32), cookies, video resolution
3. Windows Startup & System Tray
(Inherits SettingsModalExtraMixin for Speed Limiter and Engine Log tabs).
"""
from __future__ import annotations

import os
from typing import Dict, Any, Optional, List, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import (
    get_setting,
    set_setting,
    get_base_downloads_dir,
    DEFAULT_SNIFFER_PLATFORMS,
)
from faqih_downloader.services import is_startup_enabled, enable_startup, disable_startup
from .settings_modal_extra import SettingsModalExtraMixin


class SettingsModalTabsMixin(SettingsModalExtraMixin):
    """Provides methods for constructing tabs within SettingsModal."""

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1: CLIPBOARD SNIFFER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sniffer_tab(self, parent: Any):
        """Constructs Tab 1: Clipboard Sniffer & per-platform toggles."""
        active = (
            getattr(self.parent_app, "_clipboard_sniffer_active", True)
            if self.parent_app
            else bool(get_setting("clipboard_sniffer_active", True))
        )
        self.btn_master_sniffer = tk.Button(
            parent,
            text=tr("settings_sniffer_master_on") if active else tr("settings_sniffer_master_off"),
            font=("Segoe UI", 9, "bold"),
            bg="#0f292a" if active else "#182234",
            fg=self.c_success if active else self.c_text_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10b981" if active else self.c_border,
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._toggle_master_sniffer,
        )
        self.btn_master_sniffer.pack(fill=tk.X, pady=(0, 6))

        sniffer_note_txt = tr(
            "settings_sniffer_note",
            tr(
                "settings_sniffer_hint",
                "تعطيل أي منصة أدناه يوقف الالتقاط التلقائي من الحافظة، مع بقاء اللصق والتحميل اليدوي متاحاً في أي وقت."
            )
        )
        self.lbl_sniffer_note = tk.Label(
            parent,
            text=sniffer_note_txt,
            font=("Segoe UI", 8),
            bg=self.c_bg,
            fg=self.c_text_muted,
            wraplength=460,
            justify="center",
        )
        self.lbl_sniffer_note.pack(fill=tk.X, pady=(0, 8))

        row_actions = tk.Frame(parent, bg=self.c_bg)
        row_actions.pack(fill=tk.X, pady=(0, 8))
        tk.Button(
            row_actions,
            text=tr("settings_btn_enable_all_platforms", "✓ Enable All"),
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light,
            fg=self.c_success,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=3,
            command=lambda: self._set_all_platforms(True),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            row_actions,
            text=tr("settings_btn_disable_all_platforms", "✕ Disable All"),
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light,
            fg=self.c_danger,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=3,
            command=lambda: self._set_all_platforms(False),
        ).pack(side=tk.LEFT)

        grid_frame = tk.Frame(parent, bg=self.c_bg)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for idx, (plat_key, tr_key) in enumerate(self.PLATFORM_DEFS):
            plat_name = tr(tr_key)
            is_on = bool(self.sniffer_platforms.get(plat_key, True))
            btn = tk.Button(
                grid_frame,
                text=f"[✓] {plat_name}" if is_on else f"[  ] {plat_name}",
                font=("Segoe UI", 8, "bold"),
                bg="#0f292a" if is_on else "#182234",
                fg=self.c_success if is_on else self.c_text_muted,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#10b981" if is_on else self.c_border,
                cursor="hand2",
                anchor="w",
                padx=10,
                pady=4,
                command=lambda k=plat_key, tk_k=tr_key: self._toggle_platform(k, tk_k),
            )
            btn.grid(row=idx // 2, column=idx % 2, padx=4, pady=3, sticky="ew")
            self._plat_buttons[plat_key] = btn

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2: DOWNLOADS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_downloads_tab(self, parent: Any):
        """Constructs Tab 2: Downloads, folders, threads (1-32), cookies & media resolution."""
        # Default Save Directory
        tk.Label(
            parent,
            text=tr("settings_downloads_save_dir", "Default Save Folder:"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_accent,
        ).pack(anchor="w", pady=(0, 2))
        dir_row = tk.Frame(parent, bg=self.c_bg)
        dir_row.pack(fill=tk.X, pady=(0, 8))
        self.entry_dir = tk.Entry(
            dir_row,
            font=("Segoe UI", 9),
            bg=self.c_input_bg,
            fg=self.c_text_bright,
            insertbackground=self.c_text_bright,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border,
        )
        self.entry_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)
        self.entry_dir.insert(0, str(get_setting("last_download_dir", "") or get_base_downloads_dir()))
        self.entry_dir.bind("<Return>", lambda e: self._save_manual_dir_if_valid())
        self.entry_dir.bind("<FocusOut>", lambda e: self._save_manual_dir_if_valid())
        tk.Button(
            dir_row,
            text=tr("settings_btn_browse", "⋯ Browse..."),
            font=("Segoe UI", 8, "bold"),
            bg=self.c_panel_light,
            fg=self.c_accent,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._browse_save_dir,
        ).pack(side=tk.RIGHT)

        # Quick Toggles: Auto-Categorize & Auto-Unpack
        toggles_frame = tk.Frame(parent, bg=self.c_bg)
        toggles_frame.pack(fill=tk.X, pady=(0, 8))
        toggles_frame.columnconfigure(0, weight=1)
        toggles_frame.columnconfigure(1, weight=1)

        auto_cat = (
            getattr(self.parent_app, "auto_categorize_folders", True)
            if self.parent_app
            else bool(get_setting("auto_categorize_folders", True))
        )
        self.btn_auto_cat = tk.Button(
            toggles_frame,
            text=tr("settings_downloads_auto_cat_on") if auto_cat else tr("settings_downloads_auto_cat_off"),
            font=("Segoe UI", 8, "bold"),
            bg="#0f292a" if auto_cat else "#182234",
            fg=self.c_success if auto_cat else self.c_text_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10b981" if auto_cat else self.c_border,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._toggle_auto_cat,
        )
        self.btn_auto_cat.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        unpack = bool(get_setting("auto_unpack_archives", False))
        self.btn_unpack = tk.Button(
            toggles_frame,
            text=tr("settings_downloads_unpack_on") if unpack else tr("settings_downloads_unpack_off"),
            font=("Segoe UI", 8, "bold"),
            bg="#0f292a" if unpack else "#182234",
            fg=self.c_success if unpack else self.c_text_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10b981" if unpack else self.c_border,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._toggle_unpack,
        )
        self.btn_unpack.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Selectors: Threads (1-32), Preferred Resolution, Browser Cookies
        selectors = tk.Frame(parent, bg=self.c_bg)
        selectors.pack(fill=tk.X, pady=(0, 6))

        r1 = tk.Frame(selectors, bg=self.c_bg)
        r1.pack(fill=tk.X, pady=3)
        tk.Label(
            r1,
            text=tr("settings_downloads_threads_lbl", "Parallel Connections (1-32):"),
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_text_bright,
        ).pack(side=tk.LEFT)
        cur_conn = str(get_setting("max_connections", 8))
        threads_vals = ["1", "2", "4", "6", "8", "12", "16", "24", "32"]
        self.cb_threads = ttk.Combobox(r1, values=threads_vals, state="readonly", width=8)
        self.cb_threads.set(cur_conn if cur_conn in threads_vals else "8")
        self.cb_threads.pack(side=tk.RIGHT)
        self.cb_threads.bind("<<ComboboxSelected>>", self._on_threads_changed)

        self.lbl_threads_warn = tk.Label(
            selectors,
            text="",
            font=("Segoe UI", 8),
            fg="#f59e0b",
            bg=self.c_bg,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        if hasattr(self, "_update_threads_warning"):
            self._update_threads_warning(cur_conn)

        r2 = tk.Frame(selectors, bg=self.c_bg)
        r2.pack(fill=tk.X, pady=3)
        tk.Label(
            r2,
            text=tr("settings_downloads_pref_res_lbl", "Preferred Video Resolution:"),
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_text_bright,
        ).pack(side=tk.LEFT)
        res_val = int(get_setting("preferred_video_height", 0))
        self.cb_res = ttk.Combobox(r2, values=[lbl for _, lbl in self.RES_OPTIONS], state="readonly", width=18)
        self.cb_res.set(next((lbl for h, lbl in self.RES_OPTIONS if h == res_val), "0 (Ask / Best)"))
        self.cb_res.pack(side=tk.RIGHT)
        self.cb_res.bind("<<ComboboxSelected>>", self._on_res_changed)

        r3 = tk.Frame(selectors, bg=self.c_bg)
        r3.pack(fill=tk.X, pady=3)
        tk.Label(
            r3,
            text=tr("settings_downloads_cookies_lbl", "Browser Cookies Source:"),
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_text_bright,
        ).pack(side=tk.LEFT)
        cur_cookies = str(get_setting("cookies_browser", "auto") or "auto").lower()
        if cur_cookies in ("file", "file...") or bool(get_setting("cookies_file", "")):
            cookie_init = "file..."
        elif cur_cookies in ["auto", "edge", "chrome", "firefox", "brave", "none"]:
            cookie_init = cur_cookies
        else:
            cookie_init = "auto"
        self.cb_cookies = ttk.Combobox(
            r3,
            values=["auto", "edge", "chrome", "firefox", "brave", "file...", "none"],
            state="readonly",
            width=12,
        )
        self.cb_cookies.set(cookie_init)
        self.cb_cookies.pack(side=tk.RIGHT)
        self.cb_cookies.bind("<<ComboboxSelected>>", self._on_cookies_changed)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4: SYSTEM & STARTUP
    # ══════════════════════════════════════════════════════════════════════════
    def _build_system_tab(self, parent: Any):
        """Constructs Tab 4: Windows Startup, system tray on close, and browser guide."""
        st_on = is_startup_enabled()
        self.btn_startup = tk.Button(
            parent,
            text=tr("settings_system_startup_on") if st_on else tr("settings_system_startup_off"),
            font=("Segoe UI", 9, "bold"),
            bg="#0f292a" if st_on else "#182234",
            fg=self.c_success if st_on else self.c_text_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10b981" if st_on else self.c_border,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._toggle_startup,
        )
        self.btn_startup.pack(fill=tk.X, pady=(0, 10))

        tray_on = (
            getattr(self.parent_app, "minimize_to_tray", True)
            if self.parent_app
            else bool(get_setting("minimize_to_tray", True))
        )
        self.btn_tray = tk.Button(
            parent,
            text=tr("settings_system_tray_on") if tray_on else tr("settings_system_tray_off"),
            font=("Segoe UI", 9, "bold"),
            bg="#0f292a" if tray_on else "#182234",
            fg=self.c_success if tray_on else self.c_text_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#10b981" if tray_on else self.c_border,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._toggle_tray,
        )
        self.btn_tray.pack(fill=tk.X, pady=(0, 14))

        # Window Glass Transparency (Acrylic / Mica) Slider
        r_alpha = tk.Frame(parent, bg=self.c_bg)
        r_alpha.pack(fill=tk.X, pady=(0, 14))

        cur_alpha = float(get_setting("window_alpha", 1.0))
        cur_pct = int(round(cur_alpha * 100))

        top_alpha = tk.Frame(r_alpha, bg=self.c_bg)
        top_alpha.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            top_alpha,
            text=tr("settings_window_transparency_lbl", "Window Glass Transparency (Acrylic Glass):"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_text_bright,
        ).pack(side=tk.LEFT)

        self.lbl_transparency_val = tk.Label(
            top_alpha,
            text=f"{cur_pct}%",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_accent,
        )
        self.lbl_transparency_val.pack(side=tk.RIGHT)

        self.slider_transparency = tk.Scale(
            r_alpha,
            from_=70,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=0,
            bg=self.c_panel,
            fg=self.c_accent,
            troughcolor="#0b1220",
            activebackground=self.c_accent,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.slider_transparency.set(cur_pct)
        self.slider_transparency.configure(command=self._on_transparency_slider_changed)
        self.slider_transparency.pack(fill=tk.X)

        tk.Button(
            parent,
            text=tr("settings_btn_browser_integration", "❖ Open Browser Extension Integration Guide"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_panel,
            fg=self.c_accent,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_accent_dark,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._open_browser_guide,
        ).pack(fill=tk.X)

    def _on_transparency_slider_changed(self, val_str: str):
        try:
            pct = int(float(val_str))
            alpha = max(0.60, min(1.0, pct / 100.0))
        except Exception:
            alpha = 1.0
        if hasattr(self, "lbl_transparency_val") and self.lbl_transparency_val:
            try:
                self.lbl_transparency_val.configure(text=f"{int(round(alpha * 100))}%")
            except Exception:
                pass
        set_setting("window_alpha", alpha)
        set_setting("window_opacity", alpha)
        if self.parent_app and hasattr(self.parent_app, "root"):
            try:
                from faqih_downloader.utils.window_effects import apply_acrylic_or_mica_effect
                self.parent_app._window_alpha = alpha
                apply_acrylic_or_mica_effect(self.parent_app.root, alpha=alpha)
            except Exception:
                pass

    def _on_transparency_changed(self, event=None):
        if hasattr(self, "slider_transparency"):
            self._on_transparency_slider_changed(str(self.slider_transparency.get()))


__all__ = ["SettingsModalTabsMixin"]

