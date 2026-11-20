"""
System paths, shell folders (Desktop, Start Menu, Startup), and elevation checks for Faqih Downloader.
"""
import os
import sys

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

from .constants import get_default_install_dir, DEFAULT_INSTALL_DIR


def get_desktop_dir() -> str:
    """Gets the actual Desktop directory path, resolving OneDrive and Windows Shell redirection."""
    if HAS_WINREG and sys.platform.startswith("win"):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            raw_path, _ = winreg.QueryValueEx(k, "Desktop")
            winreg.CloseKey(k)
            expanded = os.path.normpath(os.path.expandvars(raw_path))
            if os.path.isdir(expanded):
                return expanded
        except Exception:
            pass
    # Fallback
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
    if os.path.isdir(onedrive_desktop):
        return onedrive_desktop
    return os.path.join(userprofile, "Desktop")


def get_start_menu_programs_dir() -> str:
    """Gets the user Start Menu Programs directory path."""
    if HAS_WINREG and sys.platform.startswith("win"):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            raw_path, _ = winreg.QueryValueEx(k, "Programs")
            winreg.CloseKey(k)
            expanded = os.path.normpath(os.path.expandvars(raw_path))
            if os.path.isdir(expanded):
                return expanded
        except Exception:
            pass
    # Fallback
    return os.path.normpath(os.path.join(os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming")),
                                        "Microsoft", "Windows", "Start Menu", "Programs"))


def get_startup_dir() -> str:
    """Gets the user Startup directory path (shell:startup)."""
    if HAS_WINREG and sys.platform.startswith("win"):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            raw_path, _ = winreg.QueryValueEx(k, "Startup")
            winreg.CloseKey(k)
            if raw_path and str(raw_path).strip():
                expanded = os.path.normpath(os.path.expandvars(str(raw_path).strip()))
                if os.path.isabs(expanded) and os.path.isdir(expanded):
                    return expanded
        except Exception:
            pass
    # Fallback
    return os.path.normpath(os.path.join(os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming")),
                                        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"))


def is_admin() -> bool:
    """Checks whether the current process has administrative elevation."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
