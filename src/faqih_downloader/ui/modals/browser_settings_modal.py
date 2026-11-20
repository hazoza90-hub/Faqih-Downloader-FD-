"""
Backward-compatibility shim for browser_settings_modal.
Re-exports BrowserSettingsModalMixin and browser integration components.
"""
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = ttk = None  # type: ignore

from ...services.startup_service import IS_WINDOWS, is_startup_enabled
from ...services.browser.bridge_server import BrowserBridgeServer, DEFAULT_BRIDGE_PORT
from ...services.browser.registry import (
    register_native_host,
    unregister_native_host,
    check_and_register_browser,
    get_status as get_browser_reg_status,
)
from ..controllers.browser_controller import BrowserControllerMixin
from .browser_settings import (
    BrowserSettingsModalMixin,
    build_status_section,
    build_capture_settings_section,
    build_extension_section,
)

__all__ = [
    "BrowserSettingsModalMixin",
    "BrowserControllerMixin",
    "BrowserBridgeServer",
    "DEFAULT_BRIDGE_PORT",
    "register_native_host",
    "unregister_native_host",
    "check_and_register_browser",
    "get_browser_reg_status",
    "IS_WINDOWS",
    "is_startup_enabled",
    "build_status_section",
    "build_capture_settings_section",
    "build_extension_section",
]
