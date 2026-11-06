"""
CLI and GUI uninstallation dispatcher for Smart Download (SD).
"""
import os
import sys
import shutil
import tempfile
import subprocess
from typing import Optional, List

from .installer_ops import (
    DEFAULT_INSTALL_DIR,
    uninstall_application,
)


def _schedule_temp_uninstaller_cleanup() -> None:
    """Schedules self-cleanup of temporary uninstaller binary upon exit."""
    if getattr(sys, "frozen", False) and sys.platform.startswith("win"):
        try:
            import base64
            pid = os.getpid()
            self_exe = os.path.normcase(os.path.realpath(os.path.abspath(sys.executable)))
            temp_dir = os.path.normcase(os.path.realpath(os.path.abspath(tempfile.gettempdir())))
            is_in_temp = False
            try:
                is_in_temp = (os.path.commonpath([self_exe, temp_dir]) == temp_dir)
            except Exception:
                is_in_temp = False
            if is_in_temp or os.path.basename(self_exe).lower().startswith(("faqihdownloader-uninstaller", "smartdownload-uninstaller")):
                esc_exe = sys.executable.replace("'", "''")
                del_ps = (
                    f"Start-Sleep -Milliseconds 500; "
                    f"while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 250 }}; "
                    f"Remove-Item -Force -LiteralPath '{esc_exe}'"
                )
                b64_cmd = base64.b64encode(del_ps.encode("utf-16le")).decode("ascii")
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", b64_cmd],
                    creationflags=0x08000000
                )
        except Exception:
            pass


def _run_uninstaller_gui(target_dir: str) -> None:
    """Initializes and runs InstallerGUI in uninstall mode."""
    import tkinter as tk
    from .installer_gui import InstallerGUI
    root = tk.Tk()
    app = InstallerGUI(root, mode="uninstall", target_dir=target_dir)
    try:
        from ..config import is_test_environment
        if not is_test_environment():
            root.mainloop()
        else:
            try:
                root.destroy()
            except Exception:
                pass
    except Exception:
        root.mainloop()


def handle_uninstall_cli(argv: Optional[List[str]] = None) -> bool:
    """
    Handles --uninstall, /U, -u, --uninstall-gui, and --uninstall-worker CLI flags directly in SmartDownload.exe.
    Returns True if an uninstall action was handled and the process should exit.
    """
    args = argv if argv is not None else sys.argv[1:]
    args_lower = [a.lower() for a in args]

    uninstall_flags = {
        "--uninstall", "-uninstall", "/uninstall",
        "/u", "-u",
        "--uninstall-gui",
        "--uninstall-worker",
    }
    if not any(f in args_lower for f in uninstall_flags):
        return False

    is_silent = any(s in args_lower for s in ("--silent", "/s", "-s"))
    is_gui_worker = "--uninstall-gui" in args_lower
    is_worker = "--uninstall-worker" in args_lower

    # Determine target directory
    target_dir = None
    for idx, arg in enumerate(args):
        arg_lower = arg.lower()
        if arg_lower.startswith(("--dir=", "-dir=", "/dir=")):
            cand = arg.split("=", 1)[1].strip('"\' ')
            if cand and cand.lower() not in uninstall_flags and cand.lower() not in ("--silent", "/s", "-s", "--dir", "-dir", "/dir"):
                target_dir = cand
                break
        elif arg_lower in ("--dir", "-dir", "/dir") and idx + 1 < len(args):
            cand = args[idx + 1].strip('"\' ')
            if cand and cand.lower() not in uninstall_flags and cand.lower() not in ("--silent", "/s", "-s", "--dir", "-dir", "/dir"):
                target_dir = cand
                break

    if not target_dir:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            target_dir = exe_dir
        else:
            target_dir = DEFAULT_INSTALL_DIR

    target_dir = os.path.abspath(target_dir)

    is_frozen = getattr(sys, "frozen", False)
    running_in_target = False
    if is_frozen:
        try:
            exe_norm = os.path.normcase(os.path.realpath(os.path.abspath(sys.executable)))
            target_norm = os.path.normcase(os.path.realpath(os.path.abspath(target_dir)))
            running_in_target = (os.path.commonpath([exe_norm, target_norm]) == target_norm)
        except Exception:
            running_in_target = False

    # When frozen inside target_dir, clone executable to temporary directory so target_dir is not locked
    if is_frozen and running_in_target and not is_gui_worker and not is_worker:
        temp_candidates = [
            os.path.join(tempfile.gettempdir(), "FaqihDownloader-Uninstaller.exe"),
            os.path.join(tempfile.gettempdir(), f"FaqihDownloader-Uninstaller-{os.getpid()}.exe"),
            os.path.join(tempfile.gettempdir(), "SmartDownload-Uninstaller.exe"),
        ]
        cloned_and_spawned = False
        for temp_exe in temp_candidates:
            try:
                if os.path.isfile(temp_exe):
                    try:
                        os.chmod(temp_exe, 0o777)
                        os.remove(temp_exe)
                    except Exception:
                        pass
                shutil.copy2(sys.executable, temp_exe)
                if is_silent:
                    subprocess.Popen([temp_exe, "--uninstall-worker", "--silent", "--dir", target_dir])
                else:
                    subprocess.Popen([temp_exe, "--uninstall-gui", "--dir", target_dir])
                cloned_and_spawned = True
                break
            except Exception:
                continue

        if cloned_and_spawned:
            sys.exit(0)
            return True

    # 1. Worker mode (spawned from cloned temp uninstaller for silent execution)
    if is_worker:
        try:
            res = uninstall_application(target_dir=target_dir)
            sys.exit(0 if res.get("success") else 1)
        finally:
            _schedule_temp_uninstaller_cleanup()

    # 2. Silent uninstall mode (when invoked in non-frozen/out-of-target context)
    if is_silent:
        res = uninstall_application(target_dir=target_dir)
        sys.exit(0 if res.get("success") else 1)

    # 3. GUI worker mode (spawned from cloned temp uninstaller)
    if is_gui_worker:
        try:
            _run_uninstaller_gui(target_dir)
        finally:
            _schedule_temp_uninstaller_cleanup()
        sys.exit(0)

    # 4. Direct GUI uninstaller fallback (non-frozen or running outside target_dir)
    _run_uninstaller_gui(target_dir)
    sys.exit(0)
