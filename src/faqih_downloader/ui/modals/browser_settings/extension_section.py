"""
Extension installation guide and directory section builder for browser settings dialog.
"""
import os
import sys
import shutil
from typing import Any

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from ....locales.i18n import tr
from ....services.startup_service import IS_WINDOWS
from ....services.browser.host_manifest import get_project_root


def build_extension_section(controller: Any, parent: Any, dlg: Any, dlg_w: int):
    """Constructs extension artifact path card, installation guide notebook, and close button."""
    # 4. Extension Directory Card
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        persistent_ext_dir = os.path.join(exe_dir, "extension")
        if hasattr(sys, "_MEIPASS"):
            bundled_ext = os.path.join(sys._MEIPASS, "extension")
            if os.path.isdir(bundled_ext):
                try:
                    shutil.copytree(bundled_ext, persistent_ext_dir, dirs_exist_ok=True)
                except Exception:
                    pass
        ext_dir = persistent_ext_dir if os.path.isdir(persistent_ext_dir) else os.path.join(getattr(sys, "_MEIPASS", exe_dir), "extension")
    else:
        ext_dir = os.path.join(get_project_root(), "extension")
        if not os.path.isdir(ext_dir):
            base_app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            ext_dir = os.path.join(base_app_dir, "extension")

    card_ext = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_ext.pack(fill=tk.X, pady=(0, 5))

    lbl_e_title = tk.Label(card_ext, text=tr("browser_card_ext_title", "WEBEXTENSION ARTIFACT (MANIFEST V3)"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_text_muted)
    lbl_e_title.pack(anchor="w")

    e_row = tk.Frame(card_ext, bg=controller.c_panel)
    e_row.pack(fill=tk.X, pady=(4, 0))

    lbl_path = tk.Label(e_row, text=ext_dir, font=("Consolas", 8), bg=controller.c_input_bg, fg=controller.c_accent, padx=6, pady=4, anchor="w")
    lbl_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    def _open_folder():
        if os.path.exists(ext_dir):
            if IS_WINDOWS:
                os.startfile(ext_dir)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", ext_dir])

    btn_open = tk.Button(
        e_row,
        text=tr("browser_btn_open_folder", "⋯ Open Folder"),
        font=("Segoe UI", 8, "bold"),
        bg=controller.c_accent_dark,
        fg="white",
        relief="flat",
        cursor="hand2",
        command=_open_folder
    )
    btn_open.pack(side=tk.RIGHT)

    # Close button (packed at bottom first so never clipped by guide notebook)
    btn_close = tk.Button(parent, text=tr("browser_btn_close", "Close"), font=("Segoe UI", 9, "bold"), bg=controller.c_panel_light, fg=controller.c_text_bright, relief="flat", cursor="hand2", padx=18, pady=5, command=dlg.destroy)
    btn_close.pack(side=tk.BOTTOM, anchor="e", pady=(6, 0))

    # 3. Installation Guide Notebook
    nb = ttk.Notebook(parent, style="Custom.TNotebook")
    nb.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

    is_ar = tr("app_title", "").startswith("فقيه")
    tabs_data = [
        ("browser_tab_chrome", " Chrome & Brave ", "browser_guide_chrome",
         "1. Open Chrome or Brave and type chrome://extensions in the address bar.\n2. Turn ON 'Developer mode' using the toggle in the top-right corner.\n3. Click the 'Load unpacked' button at the top-left.\n4. Select the extension directory displayed above.\n5. The ⚡ Faqih Downloader icon will appear in your extensions bar!"),
        ("browser_tab_edge", " Microsoft Edge ", "browser_guide_edge",
         "1. Open Edge and navigate to edge://extensions in the address bar.\n2. Turn ON 'Developer mode' in the left-hand navigation sidebar.\n3. Click the 'Load unpacked' button.\n4. Select the extension directory displayed above.\n5. Pin the extension to your toolbar for one-click access."),
        ("browser_tab_firefox", " Mozilla Firefox ", "browser_guide_firefox",
         "1. Open Firefox and type about:debugging#/runtime/this-firefox in the address bar.\n2. Click the 'Load Temporary Add-on...' button.\n3. Select the 'manifest.json' file inside the extension folder.\n4. The extension is immediately loaded and connects to Faqih Downloader."),
    ]
    for tab_key, tab_def, guide_key, guide_def in tabs_data:
        t_frame = tk.Frame(nb, bg=controller.c_panel, padx=12, pady=8)
        nb.add(t_frame, text=tr(tab_key, tab_def))
        tk.Label(t_frame, text=tr(guide_key, guide_def), font=("Segoe UI", 9), bg=controller.c_panel, fg=controller.c_text_bright, justify=("right" if is_ar else "left"), anchor=("ne" if is_ar else "nw"), wraplength=max(500, dlg_w - 76)).pack(fill=tk.BOTH, expand=True, anchor=("ne" if is_ar else "nw"))


__all__ = ["build_extension_section"]
