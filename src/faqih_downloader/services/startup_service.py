"""
Backward-compatibility shim for startup service.
Re-exports functionality from faqih_downloader.services.startup.*
"""
import os
import sys

from ..config import IS_WINDOWS

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    try:
        import winreg
    except ImportError:
        winreg = None
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_MINIMIZEBOX = 0x00020000
    WS_SYSMENU = 0x00080000
    SW_HIDE = 0
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    SW_SHOW = 5
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except Exception:
        user32 = None
        kernel32 = None
else:
    winreg = None
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_MINIMIZEBOX = 0x00020000
    WS_SYSMENU = 0x00080000
    SW_HIDE = 0
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    SW_SHOW = 5
    user32 = None
    kernel32 = None

from .startup import (
    WINDOWS_RUN_KEY,
    STARTUP_REG_KEY_NAME,
    LEGACY_STARTUP_REG_KEY_NAME,
    TASK_NAME,
    LEGACY_TASK_NAME,
    STARTUP_APPROVED_RUN_KEY,
    STARTUP_APPROVED_FOLDER_KEY,
    EXPLORER_SERIALIZE_KEY,
    ENABLED_STARTUP_BINARY,
    get_installed_exe_path,
    get_startup_folder,
    get_startup_dir,
    _parse_startup_cmd,
    _extract_exe_from_cmd,
    get_startup_command,
    _create_startup_shortcut,
    is_startup_enabled,
    enable_startup,
    disable_startup,
    get_startup_entry,
)

__all__ = [
    "IS_WINDOWS",
    "winreg",
    "GWL_STYLE",
    "GWL_EXSTYLE",
    "WS_EX_APPWINDOW",
    "WS_EX_TOOLWINDOW",
    "WS_MINIMIZEBOX",
    "WS_SYSMENU",
    "SW_HIDE",
    "SW_MINIMIZE",
    "SW_RESTORE",
    "SW_SHOW",
    "user32",
    "kernel32",
    "WINDOWS_RUN_KEY",
    "STARTUP_REG_KEY_NAME",
    "LEGACY_STARTUP_REG_KEY_NAME",
    "TASK_NAME",
    "LEGACY_TASK_NAME",
    "STARTUP_APPROVED_RUN_KEY",
    "STARTUP_APPROVED_FOLDER_KEY",
    "EXPLORER_SERIALIZE_KEY",
    "ENABLED_STARTUP_BINARY",
    "get_installed_exe_path",
    "get_startup_folder",
    "get_startup_dir",
    "_parse_startup_cmd",
    "_extract_exe_from_cmd",
    "get_startup_command",
    "_create_startup_shortcut",
    "is_startup_enabled",
    "enable_startup",
    "disable_startup",
    "get_startup_entry",
]
