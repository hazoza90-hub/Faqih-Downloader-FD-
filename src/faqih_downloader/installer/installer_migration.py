"""
Automatic migration module for Faqih Downloader (FD) v2.0.2.
Migrates history, settings, and cleans up legacy SmartDownload and TurboDownloader directories and registry keys.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from typing import Optional, Callable

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False


LEGACY_APP_DIRS = ["SmartDownload", "TurboDownloader"]
LEGACY_SHORTCUTS = [
    "Smart Download (SD).lnk",
    "SmartDownload.lnk",
    "Turbo Download Manager Pro.lnk",
    "TurboDownloader.lnk",
]
LEGACY_REG_KEYS = [
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartDownload",
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TurboDownloader",
]
LEGACY_RUN_KEYS = ["SmartDownload", "TurboDownloader"]


def terminate_all_instances():
    """Terminates any running instances of FaqihDownloader, SmartDownload, or TurboDownloader."""
    if not sys.platform.startswith("win"):
        return
    for proc in ("FaqihDownloader.exe", "SmartDownload.exe", "TurboDownloader.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5
            )
        except Exception:
            pass


def _get_target_data_dir() -> str:
    """Returns canonical data directory for FaqihDownloader."""
    cfg = os.environ.get("SD_CONFIG_DIR")
    if cfg:
        return cfg
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    target = os.path.join(appdata, "FaqihDownloader")
    os.makedirs(target, exist_ok=True)
    return target


def migrate_legacy_installations(
    new_install_dir: str,
    log_cb: Optional[Callable[[str], None]] = None
):
    """
    Performs full automated migration:
    1. Terminates any running processes.
    2. Migrates download_history.json and settings.json to new target.
    3. Removes legacy directories in %LOCALAPPDATA%\\Programs.
    4. Removes legacy Windows shortcuts.
    5. Cleans legacy registry keys.
    """
    def _log(msg: str):
        if log_cb:
            log_cb(msg)

    _log("[MIGRATION] Checking for legacy installations...")
    terminate_all_instances()

    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    target_data_dir = _get_target_data_dir()

    # 1. Migrate settings and download history
    data_files = ["download_history.json", "settings.json"]
    candidate_sources = []
    for old_name in LEGACY_APP_DIRS:
        candidate_sources.append(os.path.join(local_app_data, "Programs", old_name))
        candidate_sources.append(os.path.join(app_data, old_name))

    for src_dir in candidate_sources:
        if not os.path.isdir(src_dir):
            continue
        for df in data_files:
            src_f = os.path.join(src_dir, df)
            dst_f = os.path.join(target_data_dir, df)
            if os.path.isfile(src_f) and not os.path.isfile(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                    _log(f"[MIGRATION] Migrated {df} from {src_f} -> {dst_f}")
                except Exception as e:
                    _log(f"[MIGRATION] Warning copying {df}: {e}")

    # 2. Delete legacy installation directories
    for old_name in LEGACY_APP_DIRS:
        old_dir = os.path.join(local_app_data, "Programs", old_name)
        if os.path.isdir(old_dir) and os.path.abspath(old_dir) != os.path.abspath(new_install_dir):
            try:
                shutil.rmtree(old_dir, ignore_errors=True)
                _log(f"[MIGRATION] Removed legacy directory: {old_dir}")
            except Exception as e:
                _log(f"[MIGRATION] Warning removing {old_dir}: {e}")

    # 3. Clean legacy shortcuts
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    start_menu = os.path.join(app_data, r"Microsoft\Windows\Start Menu\Programs")
    startup = os.path.join(app_data, r"Microsoft\Windows\Start Menu\Programs\Startup")

    for loc in (desktop, start_menu, startup):
        if not os.path.isdir(loc):
            continue
        for sc in LEGACY_SHORTCUTS:
            sc_path = os.path.join(loc, sc)
            if os.path.isfile(sc_path):
                try:
                    os.remove(sc_path)
                    _log(f"[MIGRATION] Removed legacy shortcut: {sc_path}")
                except Exception:
                    pass

    # 4. Clean legacy registry entries
    if HAS_WINREG and sys.platform.startswith("win"):
        for reg_key in LEGACY_REG_KEYS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_key)
                _log(f"[MIGRATION] Deleted legacy uninstall key: {reg_key}")
            except Exception:
                pass
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            ) as k:
                for rk in LEGACY_RUN_KEYS:
                    try:
                        winreg.DeleteValue(k, rk)
                    except Exception:
                        pass
        except Exception:
            pass


def _is_safe_uninstall_target(target_dir: str) -> bool:
    r"""
    Validates that target_dir is safe for directory-level uninstallation/deletion.
    Rejects empty paths, drive roots (C:\, D:\, /), user home, standard system and user folders,
    and %LOCALAPPDATA%\Programs. Allows dedicated app subdirectories (including temp subdirectories).
    """
    if not target_dir or not isinstance(target_dir, str):
        return False
    clean = target_dir.strip()
    if not clean:
        return False
    norm = os.path.normcase(os.path.abspath(clean)).rstrip("\\/")
    if not norm:
        return False
    if os.path.dirname(norm) == norm or norm.endswith(":") or norm == "\\":
        return False

    blocked_paths = set()
    env_keys = [
        "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA",
        "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
        "SystemRoot", "WINDIR", "TEMP", "TMP"
    ]
    for k in env_keys:
        val = os.environ.get(k)
        if val:
            blocked_paths.add(os.path.normcase(os.path.abspath(val)).rstrip("\\/"))

    home = os.path.expanduser("~")
    if home:
        home_norm = os.path.normcase(os.path.abspath(home)).rstrip("\\/")
        blocked_paths.add(home_norm)
        user_folders = [
            "Desktop", "Downloads", "Documents", "Pictures",
            "Videos", "Music", "OneDrive",
            os.path.join("OneDrive", "Desktop"),
            os.path.join("OneDrive", "Documents"),
        ]
        for uf in user_folders:
            blocked_paths.add(os.path.normcase(os.path.abspath(os.path.join(home, uf))).rstrip("\\/"))

    localapp = os.environ.get("LOCALAPPDATA")
    if localapp:
        blocked_paths.add(os.path.normcase(os.path.abspath(os.path.join(localapp, "Programs"))).rstrip("\\/"))

    if norm in blocked_paths:
        return False

    return True


def _spawn_encoded_dir_cleanup(target_dir: str) -> None:
    """Spawns an asynchronous detached PowerShell watcher using Base64 encoded command without shell=True."""
    if not sys.platform.startswith("win"):
        return
    import base64
    pid = os.getpid()
    esc_target = target_dir.replace("'", "''")
    clean_ps = (
        f"Start-Sleep -Milliseconds 400; "
        f"while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 250 }}; "
        f"Start-Sleep -Milliseconds 200; "
        f"Remove-Item -Recurse -Force -LiteralPath '{esc_target}'"
    )
    b64_cmd = base64.b64encode(clean_ps.encode("utf-16le")).decode("ascii")
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", b64_cmd],
            creationflags=0x08000000
        )
    except Exception:
        pass


def extract_payload_lzma_archive(archive_path: str, target_dir: str) -> bool:
    """
    Extracts high-compression payload.lzma.zip containing heavy binaries
    (FaqihDownloader.exe and ffmpeg.exe) directly into target_dir.
    """
    import zipfile
    if not archive_path or not os.path.isfile(archive_path):
        return False
    try:
        target_dir = os.path.abspath(target_dir)
        target_dir_norm = os.path.normcase(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise RuntimeError(f"Corrupted file in installer payload archive: {bad}")
            for member in zf.infolist():
                target_file_norm = os.path.normcase(os.path.abspath(os.path.join(target_dir, member.filename)))
                if not (target_file_norm == target_dir_norm or target_file_norm.startswith(target_dir_norm + os.sep)):
                    raise RuntimeError(f"Unsafe zip member path traversal blocked: {member.filename}")
                target_file = os.path.abspath(os.path.join(target_dir, member.filename))
                if member.is_dir():
                    os.makedirs(target_file, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)
                    with zf.open(member) as src, open(target_file, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        return True
    except Exception as e:
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        return False


__all__ = [
    "terminate_all_instances",
    "migrate_legacy_installations",
    "extract_payload_lzma_archive",
    "_is_safe_uninstall_target",
    "_spawn_encoded_dir_cleanup",
]
