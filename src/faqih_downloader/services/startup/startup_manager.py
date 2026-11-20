"""
Windows startup registration, query, and unregistration manager for Faqih Downloader.
"""
import os
import sys
import subprocess
from typing import Optional, Any

from ...config import IS_WINDOWS
from .constants import (
    WINDOWS_RUN_KEY,
    STARTUP_REG_KEY_NAME,
    LEGACY_STARTUP_REG_KEY_NAME,
    TASK_NAME,
    LEGACY_TASK_NAME,
    STARTUP_APPROVED_RUN_KEY,
    STARTUP_APPROVED_FOLDER_KEY,
    EXPLORER_SERIALIZE_KEY,
    ENABLED_STARTUP_BINARY,
)
from .command_resolver import (
    get_startup_folder,
    get_startup_command,
    _parse_startup_cmd,
)
from .shortcut_helper import _create_startup_shortcut

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


def _get_startup_attr(name: str, fallback_val: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.services.startup_service")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback_val


def is_startup_enabled() -> bool:
    """
    Checks if SmartDownload is currently registered to auto-run on Windows startup.
    Checks HKCU Run registry key and cleans up stale or broken keys pointing to missing binaries.
    Returns True if an active, valid auto-start mechanism exists, False otherwise.
    """
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    wreg = _get_startup_attr("winreg", winreg)
    if not is_win or wreg is None:
        return False
    try:
        with wreg.OpenKey(wreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, wreg.KEY_READ) as key:
            for k_name in (STARTUP_REG_KEY_NAME, LEGACY_STARTUP_REG_KEY_NAME):
                try:
                    val, _ = wreg.QueryValueEx(key, k_name)
                    if val and str(val).strip():
                        exe_path, args, script_path, _ = _parse_startup_cmd(str(val))
                        is_valid = False
                        if exe_path:
                            if script_path:
                                is_valid = os.path.isfile(exe_path) and os.path.isfile(script_path)
                            else:
                                is_valid = os.path.isfile(exe_path)

                        if is_valid:
                            return True
                        elif exe_path:
                            # Stale or broken key pointing to a missing binary or script: clean it up
                            try:
                                with wreg.OpenKey(wreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, wreg.KEY_SET_VALUE) as wkey:
                                    wreg.DeleteValue(wkey, k_name)
                            except Exception:
                                pass
                        else:
                            return True
                except FileNotFoundError:
                    pass
    except (FileNotFoundError, OSError):
        pass

    try:
        get_sf = _get_startup_attr("get_startup_folder", get_startup_folder)
        startup_dir = get_sf()
        if os.path.isdir(startup_dir):
            for sname in ("Smart Download (SD).lnk", "SmartDownload.lnk"):
                if os.path.isfile(os.path.join(startup_dir, sname)):
                    return True
    except Exception:
        pass
    return False


def enable_startup(minimized: bool = True) -> bool:
    """
    Registers SmartDownload in HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
    When minimized=True, adds the --minimized flag so it starts silently in background.
    Cleans up any legacy (TurboDownloader) or stale keys, and coordinates with Scheduled
    Tasks and Startup folder shortcuts.
    Returns True on success, False otherwise.
    """
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    wreg = _get_startup_attr("winreg", winreg)
    if not is_win or wreg is None:
        return False

    get_cmd = _get_startup_attr("get_startup_command", get_startup_command)
    cmd = get_cmd(minimized=minimized)
    reg_ok = False
    try:
        with wreg.CreateKey(wreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            wreg.SetValueEx(key, STARTUP_REG_KEY_NAME, 0, wreg.REG_SZ, cmd)
            # Clean up legacy key
            try:
                wreg.DeleteValue(key, LEGACY_STARTUP_REG_KEY_NAME)
            except (FileNotFoundError, OSError):
                pass
        reg_ok = True
    except Exception:
        reg_ok = False

    if reg_ok:
        # Disable Windows 10/11 Explorer's 10-second artificial startup delay
        try:
            reg_dword = getattr(wreg, "REG_DWORD", 4)
            with wreg.CreateKey(wreg.HKEY_CURRENT_USER, EXPLORER_SERIALIZE_KEY) as key:
                wreg.SetValueEx(key, "StartupDelayInMSec", 0, reg_dword, 0)
                wreg.SetValueEx(key, "WaitForIdleState", 0, reg_dword, 0)
        except Exception:
            pass

        # Windows 10/11 StartupApproved binary registration
        try:
            with wreg.CreateKey(wreg.HKEY_CURRENT_USER, STARTUP_APPROVED_RUN_KEY) as key:
                wreg.SetValueEx(key, STARTUP_REG_KEY_NAME, 0, wreg.REG_BINARY, ENABLED_STARTUP_BINARY)
                try:
                    wreg.DeleteValue(key, LEGACY_STARTUP_REG_KEY_NAME)
                except (FileNotFoundError, OSError):
                    pass
        except Exception:
            pass

        try:
            with wreg.CreateKey(wreg.HKEY_CURRENT_USER, STARTUP_APPROVED_FOLDER_KEY) as key:
                wreg.SetValueEx(key, "Smart Download (SD).lnk", 0, wreg.REG_BINARY, ENABLED_STARTUP_BINARY)
                for leg in (LEGACY_STARTUP_REG_KEY_NAME, "TurboDownloader.lnk", "Turbo Download Manager Pro.lnk"):
                    try:
                        wreg.DeleteValue(key, leg)
                    except (FileNotFoundError, OSError):
                        pass
        except Exception:
            pass

        # Canonical Run key succeeded: delete duplicate Scheduled Tasks so Windows only launches 1 process
        try:
            for tname in (TASK_NAME, LEGACY_TASK_NAME):
                subprocess.run(
                    ["schtasks.exe", "/Delete", "/TN", tname, "/F"],
                    capture_output=True,
                    timeout=5
                )
        except Exception:
            pass

        # Actively clean up / remove duplicate Startup folder shortcuts
        try:
            get_sf = _get_startup_attr("get_startup_folder", get_startup_folder)
            startup_dir = get_sf()
            if os.path.isdir(startup_dir):
                for old in ("Smart Download (SD).lnk", "Turbo Download Manager Pro.lnk", "TurboDownloader.lnk", "SmartDownload.lnk"):
                    old_p = os.path.join(startup_dir, old)
                    if os.path.isfile(old_p):
                        try:
                            os.remove(old_p)
                        except Exception:
                            pass
        except Exception:
            pass
        return True

    exe_path, args, script_path, working_dir = _parse_startup_cmd(cmd)

    # Fallback 1: Scheduled Task
    try:
        if exe_path and os.path.isfile(exe_path):
            res = subprocess.run(
                ["schtasks.exe", "/Create", "/F", "/SC", "ONLOGON", "/TN", TASK_NAME, "/TR", cmd],
                capture_output=True,
                timeout=5
            )
            if res.returncode == 0:
                return True
    except Exception:
        pass

    # Fallback 2: Startup folder shortcut
    try:
        if exe_path and os.path.isfile(exe_path):
            get_sf = _get_startup_attr("get_startup_folder", get_startup_folder)
            startup_dir = get_sf()
            if os.path.isdir(startup_dir):
                for old in ("Turbo Download Manager Pro.lnk", "TurboDownloader.lnk", "SmartDownload.lnk"):
                    old_p = os.path.join(startup_dir, old)
                    if os.path.isfile(old_p):
                        try:
                            os.remove(old_p)
                        except Exception:
                            pass
                lnk_path = os.path.join(startup_dir, "Smart Download (SD).lnk")
                icon_path = ""
                for ico_cand in (
                    os.path.join(os.path.dirname(os.path.abspath(exe_path)), "app_icon.ico"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico") if "__file__" in globals() else "",
                    os.path.join(os.getcwd(), "app_icon.ico")
                ):
                    if ico_cand and os.path.isfile(ico_cand):
                        icon_path = os.path.abspath(ico_cand)
                        break

                create_sc = _get_startup_attr("_create_startup_shortcut", _create_startup_shortcut)
                return create_sc(
                    target_exe=exe_path,
                    shortcut_path=lnk_path,
                    arguments=args,
                    working_dir=working_dir,
                    icon_path=icon_path,
                    description="Smart Download (SD) AutoStart"
                )
    except Exception:
        pass

    return False


def disable_startup() -> bool:
    """
    Removes SmartDownload from HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
    Also cleans up Scheduled Tasks and Startup folder shortcuts.
    Returns True on success or if already absent, False on unexpected error.
    """
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    wreg = _get_startup_attr("winreg", winreg)
    if not is_win or wreg is None:
        return False

    reg_ok = True
    # 1. Clean up Run registry keys
    try:
        with wreg.OpenKey(wreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, wreg.KEY_SET_VALUE) as key:
            for k_name in (STARTUP_REG_KEY_NAME, LEGACY_STARTUP_REG_KEY_NAME):
                try:
                    wreg.DeleteValue(key, k_name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass
    except (OSError, PermissionError):
        reg_ok = False
    except Exception:
        reg_ok = False

    # 2. Clean up Scheduled Tasks
    try:
        for tname in (TASK_NAME, LEGACY_TASK_NAME):
            try:
                subprocess.run(
                    ["schtasks.exe", "/Delete", "/TN", tname, "/F"],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
    except Exception:
        pass

    # 3. Clean up Startup folder shortcuts
    try:
        get_sf = _get_startup_attr("get_startup_folder", get_startup_folder)
        startup_dir = get_sf()
        for name in ("Smart Download (SD).lnk", "SmartDownload.lnk", "TurboDownloader.lnk", "Turbo Download Manager Pro.lnk"):
            p = os.path.join(startup_dir, name)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass

    # 4. Clean up StartupApproved registry keys
    try:
        with wreg.OpenKey(wreg.HKEY_CURRENT_USER, STARTUP_APPROVED_RUN_KEY, 0, wreg.KEY_SET_VALUE) as key:
            for k in (STARTUP_REG_KEY_NAME, LEGACY_STARTUP_REG_KEY_NAME):
                try:
                    wreg.DeleteValue(key, k)
                except Exception:
                    pass
    except Exception:
        pass
    try:
        with wreg.OpenKey(wreg.HKEY_CURRENT_USER, STARTUP_APPROVED_FOLDER_KEY, 0, wreg.KEY_SET_VALUE) as key:
            for k in ("Smart Download (SD).lnk", LEGACY_STARTUP_REG_KEY_NAME, "SmartDownload.lnk", "TurboDownloader.lnk"):
                try:
                    wreg.DeleteValue(key, k)
                except Exception:
                    pass
    except Exception:
        pass

    return reg_ok


def get_startup_entry() -> Optional[str]:
    """Returns the registered command string from Windows Run registry, or None."""
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    wreg = _get_startup_attr("winreg", winreg)
    if not is_win or wreg is None:
        return None
    try:
        with wreg.OpenKey(wreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, wreg.KEY_READ) as key:
            for k_name in (STARTUP_REG_KEY_NAME, LEGACY_STARTUP_REG_KEY_NAME):
                try:
                    val, _ = wreg.QueryValueEx(key, k_name)
                    if val and str(val).strip():
                        return str(val)
                except FileNotFoundError:
                    pass
            return None
    except (FileNotFoundError, OSError):
        return None
