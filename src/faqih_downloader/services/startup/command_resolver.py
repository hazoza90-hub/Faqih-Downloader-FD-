"""
Executable resolution, startup command formatting, and command line parsing for Faqih Downloader.
"""
import os
import sys
from typing import Optional, Tuple, Any

from ...config import IS_WINDOWS

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


def _get_startup_attr(name: str, fallback_val: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.services.startup_service")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback_val


def get_installed_exe_path() -> Optional[str]:
    """Returns the canonical installed executable path if present on disk."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    for app_id, exe_name in (
        ("FaqihDownloader", "FaqihDownloader.exe"),
        ("SmartDownload", "SmartDownload.exe"),
        ("FaqihDownloader", "SmartDownload.exe"),
    ):
        cand = os.path.normpath(os.path.join(local_app_data, "Programs", app_id, exe_name))
        if os.path.isfile(cand):
            return cand
    return None


def get_startup_folder() -> str:
    """Returns the user Startup folder path (shell:startup)."""
    is_win = _get_startup_attr("IS_WINDOWS", IS_WINDOWS)
    wreg = _get_startup_attr("winreg", winreg)
    if is_win and wreg is not None:
        try:
            with wreg.OpenKey(wreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                raw_path, _ = wreg.QueryValueEx(k, "Startup")
                if raw_path and str(raw_path).strip():
                    expanded = os.path.normpath(os.path.expandvars(str(raw_path).strip()))
                    if os.path.isabs(expanded) and os.path.isdir(expanded):
                        return expanded
        except Exception:
            pass
    return os.path.normpath(os.path.join(
        os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming")),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    ))


get_startup_dir = get_startup_folder


def _parse_startup_cmd(cmd_str: str) -> Tuple[str, str, str, str]:
    """
    Parses a startup command string into:
    (exe_path, args, script_path, working_dir)
    Handles:
    - Standalone executables with/without quotes and arguments
    - Python script launches (e.g. "pythonw.exe" "script.py" --minimized)
    """
    if not cmd_str:
        return "", "", "", ""
    s = str(cmd_str).strip()
    if s.startswith('"'):
        end_idx = s.find('"', 1)
        if end_idx != -1:
            exe_path = s[1:end_idx].strip()
            rest = s[end_idx + 1:].strip()
        else:
            exe_path = s.strip('"')
            rest = ""
    else:
        parts = s.split(None, 1)
        exe_path = parts[0].strip()
        rest = parts[1].strip() if len(parts) > 1 else ""

    script_path = ""
    if os.path.basename(exe_path).lower() in ("python.exe", "pythonw.exe"):
        if rest.startswith('"'):
            s_end = rest.find('"', 1)
            if s_end != -1:
                script_path = rest[1:s_end].strip()
        elif rest:
            script_path = rest.split()[0].strip()

    working_dir = ""
    if script_path and os.path.isfile(script_path):
        working_dir = os.path.dirname(os.path.abspath(script_path))
    elif exe_path and os.path.isfile(exe_path):
        working_dir = os.path.dirname(os.path.abspath(exe_path))

    return exe_path, rest, script_path, working_dir


def _extract_exe_from_cmd(cmd_str: str) -> str:
    """Extracts target executable file path from command string."""
    exe_path, _, _, _ = _parse_startup_cmd(cmd_str)
    return exe_path


def get_startup_command(minimized: bool = True) -> str:
    """
    Constructs the command line string to launch SmartDownload on system startup.
    Accurately resolves executable path prioritizing:
    1. Active standalone frozen binary (.exe) if already running as frozen executable
    2. Canonical installed executable (%LocalAppData%\\Programs\\SmartDownload\\SmartDownload.exe)
    3. Standalone binary in dist/ directory or adjacent to script
    4. Python script fallback with pythonw.exe
    """
    flag = " --minimized" if minimized else ""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(str(sys.executable).strip('"'))
        return f'"{exe_path}"{flag}'

    # Check installed location first (%LOCALAPPDATA%\Programs\SmartDownload\SmartDownload.exe)
    installed_exe = get_installed_exe_path()
    if installed_exe:
        return f'"{installed_exe}"{flag}'

    # Prioritize compiled standalone binary in dist/ directory or adjacent to script
    search_dirs = [os.getcwd()]
    b = os.path.dirname(os.path.abspath(__file__))
    search_dirs.extend([
        b,
        os.path.abspath(os.path.join(b, "..")),
        os.path.abspath(os.path.join(b, "..", "..")),
        os.path.abspath(os.path.join(b, "..", "..", "..")),
        os.path.abspath(os.path.join(b, "..", "..", "..", "..")),
    ])
    for sd in search_dirs:
        for exe_name in ("FaqihDownloader.exe", "SmartDownload.exe", "TurboDownloader.exe"):
            cand = os.path.join(sd, "dist", exe_name)
            if os.path.isfile(cand):
                return f'"{os.path.abspath(cand)}"{flag}'
            cand2 = os.path.join(sd, exe_name)
            if os.path.isfile(cand2):
                return f'"{os.path.abspath(cand2)}"{flag}'

    # Script mode fallback: prefer pythonw.exe if available so no console window flashes
    py_exe = str(sys.executable).strip('"')
    py_dir = os.path.dirname(py_exe)
    pyw_exe = os.path.join(py_dir, "pythonw.exe")
    if os.path.isfile(pyw_exe):
        py_exe = pyw_exe
    script_path = None
    for sd in search_dirs:
        cand_script = os.path.join(sd, "turbo_downloader.py")
        if os.path.isfile(cand_script):
            script_path = os.path.abspath(cand_script)
            break
    if not script_path:
        script_path = os.path.abspath("turbo_downloader.py")
    return f'"{py_exe}" "{script_path}"{flag}'
