"""
Status section builder for browser settings dialog (IPC loopback listener & Windows Registry Native Messaging).
"""
import json
import urllib.request
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ....locales.i18n import tr
from ....services.browser.bridge_server import BrowserBridgeServer, DEFAULT_BRIDGE_PORT
from ....services.browser.registry import (
    register_native_host,
    unregister_native_host,
    get_status as get_browser_reg_status,
)


def build_status_section(controller: Any, parent: Any, dlg: Any):
    """Constructs Local IPC Loopback Listener and Windows Registry Native Messaging status cards."""
    # 1. Server Status Card
    card_server = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_server.pack(fill=tk.X, pady=(0, 5))

    lbl_s_title = tk.Label(card_server, text=tr("browser_card_server_title", "LOCAL IPC LOOPBACK LISTENER"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_text_muted)
    lbl_s_title.pack(anchor="w")

    s_row = tk.Frame(card_server, bg=controller.c_panel)
    s_row.pack(fill=tk.X, pady=(6, 0))

    lbl_status = tk.Label(s_row, text="", font=("Segoe UI", 9, "bold"), bg=controller.c_panel)
    lbl_status.pack(side=tk.LEFT)

    def _update_server_status_label():
        if controller.bridge_server and controller.bridge_server.is_running:
            lbl_status.configure(text=tr("browser_server_active", f"● Active on http://{controller.bridge_server.host}:{controller.bridge_server.port}").format(host=controller.bridge_server.host, port=controller.bridge_server.port), fg=controller.c_success)
            btn_toggle_server.configure(text=tr("browser_btn_stop_server", "✕ Stop Server"), bg=controller.c_danger)
        else:
            lbl_status.configure(text=tr("browser_server_stopped", "● Listener Stopped / Offline"), fg=controller.c_danger)
            btn_toggle_server.configure(text=tr("browser_btn_start_server", "▶ Start Server"), bg=controller.c_success)

    def _toggle_bridge():
        if controller.bridge_server and controller.bridge_server.is_running:
            controller.bridge_server.stop()
        else:
            if not controller.bridge_server:
                controller.bridge_server = BrowserBridgeServer(
                    port=DEFAULT_BRIDGE_PORT,
                    on_download=controller._on_browser_download_received,
                    on_log=controller.log
                )
            controller.bridge_server.start()
        _update_server_status_label()

    def _test_ping():
        port = controller.bridge_server.port if controller.bridge_server else DEFAULT_BRIDGE_PORT
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/ping")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    controller.show_safe_info("Ping Successful", f"Loopback server is responding perfectly!\n\nApp: {data.get('app')}\nVersion: {data.get('version')}")
                    return
        except Exception as e:
            controller.show_safe_error("Ping Failed", f"Could not reach loopback server:\n\n{e}")

    btn_test = tk.Button(
        s_row,
        text=tr("browser_btn_test_ping", "⚡ Test Ping"),
        font=("Segoe UI", 8, "bold"),
        bg=controller.c_panel_light,
        fg=controller.c_text_bright,
        relief="flat",
        cursor="hand2",
        command=_test_ping
    )
    btn_test.pack(side=tk.RIGHT, padx=(6, 0))

    btn_toggle_server = tk.Button(
        s_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=10,
        command=_toggle_bridge
    )
    btn_toggle_server.pack(side=tk.RIGHT)
    _update_server_status_label()

    # 2. Windows Registry Native Messaging Integration Card
    card_reg = tk.Frame(parent, bg=controller.c_panel, padx=12, pady=6, highlightbackground=controller.c_border, highlightthickness=1)
    card_reg.pack(fill=tk.X, pady=(0, 5))

    lbl_reg_title = tk.Label(card_reg, text=tr("browser_card_reg_title", "WINDOWS REGISTRY DIRECT BROWSER LINK (NATIVE MESSAGING)"), font=("Segoe UI", 8, "bold"), bg=controller.c_panel, fg=controller.c_accent)
    lbl_reg_title.pack(anchor="w")

    reg_row = tk.Frame(card_reg, bg=controller.c_panel)
    reg_row.pack(fill=tk.X, pady=(6, 0))

    lbl_reg_status = tk.Label(reg_row, text="", font=("Segoe UI", 9, "bold"), bg=controller.c_panel)
    lbl_reg_status.pack(side=tk.LEFT)

    def _update_reg_status_label():
        status = get_browser_reg_status()
        if status.get("is_registered"):
            chrome_str = "Chrome ✓" if status.get("chrome_registered") else "Chrome ✕"
            edge_str = "Edge ✓" if status.get("edge_registered") else "Edge ✕"
            lbl_reg_status.configure(text=tr("browser_reg_active", f"● Registry Active: {chrome_str}  {edge_str} (com.smartdownload.host)").format(chrome=chrome_str, edge=edge_str), fg=controller.c_success)
            btn_reg.configure(text=tr("browser_btn_reregister", "↻ Re-Register"), bg=controller.c_panel_light)
        else:
            lbl_reg_status.configure(text=tr("browser_reg_inactive", "● Not Registered in Windows Registry"), fg=controller.c_warning)
            btn_reg.configure(text=tr("browser_btn_register", "⚡ 1-Click Register (Chrome & Edge)"), bg=controller.c_success)

    def _on_register_click():
        res = register_native_host()
        _update_reg_status_label()
        if res.get("success"):
            controller.show_safe_info(
                "Registration Successful! ⚡",
                "Native Messaging Host successfully linked in Windows Registry for Google Chrome and Microsoft Edge!\n\n"
                f"Host Name: com.smartdownload.host\n"
                f"Manifest: {res.get('manifest_path')}"
            )
        else:
            controller.show_safe_error("Registration Error", f"Failed to register in Windows Registry:\n\n{res.get('error', 'Unknown error')}")

    def _on_unregister_click():
        unregister_native_host()
        _update_reg_status_label()
        controller.show_safe_info("Unregistered", "Removed Native Messaging Host registry entries for Chrome & Edge.")

    btn_unreg = tk.Button(
        reg_row,
        text=tr("browser_btn_unregister", "Unregister"),
        font=("Segoe UI", 8),
        bg=controller.c_panel_light,
        fg=controller.c_text_muted,
        relief="flat",
        cursor="hand2",
        padx=8,
        command=_on_unregister_click
    )
    btn_unreg.pack(side=tk.RIGHT, padx=(6, 0))

    btn_reg = tk.Button(
        reg_row,
        text="",
        font=("Segoe UI", 8, "bold"),
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=12,
        command=_on_register_click
    )
    btn_reg.pack(side=tk.RIGHT)
    _update_reg_status_label()


__all__ = ["build_status_section"]
