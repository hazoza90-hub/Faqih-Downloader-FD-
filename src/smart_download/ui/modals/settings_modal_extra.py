"""
SettingsModalExtraMixin: Speed Limiter and Engine Log tab builders for SettingsModal in Smart Download (SD).
"""
from __future__ import annotations

import os
from typing import Any, Optional

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from smart_download.i18n import tr
from smart_download.config import set_setting
from smart_download.utils import format_speed


class SettingsModalExtraMixin:
    """Provides methods for constructing the Speed Limiter and Engine Activity Log tabs."""

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: SPEED LIMITER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_limiter_tab(self, parent: Any):
        """Constructs dedicated Speed Limiter bandwidth throttling controls."""
        tk.Label(
            parent,
            text=tr("lbl_speed_limiter", "Download Bandwidth Throttling:"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_accent,
        ).pack(anchor="w", pady=(0, 6))

        # Preset Row
        row_preset = tk.Frame(parent, bg=self.c_bg)
        row_preset.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row_preset, text="Preset Limit:", font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text_bright).pack(side=tk.LEFT)

        unlimited_val = tr("lbl_unlimited", "Unlimited")
        presets = [unlimited_val, "512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "20 MB/s"]
        cur_preset = getattr(self.parent_app, "speed_preset_var", None)
        init_preset = cur_preset.get() if cur_preset else unlimited_val
        self.modal_combo_preset = ttk.Combobox(row_preset, values=presets, state="readonly", width=14)
        self.modal_combo_preset.set(init_preset if init_preset in presets else unlimited_val)
        self.modal_combo_preset.pack(side=tk.RIGHT)
        self.modal_combo_preset.bind("<<ComboboxSelected>>", self._on_modal_preset_selected)

        # Scale Slider Row
        row_slider = tk.Frame(parent, bg=self.c_bg)
        row_slider.pack(fill=tk.X, pady=(0, 6))
        tk.Label(row_slider, text="Throttling Slider (KB/s):", font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text_bright).pack(anchor="w")

        slider_val = 0
        if self.parent_app and hasattr(self.parent_app, "slider_speed"):
            try:
                slider_val = int(self.parent_app.slider_speed.get())
            except Exception:
                slider_val = 0

        self.modal_slider_val_lbl = tk.Label(
            row_slider,
            text=f"{unlimited_val} (0 KB/s)" if slider_val == 0 else f"{slider_val:,} KB/s ({slider_val/1024:.1f} MB/s)",
            font=("Segoe UI", 8, "bold"),
            bg=self.c_bg,
            fg=self.c_accent,
        )
        self.modal_slider_val_lbl.pack(anchor="e")

        self.modal_slider = tk.Scale(
            row_slider,
            from_=0,
            to=20480,
            orient=tk.HORIZONTAL,
            showvalue=False,
            command=self._on_modal_slider_moved,
            highlightthickness=1,
            highlightbackground=self.c_border,
            highlightcolor=self.c_accent,
            bd=0,
            relief="flat",
            sliderrelief="flat",
            bg=self.c_panel,
            troughcolor=self.c_input_bg,
        )
        self.modal_slider.set(slider_val)
        self.modal_slider.pack(fill=tk.X, pady=(2, 8))

        # Custom Input Row + Apply
        row_custom = tk.Frame(parent, bg=self.c_bg)
        row_custom.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row_custom, text=tr("lbl_custom_speed", "Custom Limit (KB/s):"), font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text_bright).pack(side=tk.LEFT)

        self.modal_btn_apply = tk.Button(
            row_custom,
            text=tr("btn_apply_limit", "Apply"),
            font=("Segoe UI", 8, "bold"),
            bg=self.c_accent,
            fg="#0b0e14",
            activebackground=self.c_accent_dark,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=2,
            command=self._apply_modal_speed_limit,
        )
        self.modal_btn_apply.pack(side=tk.RIGHT)

        custom_val = "0"
        if self.parent_app and hasattr(self.parent_app, "entry_custom_speed"):
            try:
                custom_val = self.parent_app.entry_custom_speed.get().strip() or "0"
            except Exception:
                custom_val = "0"
        self.modal_entry_custom = tk.Entry(
            row_custom,
            font=("Segoe UI", 9),
            bg=self.c_input_bg,
            fg=self.c_text_bright,
            insertbackground=self.c_text_bright,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_border,
            width=10,
        )
        self.modal_entry_custom.pack(side=tk.RIGHT, padx=(0, 8), ipady=2)
        self.modal_entry_custom.insert(0, custom_val)
        self.modal_entry_custom.bind("<Return>", lambda e: self._apply_modal_speed_limit())

        # Live status
        cur_limit = getattr(self.parent_app, "speed_limit", 0.0) if self.parent_app else 0.0
        limit_desc = tr("lbl_current_unlimited", "● Current: Unlimited") if cur_limit <= 0 else f"● Current: {format_speed(cur_limit)}"
        self.modal_lbl_active = tk.Label(
            parent,
            text=limit_desc,
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_success if cur_limit <= 0 else self.c_accent,
        )
        self.modal_lbl_active.pack(anchor="w", pady=(4, 0))

    def _on_modal_preset_selected(self, event=None):
        val = self.modal_combo_preset.get()
        unlimited_val = tr("lbl_unlimited", "Unlimited")
        if val == unlimited_val:
            kbps = 0
        else:
            mapping = {
                "512 KB/s": 512,
                "1 MB/s": 1024,
                "2 MB/s": 2048,
                "5 MB/s": 5120,
                "10 MB/s": 10240,
                "20 MB/s": 20480,
            }
            kbps = mapping.get(val, 0)
        self.modal_slider.set(kbps)
        self.modal_entry_custom.delete(0, tk.END)
        self.modal_entry_custom.insert(0, str(kbps))
        self._apply_modal_speed_limit()

    def _on_modal_slider_moved(self, val_str: str):
        try:
            kbps = int(float(val_str))
        except Exception:
            kbps = 0
        unlimited_val = tr("lbl_unlimited", "Unlimited")
        if kbps == 0:
            txt = f"{unlimited_val} (0 KB/s)"
        else:
            txt = f"{kbps:,} KB/s ({kbps/1024:.1f} MB/s)"
        self.modal_slider_val_lbl.configure(text=txt)
        self.modal_entry_custom.delete(0, tk.END)
        self.modal_entry_custom.insert(0, str(kbps))

    def _apply_modal_speed_limit(self):
        try:
            kbps = int(self.modal_entry_custom.get().strip() or "0")
        except ValueError:
            kbps = 0
        bytes_sec = float(kbps * 1024)
        set_setting("custom_speed_limit_kbps", kbps)
        unlimited_val = tr("lbl_unlimited", "Unlimited")
        desc = tr("lbl_current_unlimited", "● Current: Unlimited") if kbps <= 0 else f"● Current: {format_speed(bytes_sec)}"
        self.modal_lbl_active.configure(text=desc, fg=self.c_success if kbps <= 0 else self.c_accent)

        if self.parent_app:
            self.parent_app.speed_limit = bytes_sec
            if hasattr(self.parent_app, "slider_speed"):
                self.parent_app.slider_speed.set(kbps)
            if hasattr(self.parent_app, "entry_custom_speed"):
                self.parent_app.entry_custom_speed.delete(0, tk.END)
                self.parent_app.entry_custom_speed.insert(0, str(kbps))
            if hasattr(self.parent_app, "speed_preset_var"):
                self.parent_app.speed_preset_var.set(self.modal_combo_preset.get())
            if hasattr(self.parent_app, "lbl_active_limit"):
                self.parent_app.lbl_active_limit.configure(text=desc)
            if hasattr(self.parent_app, "engine") and self.parent_app.engine:
                try:
                    self.parent_app.engine.set_speed_limit(bytes_sec)
                except Exception:
                    pass
            if hasattr(self.parent_app, "log") and callable(self.parent_app.log):
                self.parent_app.log(f"[SETTINGS] Speed limiter updated to: {desc}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB: ENGINE ACTIVITY LOG
    # ══════════════════════════════════════════════════════════════════════════
    def _build_log_tab(self, parent: Any):
        """Constructs Real-time engine and activity console."""
        top_bar = tk.Frame(parent, bg=self.c_bg)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            top_bar,
            text=tr("settings_tab_log", "Engine Activity Log:"),
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_accent,
        ).pack(side=tk.LEFT)

        tk.Button(
            top_bar,
            text=tr("settings_log_clear", "⌫ Clear"),
            font=("Segoe UI", 8),
            bg=self.c_panel_light,
            fg=self.c_text_muted,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._clear_modal_log,
        ).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            top_bar,
            text=tr("settings_log_copy", "⎘ Copy"),
            font=("Segoe UI", 8),
            bg=self.c_panel_light,
            fg=self.c_text_bright,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._copy_modal_log,
        ).pack(side=tk.RIGHT)

        txt_frame = tk.Frame(parent, bg="#090e1a", highlightthickness=1, highlightbackground=self.c_border)
        txt_frame.pack(fill=tk.BOTH, expand=True)

        self.modal_txt_log = tk.Text(
            txt_frame,
            bg="#090e1a",
            fg="#f8fafc",
            font=("Consolas", 8),
            bd=0,
            relief="flat",
            wrap="word",
        )
        self.modal_txt_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        log_content = ""
        if self.parent_app and hasattr(self.parent_app, "txt_log"):
            try:
                log_content = self.parent_app.txt_log.get("1.0", tk.END).strip()
            except Exception:
                pass
        if not log_content and self.parent_app and hasattr(self.parent_app, "logs"):
            try:
                log_content = "\n".join(str(l) for l in self.parent_app.logs)
            except Exception:
                pass
        if not log_content:
            log_content = "[SMART DOWNLOAD] Engine online. Ready for downloads."
        self.modal_txt_log.insert("1.0", log_content)
        self.modal_txt_log.see(tk.END)

    def _copy_modal_log(self):
        try:
            content = self.modal_txt_log.get("1.0", tk.END).strip()
            if content and hasattr(self, "clipboard_clear"):
                self.clipboard_clear()
                self.clipboard_append(content)
        except Exception:
            pass

    def _clear_modal_log(self):
        try:
            self.modal_txt_log.delete("1.0", tk.END)
            if self.parent_app and hasattr(self.parent_app, "txt_log"):
                self.parent_app.txt_log.delete("1.0", tk.END)
            if self.parent_app and hasattr(self.parent_app, "logs"):
                self.parent_app.logs.clear()
        except Exception:
            pass


__all__ = ["SettingsModalExtraMixin"]
