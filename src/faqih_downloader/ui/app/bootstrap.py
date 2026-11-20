"""
Application launch entry point, single-instance mutex enforcement, and CLI dispatch.
"""
from __future__ import annotations

import os
import sys
import json
import multiprocessing
from typing import Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ...config import get_resource_path, is_test_environment as _cfg_is_test_env
from ...locales.i18n import tr
from ...utils.dpi import enable_high_dpi_awareness
from ...services.single_instance import (
    acquire_single_instance_mutex as _svc_acquire_mutex,
    is_single_instance_mutex_held as _svc_is_mutex_held,
    notify_running_instance as _svc_notify_inst,
    release_single_instance_mutex as _svc_release_mutex,
)
from ...services.browser.registry import check_and_register_browser, unregister_native_host
from .gui import ModernFramelessGUI


def _get_mw_attr(name: str, fallback: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.ui.main_window")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback


def main():
    multiprocessing.freeze_support()

    # CLI handler for test mode or binary verification
    if "--test-startup" in sys.argv:
        try:
            from ...services import updater_service as updater
            from ...services import youtube_service as youtube_resolver
            from ...services.browser import bridge_server as browser_bridge
            from ...services.browser import native_host as native_messaging_host
            from ...services.browser import registry as register_browser
        except ImportError:
            import updater  # type: ignore
            import youtube_resolver  # type: ignore
            import browser_bridge  # type: ignore
            import native_messaging_host  # type: ignore
            import register_browser  # type: ignore
        import yt_dlp
        ico = get_resource_path("app_icon.ico")
        png = get_resource_path("app_icon.png")
        if not os.path.isfile(ico) or not os.path.isfile(png):
            os._exit(2)
        if not youtube_resolver.is_ytdlp_available():
            os._exit(1)
        os._exit(0)

    # CLI handler for Chrome/Edge Native Messaging Host execution
    if ("--native-host" in sys.argv or "--native-messaging-host" in sys.argv
            or any(arg.startswith("chrome-extension://") or arg.startswith("edge-extension://") for arg in sys.argv[1:])):
        try:
            from ...services.browser.native_host import run_host
        except ImportError:
            from native_messaging_host import run_host  # type: ignore
        run_host()
        return

    # CLI handler for browser registration
    if "--register-browser" in sys.argv:
        res = check_and_register_browser(force=True)
        print(json.dumps(res, indent=2))
        return

    if "--unregister-browser" in sys.argv:
        res = unregister_native_host()
        print(json.dumps(res, indent=2))
        return

    # CLI handler for uninstaller
    if any(arg.lower() in ("--uninstall", "-uninstall", "/uninstall", "/u", "-u", "--uninstall-gui") for arg in sys.argv[1:]):
        from ...installer.uninstaller_runner import handle_uninstall_cli
        handle_uninstall_cli()
        return

    # Check for CLI download URLs (e.g. TurboDownloader.exe https://example.com/file.zip)
    cli_url = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and not arg.startswith("/"):
            if arg.startswith("http://") or arg.startswith("https://") or arg.startswith("ftp://"):
                cli_url = arg.strip()
                break

    bg_flags = ("--background", "-background", "/background", "--minimized", "-minimized", "/minimized")
    start_in_background = any(arg.lower() in bg_flags for arg in sys.argv[1:])

    # Single-instance check: acquire Win32 Named Mutex and handle IPC forwarding
    is_test_env_fn = _get_mw_attr("is_test_environment", _cfg_is_test_env)
    if (
        not getattr(sys, "_sd_early_guard_checked", False)
        and not any(arg in sys.argv for arg in ("--force-new-instance", "--multi-instance"))
        and not is_test_env_fn()
    ):
        acquire_mutex_fn = _get_mw_attr("acquire_single_instance_mutex", _svc_acquire_mutex)
        is_held_fn = _get_mw_attr("is_single_instance_mutex_held", _svc_is_mutex_held)
        notify_inst_fn = _get_mw_attr("notify_running_instance", _svc_notify_inst)
        release_mutex_fn = _get_mw_attr("release_single_instance_mutex", _svc_release_mutex)

        if not is_held_fn() and not acquire_mutex_fn():
            if start_in_background:
                sys.exit(0)
            import time
            for _ in range(8):
                if notify_inst_fn(url=cli_url, show=True):
                    sys.exit(0)
                time.sleep(0.2)
        elif notify_inst_fn(url=cli_url, show=not start_in_background):
            release_mutex_fn()
            sys.exit(0)

    # Ensure Windows High-DPI Awareness is active before root creation
    enable_high_dpi_awareness()

    root = tk.Tk()
    root.title(tr("app_title", "فقيه التنزيلات (FD)"))

    # Set application icon on root window
    ico_path = get_resource_path("app_icon.ico")
    png_path = get_resource_path("app_icon.png")
    if os.path.isfile(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass
    if os.path.isfile(png_path):
        try:
            from PIL import Image, ImageTk
            with Image.open(png_path) as _im:
                _ico_img = ImageTk.PhotoImage(_im)
                root.iconphoto(True, _ico_img)
        except Exception:
            pass

    if start_in_background:
        try:
            root.withdraw()
        except Exception:
            pass

    gui_cls = _get_mw_attr("ModernFramelessGUI", ModernFramelessGUI)
    app = gui_cls(root, start_hidden=start_in_background, initial_url=cli_url)
    root.mainloop()


__all__ = ["main"]
