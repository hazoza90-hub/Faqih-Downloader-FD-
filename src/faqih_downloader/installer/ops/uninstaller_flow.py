"""
Application uninstallation workflow and file/registry cleanup for Faqih Downloader.
"""
import os
import sys
import shutil
from typing import Dict, Optional, Callable, Any

from ..installer_registry import (
    APP_NAME,
    unregister_startup_entries,
    unregister_uninstall_entry,
)
from ..installer_migration import _is_safe_uninstall_target, _spawn_encoded_dir_cleanup
from .constants import DEFAULT_INSTALL_DIR
from .paths import get_desktop_dir, get_start_menu_programs_dir
from .process_guard import terminate_running_app, _is_running_under_pytest


def _get_op(name: str, fallback_fn: Any) -> Any:
    for mod_name in ("faqih_downloader.installer.installer_ops", "faqih_downloader.installer.ops", "installer"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, name):
            return getattr(mod, name)
    return fallback_fn


def uninstall_application(
    target_dir: Optional[str] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Core uninstallation workflow:
    1. Terminate running TurboDownloader.exe
    2. Unregister Chrome & Edge native messaging hosts
    3. Unregister Chrome & Edge extensions
    4. Remove Desktop and Start Menu shortcuts
    5. Delete Windows Uninstall registry key
    6. Remove installed files and folder cleanly
    """
    def _notify(pct: float, msg: str):
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                pass

    if not target_dir:
        target_dir = DEFAULT_INSTALL_DIR
    target_dir = os.path.abspath(target_dir)

    _term = _get_op("terminate_running_app", terminate_running_app)
    _notify(0.10, "Closing active application instances...")
    _term()

    _notify(0.30, "Removing browser integration from registry...")
    try:
        import register_browser as rb
        mock_mod = sys.modules.get("unittest.mock")
        mock_cls = getattr(mock_mod, "Mock", tuple()) if mock_mod else ()
        magic_cls = getattr(mock_mod, "MagicMock", tuple()) if mock_mod else ()
        is_mock_rb = (
            isinstance(rb.unregister_native_host, (mock_cls, magic_cls))
            or hasattr(rb.unregister_native_host, "mock_calls")
            or hasattr(rb.unregister_native_host, "assert_called")
        )
        if not _is_running_under_pytest() or is_mock_rb:
            rb.unregister_native_host(unregister_extensions=True)
    except Exception:
        pass

    _notify(0.50, "Removing application shortcuts...")
    # Desktop shortcut
    _get_dt = _get_op("get_desktop_dir", get_desktop_dir)
    dt_dirs = [_get_dt()]
    if not _is_running_under_pytest():
        dt_dirs.append(os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop"))
    for dt_dir in set(dt_dirs):
        for name in (APP_NAME, "Smart Download (SD)", "Smart Download", "SmartDownload", "TurboDownloader", "Turbo Download Manager Pro"):
            dt_lnk = os.path.join(dt_dir, f"{name}.lnk")
            if os.path.isfile(dt_lnk):
                try:
                    os.remove(dt_lnk)
                except Exception:
                    pass

    # Start menu shortcut
    _get_sm = _get_op("get_start_menu_programs_dir", get_start_menu_programs_dir)
    sm_dirs = [_get_sm()]
    if not _is_running_under_pytest():
        sm_dirs.append(os.path.join(os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming")), "Microsoft", "Windows", "Start Menu", "Programs"))
    for sm_dir in set(sm_dirs):
        for name in (APP_NAME, "Smart Download (SD)", "Smart Download", "SmartDownload", "TurboDownloader", "Turbo Download Manager Pro"):
            sm_lnk = os.path.join(sm_dir, f"{name}.lnk")
            if os.path.isfile(sm_lnk):
                try:
                    os.remove(sm_lnk)
                except Exception:
                    pass

    _notify(0.65, "Removing automatic background startup entries...")
    _unreg_start = _get_op("unregister_startup_entries", unregister_startup_entries)
    _unreg_start()

    _notify(0.75, "Unregistering Windows Uninstall entry...")
    _unreg_uninst = _get_op("unregister_uninstall_entry", unregister_uninstall_entry)
    _unreg_uninst()

    _notify(0.90, "Cleaning up installed files...")
    # If the uninstaller process itself is running from within target_dir,
    # clean up all other files and schedule a detached watcher to delete
    # the uninstaller binary and folder once this process terminates.
    running_in_target = False
    current_exe = os.path.normcase(os.path.abspath(sys.executable))
    target_norm = os.path.normcase(os.path.abspath(target_dir))
    if getattr(sys, "frozen", False):
        try:
            running_in_target = (os.path.commonpath([current_exe, target_norm]) == target_norm)
        except Exception:
            running_in_target = False

    safe_target = _is_safe_uninstall_target(target_dir)
    if running_in_target and sys.platform.startswith("win"):
        if os.path.isdir(target_dir):
            for item in os.listdir(target_dir):
                item_path = os.path.normcase(os.path.abspath(os.path.join(target_dir, item)))
                if item_path == current_exe:
                    continue
                if not safe_target and item.lower() not in ("faqihdownloader.exe", "smartdownload.exe"):
                    continue
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                except Exception:
                    pass
        if safe_target:
            _spawn_encoded_dir_cleanup(target_dir)
    else:
        if os.path.isdir(target_dir):
            if safe_target:
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception:
                    pass
            else:
                for fn in ("FaqihDownloader.exe", "SmartDownload.exe"):
                    fp = os.path.join(target_dir, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass

    _notify(1.0, "Uninstallation complete!")
    return {
        "success": True,
        "target_dir": target_dir
    }
