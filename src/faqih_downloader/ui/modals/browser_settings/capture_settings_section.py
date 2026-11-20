"""
Capture settings section builder for browser settings dialog (clipboard monitor, startup auto-boot, tray minimization, auto-unpack).
"""
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ....config import get_setting, set_setting
from ....locales.i18n import tr
from ....services.startup_service import is_startup_enabled


def build_capture_settings_section(controller: Any, parent: Any, dlg: Any):
    """Constructs clipboard sniffer, auto-boot, system tray, and archive auto-unpack cards."""
    # 0. Zero-Install Universal Clipboard Sniffer Card (TDM Style)
    card_sniff = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_sniff.pack(fill=tk.X, pady=(0, 5))

    lbl_sniff_t = tk.Label(card_sniff, text=tr("browser_card_sniffer_title", "❐ ZERO-INSTALL CLIPBOARD MONITOR (SD SMART CAPTURE — ALL BROWSERS)"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_success)
    lbl_sniff_t.pack(anchor="w")

    sniff_row = tk.Frame(card_sniff, bg=controller.c_panel)
    sniff_row.pack(fill=tk.X, pady=(6, 0))

    lbl_sniff_desc = tk.Label(
        sniff_row,
        text=tr("browser_card_sniffer_desc", "Works 100% across ALL browsers (Chrome, Edge, Firefox, Brave, Opera, Safari) without any extension.\nJust right-click any link or video and choose 'Copy Link Address' — Smart Download catches it instantly!"),
        font=("Segoe UI", 8),
        bg=controller.c_panel,
        fg=controller.c_text_bright,
        justify="left"
    )
    lbl_sniff_desc.pack(side=tk.LEFT)

    def _update_dlg_sniff_btn():
        if controller._clipboard_sniffer_active:
            btn_dlg_sniff.configure(text=tr("btn_sniffer_active", "● Sniffer: Active"), fg=controller.c_success, bg=controller.c_panel_light)
        else:
            btn_dlg_sniff.configure(text=tr("btn_sniffer_paused", "○ Sniffer: Paused"), fg=controller.c_text_muted, bg=controller.c_panel)

    def _on_dlg_sniff_toggle():
        controller.toggle_clipboard_sniffer()
        _update_dlg_sniff_btn()

    btn_dlg_sniff = tk.Button(
        sniff_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        cursor="hand2",
        padx=10,
        command=_on_dlg_sniff_toggle
    )
    btn_dlg_sniff.pack(side=tk.RIGHT)
    _update_dlg_sniff_btn()

    # 3. Windows Startup Auto-Boot Card (Silent Background Mode)
    card_boot = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_boot.pack(fill=tk.X, pady=(0, 5))

    lbl_boot_title = tk.Label(card_boot, text=tr("browser_card_boot_title", "⚡ WINDOWS STARTUP AUTO-BOOT (SILENT BACKGROUND MODE)"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_accent)
    lbl_boot_title.pack(anchor="w")

    boot_row = tk.Frame(card_boot, bg=controller.c_panel)
    boot_row.pack(fill=tk.X, pady=(6, 0))

    lbl_boot_status = tk.Label(boot_row, text="", font=("Segoe UI", 9, "bold"), bg=controller.c_panel)
    lbl_boot_status.pack(side=tk.LEFT)

    def _update_dlg_boot_status():
        try:
            if not dlg.winfo_exists() or not lbl_boot_status.winfo_exists():
                return
        except Exception:
            return
        enabled = is_startup_enabled()
        if enabled:
            lbl_boot_status.configure(text=tr("browser_boot_enabled", "● Start with Windows: Enabled (Silent Background)"), fg=controller.c_success)
            btn_dlg_boot.configure(text=tr("browser_btn_boot_enabled", "⚡ Start on Boot: Enabled"), fg=controller.c_success, bg=controller.c_panel_light)
        else:
            lbl_boot_status.configure(text=tr("browser_boot_disabled", "● Start with Windows: Disabled"), fg=controller.c_warning)
            btn_dlg_boot.configure(text=tr("browser_btn_boot_disabled", "⚡ Start on Boot: Disabled"), fg=controller.c_text_muted, bg=controller.c_panel)

    controller._update_dlg_startup_ui = _update_dlg_boot_status
    try:
        dlg.bind("<Destroy>", lambda e: setattr(controller, "_update_dlg_startup_ui", None) if e.widget == dlg else None, add="+")
    except Exception:
        pass

    def _on_dlg_boot_toggle():
        controller.toggle_startup_setting()
        _update_dlg_boot_status()

    btn_dlg_boot = tk.Button(
        boot_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        cursor="hand2",
        padx=10,
        command=_on_dlg_boot_toggle
    )
    btn_dlg_boot.pack(side=tk.RIGHT)
    _update_dlg_boot_status()

    # 3b. Windows System Tray & Background Minimization Card
    card_tray = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_tray.pack(fill=tk.X, pady=(0, 5))

    lbl_tray_title = tk.Label(card_tray, text=tr("browser_card_tray_title", "❖ WINDOWS SYSTEM TRAY & BACKGROUND MINIMIZATION"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_accent)
    lbl_tray_title.pack(anchor="w")

    tray_row = tk.Frame(card_tray, bg=controller.c_panel)
    tray_row.pack(fill=tk.X, pady=(6, 0))

    lbl_tray_status = tk.Label(tray_row, text="", font=("Segoe UI", 9, "bold"), bg=controller.c_panel)
    lbl_tray_status.pack(side=tk.LEFT)

    def _update_dlg_tray_status():
        try:
            if not dlg.winfo_exists() or not lbl_tray_status.winfo_exists():
                return
        except Exception:
            return
        enabled = getattr(controller, "minimize_to_tray", True)
        if enabled:
            lbl_tray_status.configure(text=tr("browser_tray_enabled", "● Close (✕) Action: Minimize to System Tray"), fg=controller.c_success)
            btn_dlg_tray.configure(text=tr("browser_btn_tray_enabled", "[✓] Minimize to System Tray on Close (✕)"), fg=controller.c_success, bg=controller.c_panel_light)
        else:
            lbl_tray_status.configure(text=tr("browser_tray_disabled", "● Close (✕) Action: Exit Application Completely"), fg=controller.c_warning)
            btn_dlg_tray.configure(text=tr("browser_btn_tray_disabled", "[  ] Minimize to System Tray on Close (✕)"), fg=controller.c_text_muted, bg=controller.c_panel)

    controller._update_dlg_tray_ui = _update_dlg_tray_status
    try:
        dlg.bind("<Destroy>", lambda e: (setattr(controller, "_update_dlg_startup_ui", None), setattr(controller, "_update_dlg_tray_ui", None)) if e.widget == dlg else None, add="+")
    except Exception:
        pass

    def _on_dlg_tray_toggle():
        controller.toggle_minimize_to_tray_setting()
        _update_dlg_tray_status()

    btn_dlg_tray = tk.Button(
        tray_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        cursor="hand2",
        padx=10,
        command=_on_dlg_tray_toggle
    )
    btn_dlg_tray.pack(side=tk.RIGHT)
    _update_dlg_tray_status()

    # 3c. Auto-Unpack Archives Card (AeroArchive Engine)
    card_unpack = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_unpack.pack(fill=tk.X, pady=(0, 5))

    lbl_unpack_title = tk.Label(card_unpack, text=tr("browser_card_unpack_title", "▣ AUTOMATIC ARCHIVE EXTRACTION (AEROARCHIVE ENGINE)"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_accent)
    lbl_unpack_title.pack(anchor="w")

    unpack_row = tk.Frame(card_unpack, bg=controller.c_panel)
    unpack_row.pack(fill=tk.X, pady=(6, 0))

    lbl_unpack_status = tk.Label(unpack_row, text="", font=("Segoe UI", 9, "bold"), bg=controller.c_panel)
    lbl_unpack_status.pack(side=tk.LEFT)

    def _update_dlg_unpack_status():
        try:
            if not dlg.winfo_exists() or not lbl_unpack_status.winfo_exists():
                return
        except Exception:
            return
        enabled = get_setting("auto_unpack_archives", False)
        if enabled:
            lbl_unpack_status.configure(text=tr("browser_unpack_enabled", "● Auto-Unpack: Enabled"), fg=controller.c_success)
            btn_dlg_unpack.configure(text=tr("browser_btn_unpack_enabled", "[✓] Auto-Unpack Archives after Download"), fg=controller.c_success, bg=controller.c_panel_light)
        else:
            lbl_unpack_status.configure(text=tr("browser_unpack_disabled", "● Auto-Unpack: Disabled"), fg=controller.c_warning)
            btn_dlg_unpack.configure(text=tr("browser_btn_unpack_disabled", "[  ] Auto-Unpack Archives after Download"), fg=controller.c_text_muted, bg=controller.c_panel)

    def _on_dlg_unpack_toggle():
        cur = get_setting("auto_unpack_archives", False)
        set_setting("auto_unpack_archives", not cur)
        _update_dlg_unpack_status()

    btn_dlg_unpack = tk.Button(
        unpack_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        relief="flat",
        cursor="hand2",
        padx=10,
        command=_on_dlg_unpack_toggle
    )
    btn_dlg_unpack.pack(side=tk.RIGHT)
    _update_dlg_unpack_status()


__all__ = ["build_capture_settings_section"]
