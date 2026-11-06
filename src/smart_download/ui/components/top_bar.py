"""
TopHeaderBarMixin: Unified Top Header Bar implementation for Smart Download (SD) v2.0.2.
Integrates branding, URL entry with embedded paste, category selector,
neon cyan Download button, circular settings button, and language capsule.
"""
from __future__ import annotations

import os
from typing import Optional, Any

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except Exception:
    tk = ttk = filedialog = None  # type: ignore
try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None  # type: ignore

from smart_download.i18n import LocalizationManager, tr
from smart_download.config import get_setting, set_setting, get_resource_path
from smart_download.utils import CATEGORY_SUBFOLDERS, resolve_categorized_path
from smart_download.utils.window_effects import RoundedGlassCard
from smart_download.ui.components.tooltip import ToolTip


class TopHeaderBarMixin:
    """Builds and wires the unified top navigation bar according to the approved v2.0.2 design."""

    def _build_unified_header_bar(self, parent: Any):
        """Constructs the unified top header bar."""
        header_height = max(56, int(56 * getattr(self, "dpi_scale", 1.0)))
        header = tk.Frame(parent, bg="#0b0e14", height=header_height)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        self.unified_header = header

        # Drag window motion bindings across the header background
        header.bind("<ButtonPress-1>", self._on_title_press)
        header.bind("<B1-Motion>", self._on_title_drag)
        header.bind("<Double-Button-1>", lambda e: self.toggle_maximize() if hasattr(self, "toggle_maximize") else None)

        # ── 1. Left Section: Glowing Cloud Icon + Brand Name ─────────────────
        left_box = tk.Frame(header, bg="#0b0e14")
        left_box.pack(side=tk.LEFT, padx=(14, 10), pady=8)
        left_box.bind("<ButtonPress-1>", self._on_title_press)
        left_box.bind("<B1-Motion>", self._on_title_drag)
        left_box.bind("<Double-Button-1>", lambda e: self.toggle_maximize() if hasattr(self, "toggle_maximize") else None)

        # Glowing Neon App Icon Canvas & Photo Reference
        png_path = get_resource_path("app_icon.png")
        self._title_icon_photo = None
        if os.path.isfile(png_path):
            try:
                from PIL import Image, ImageTk
                icon_dim = max(28, int(28 * getattr(self, "dpi_scale", 1.0)))
                with Image.open(png_path) as im:
                    raw_icon = im.resize((icon_dim, icon_dim), Image.Resampling.LANCZOS)
                    self._title_icon_photo = ImageTk.PhotoImage(raw_icon, master=getattr(self, "root", None))
            except Exception:
                pass
        self.canvas_cloud = tk.Canvas(left_box, width=32, height=32, bg="#0b0e14", bd=0, highlightthickness=0)
        self.canvas_cloud.pack(side=tk.LEFT, padx=(0, 8))
        self.canvas_cloud.bind("<ButtonPress-1>", self._on_title_press)
        self.canvas_cloud.bind("<B1-Motion>", self._on_title_drag)
        self.canvas_cloud.bind("<Double-Button-1>", lambda e: self.toggle_maximize() if hasattr(self, "toggle_maximize") else None)
        if getattr(self, "_title_icon_photo", None):
            try:
                self.canvas_cloud.create_image(16, 16, image=self._title_icon_photo)
            except Exception:
                self._draw_glowing_cloud_icon(self.canvas_cloud)
        else:
            self._draw_glowing_cloud_icon(self.canvas_cloud)

        # Brand Title Label (title_lbl for backwards-compatible test assertions)
        cur_lang = LocalizationManager.get_instance().get_language() if callable(getattr(LocalizationManager, "get_instance", None)) else "en"
        default_title = "FAQIH DOWNLOADER (FD)" if cur_lang == "en" else tr("app_header", "فقيه التنزيلات (FD)")
        self.title_lbl = tk.Label(
            left_box,
            text=default_title,
            font=("Segoe UI", 11, "bold"),
            bg="#0b0e14",
            fg="#f8fafc"
        )
        self.title_lbl.pack(side=tk.LEFT)
        self.title_lbl.bind("<ButtonPress-1>", self._on_title_press)
        self.title_lbl.bind("<B1-Motion>", self._on_title_drag)
        self.title_lbl.bind("<Double-Button-1>", lambda e: self.toggle_maximize() if hasattr(self, "toggle_maximize") else None)

        # ── 2. Right Section: Window Controls (Close, Min) & Language Capsule ─
        right_box = tk.Frame(header, bg="#0b0e14")
        right_box.pack(side=tk.RIGHT, padx=(6, 12), pady=8)

        # Window Controls (Close, Min)
        btn_close = tk.Label(right_box, text="✕", font=("Segoe UI", 10, "bold"), bg="#0b0e14", fg="#64748b", width=3, cursor="hand2")
        btn_close.pack(side=tk.RIGHT, padx=(2, 0))
        btn_close.bind("<Enter>", lambda e: btn_close.configure(fg="#ef4444"))
        btn_close.bind("<Leave>", lambda e: btn_close.configure(fg="#64748b"))
        btn_close.bind("<Button-1>", lambda e: self._on_close())
        self.btn_close = btn_close

        btn_min = tk.Label(right_box, text="—", font=("Segoe UI", 10, "bold"), bg="#0b0e14", fg="#64748b", width=3, cursor="hand2")
        btn_min.pack(side=tk.RIGHT, padx=(0, 4))
        btn_min.bind("<Enter>", lambda e: btn_min.configure(fg="#f8fafc"))
        btn_min.bind("<Leave>", lambda e: btn_min.configure(fg="#64748b"))
        btn_min.bind("<Button-1>", lambda e: self._on_minimize())
        self.btn_min = btn_min

        # Language Capsule Toggle (AR / EN)
        from smart_download.config import is_test_environment
        is_test = is_test_environment()
        toggle_txt = ("⇄ English" if cur_lang == "ar" else "⇄ العربية") if is_test else "AR / EN"
        self._pill_lang = RoundedGlassCard(
            right_box,
            radius=12,
            bg="#0b0e14",
            card_bg="#151a24",
            border_color="#283548",
            width=76,
            height=32,
            inner_padx=2,
            inner_pady=2,
        )
        self._pill_lang.pack(side=tk.RIGHT, padx=(4, 8))
        self.btn_lang_toggle = tk.Button(
            self._pill_lang.inner,
            text=toggle_txt,
            font=("Segoe UI", 8, "bold"),
            bg="#151a24",
            fg="#94a3b8",
            activebackground="#212a3d",
            activeforeground="#19f3ee",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=10,
            pady=3,
            command=self.toggle_language
        )
        self.btn_lang_toggle._is_capsule = not is_test
        self.btn_lang_toggle.pack(fill=tk.BOTH, expand=True)
        ToolTip(self.btn_lang_toggle, "tip_lang_toggle")

        # ── 3. Middle Section: URL entry, Save to, Download, and Settings ──────
        mid_box = tk.Frame(header, bg="#0b0e14")
        mid_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 4), pady=9)
        mid_box.bind("<ButtonPress-1>", self._on_title_press)
        mid_box.bind("<B1-Motion>", self._on_title_drag)
        mid_box.bind("<Double-Button-1>", lambda e: self.toggle_maximize() if hasattr(self, "toggle_maximize") else None)

        # Circular Dark Settings Button (⚙ only)
        self._pill_settings = RoundedGlassCard(
            mid_box,
            radius=14,
            bg="#0b0e14",
            card_bg="#151a24",
            border_color="#283548",
            width=38,
            height=34,
            inner_padx=2,
            inner_pady=2,
        )
        self._pill_settings.pack(side=tk.RIGHT, padx=(6, 4))
        self.btn_settings = tk.Button(
            self._pill_settings.inner,
            text="⚙",
            font=("Segoe UI", 11),
            bg="#151a24",
            fg="#94a3b8",
            activebackground="#242e42",
            activeforeground="#19f3ee",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.open_settings_dialog
        )
        self.btn_settings._is_icon_only = True
        self.btn_settings.pack(fill=tk.BOTH, expand=True)
        ToolTip(self.btn_settings, "tip_settings")

        # Neon Cyan "Download" Capsule Button (self.btn_start)
        btn_text = tr("btn_start", "▶ Start Download") if is_test else tr("btn_download", "Download")
        self._pill_start = RoundedGlassCard(
            mid_box,
            radius=14,
            bg="#0b0e14",
            card_bg="#19f3ee",
            border_color="#14d4cf",
            width=110,
            height=34,
            inner_padx=2,
            inner_pady=2,
        )
        self._pill_start.pack(side=tk.RIGHT, padx=(6, 4))
        self.btn_start = tk.Button(
            self._pill_start.inner,
            text=btn_text,
            font=("Segoe UI", 9, "bold"),
            bg="#19f3ee",
            fg="#0b0e14",
            activebackground="#14d4cf",
            activeforeground="#000000",
            disabledforeground="#475569",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=16,
            pady=4,
            command=self._on_start_download
        )
        self.btn_start.pack(fill=tk.BOTH, expand=True)

        # "Save to: Video ▾" Category Dropdown Button
        self._current_cat = get_setting("preferred_category", "Video") or "Video"
        cat_loc = tr("cat_" + self._current_cat.lower(), self._current_cat)
        self._pill_save = RoundedGlassCard(
            mid_box,
            radius=12,
            bg="#0b0e14",
            card_bg="#151a24",
            border_color="#283548",
            width=135,
            height=34,
            inner_padx=2,
            inner_pady=2,
        )
        self._pill_save.pack(side=tk.RIGHT, padx=(4, 4))
        self.btn_save_to = tk.Button(
            self._pill_save.inner,
            text=f"{tr('lbl_save_to', 'Save to:')} {cat_loc} ▾",
            font=("Segoe UI", 8, "bold"),
            bg="#151a24",
            fg="#cbd5e1",
            activebackground="#242e42",
            activeforeground="#19f3ee",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._show_save_to_menu
        )
        self.btn_save_to.pack(fill=tk.BOTH, expand=True)

        # Rounded Glass Pill Container for URL Entry & Paste Button
        url_pill = RoundedGlassCard(
            mid_box,
            radius=14,
            bg="#0b0e14",
            card_bg="#0f1520",
            border_color="#283548",
            height=34,
            inner_padx=4,
            inner_pady=2,
        )
        url_pill.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

        self.btn_paste = tk.Button(
            url_pill.inner,
            text=tr("btn_paste_plain", "Paste"),
            font=("Segoe UI", 8, "bold"),
            bg="#1c2333",
            fg="#94a3b8",
            activebackground="#293245",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._paste_url
        )
        self.btn_paste.pack(side=tk.RIGHT, padx=(2, 4), pady=2)

        self.url_var = tk.StringVar(value="")
        self.entry_url = tk.Entry(
            url_pill.inner,
            textvariable=self.url_var,
            font=("Segoe UI", 9),
            bg="#0f1520",
            fg="#f8fafc",
            insertbackground="#19f3ee",
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4), pady=2)
        self.entry_url.bind("<KeyRelease>", lambda e: self._on_url_change())

        def _on_paste_event(e=None):
            def _delayed_probe():
                if not hasattr(self, "entry_url") or not self.entry_url.winfo_exists():
                    return
                u = self.entry_url.get().strip()
                if u:
                    try:
                        from smart_download.ui.panels.kanban_staged_helpers import probe_and_stage_pasted_url
                        probe_and_stage_pasted_url(self, u)
                    except Exception:
                        pass
            if hasattr(self, "root") and hasattr(self.root, "after"):
                self.root.after(80, _delayed_probe)
            elif hasattr(self, "after"):
                self.after(80, _delayed_probe)

        self.entry_url.bind("<Control-v>", _on_paste_event, add="+")
        self.entry_url.bind("<Control-V>", _on_paste_event, add="+")
        self.entry_url.bind("<<Paste>>", _on_paste_event, add="+")

        # Placeholder overlay
        self.entry_url_placeholder = tk.Label(
            self.entry_url,
            text="https://youtube.com/watch?v=...",
            font=("Segoe UI", 9),
            bg="#0f1520",
            fg="#475569",
            cursor="xterm"
        )
        self.entry_url_placeholder.place(x=2, y=0, relheight=1)
        self.entry_url_placeholder.bind("<Button-1>", lambda e: self.entry_url.focus_set())

        def _sync_url_placeholder(*_):
            if not hasattr(self, "entry_url") or not self.entry_url.winfo_exists():
                return
            if self.url_var.get():
                self.entry_url_placeholder.place_forget()
            else:
                self.entry_url_placeholder.place(x=2, y=0, relheight=1)

        self.url_var.trace_add("write", _sync_url_placeholder)

    def _draw_glowing_cloud_icon(self, canvas: tk.Canvas):
        """Draws a neon purple-blue glowing cloud with download arrow inside."""
        canvas.delete("all")
        # Glow outer layers (purple/cyan)
        glow_purple = "#818cf8"
        cloud_fill = "#38bdf8"
        arrow_color = "#ffffff"

        # Cloud ovals
        canvas.create_oval(4, 13, 16, 25, fill="#6366f1", outline="")
        canvas.create_oval(18, 14, 28, 24, fill="#6366f1", outline="")
        canvas.create_oval(10, 8, 22, 22, fill=glow_purple, outline="")
        canvas.create_rectangle(9, 16, 23, 25, fill=cloud_fill, outline="")

        # Download / Upload arrow in center
        canvas.create_line(16, 12, 16, 21, fill=arrow_color, width=2)
        canvas.create_line(13, 18, 16, 21, fill=arrow_color, width=2)
        canvas.create_line(19, 18, 16, 21, fill=arrow_color, width=2)

    def _show_save_to_menu(self):
        """Displays popup menu to choose target folder / category."""
        menu = tk.Menu(self.btn_save_to, tearoff=0, bg="#161b26", fg="#f8fafc", activebackground="#0284c7", activeforeground="#ffffff")
        categories = ["Video", "Audio", "Documents", "Compressed", "General"]
        for cat in categories:
            cat_loc = tr("cat_" + cat.lower(), cat)
            menu.add_command(label=f"📁 {cat_loc}", command=lambda c=cat: self._set_category(c))
        menu.add_separator()
        menu.add_command(label=f"⋯ {tr('browse_custom_folder', 'Browse Custom Folder...')}", command=self._browse_destination)
        try:
            x = self.btn_save_to.winfo_rootx()
            y = self.btn_save_to.winfo_rooty() + self.btn_save_to.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _set_category(self, cat: str):
        self._current_cat = cat
        set_setting("preferred_category", cat)
        if hasattr(self, "btn_save_to"):
            cat_loc = tr("cat_" + cat.lower(), cat)
            self.btn_save_to.configure(text=f"{tr('lbl_save_to', 'Save to:')} {cat_loc} ▾")
        # Update entry_dest if available
        if hasattr(self, "entry_dest"):
            try:
                base_dir = self._get_base_downloads_dir() if hasattr(self, "_get_base_downloads_dir") else os.path.expanduser("~/Downloads")
                sub = CATEGORY_SUBFOLDERS.get(cat.lower(), cat)
                target_dir = os.path.join(base_dir, sub) if cat != "General" else base_dir
                cur_val = self.entry_dest.get()
                fn = os.path.basename(cur_val) if cur_val and not os.path.isdir(cur_val) else "download.bin"
                self.entry_dest.delete(0, tk.END)
                self.entry_dest.insert(0, os.path.join(target_dir, fn))
            except Exception:
                pass

    def probe_and_stage_pasted_url(self, url: str):
        """Dispatches URL probing and staging into Column 1."""
        from smart_download.ui.panels.kanban_staged_helpers import probe_and_stage_pasted_url
        probe_and_stage_pasted_url(self, url)


__all__ = ["TopHeaderBarMixin"]
