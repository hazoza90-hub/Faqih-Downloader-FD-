"""
Windows startup shortcut (.lnk) creation utilities using WScript.Shell and PowerShell fallbacks.
"""
import os
import sys
import subprocess
from typing import Any

from ...config import IS_WINDOWS


def _get_startup_attr(name: str, fallback_val: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.services.startup_service")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback_val


def _create_startup_shortcut(
    target_exe: str,
    shortcut_path: str,
    arguments: str = "",
    working_dir: str = "",
    icon_path: str = "",
    description: str = "Smart Download (SD) AutoStart"
) -> bool:
    """Creates a Windows shortcut (.lnk) with win32com and PowerShell fallback."""
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    if not is_win:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(shortcut_path)), exist_ok=True)
    except Exception:
        pass

    clean_target = str(target_exe).strip('"\'')
    clean_shortcut = str(shortcut_path).strip('"\'')
    clean_working = str(working_dir).strip('"\'') if working_dir else os.path.dirname(os.path.abspath(clean_target))

    # 1. Try win32com WScript.Shell
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(os.path.abspath(clean_shortcut))
        shortcut.TargetPath = os.path.abspath(clean_target)
        shortcut.WorkingDirectory = os.path.abspath(clean_working)
        if arguments:
            shortcut.Arguments = arguments
        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = f"{os.path.abspath(icon_path)},0"
        if description:
            shortcut.Description = description
        shortcut.Save()
        if os.path.exists(shortcut_path):
            return True
    except Exception:
        pass

    # 2. PowerShell fallback with single quote escaping
    try:
        def _ps_quote(s: str) -> str:
            return str(s).replace("'", "''")

        ps_icon = f"$s.IconLocation = '{_ps_quote(os.path.abspath(icon_path))},0'; " if (icon_path and os.path.exists(icon_path)) else ""
        ps_args = f"$s.Arguments = '{_ps_quote(arguments)}'; " if arguments else ""
        ps_script = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{_ps_quote(os.path.abspath(clean_shortcut))}'); "
            f"$s.TargetPath = '{_ps_quote(os.path.abspath(clean_target))}'; "
            f"$s.WorkingDirectory = '{_ps_quote(os.path.abspath(clean_working))}'; "
            f"{ps_args}"
            f"{ps_icon}"
            f"$s.Description = '{_ps_quote(description)}'; "
            f"$s.Save();"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )
        return res.returncode == 0 and os.path.exists(shortcut_path)
    except Exception:
        return False
