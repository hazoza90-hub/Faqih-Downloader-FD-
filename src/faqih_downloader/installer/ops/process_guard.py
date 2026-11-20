"""
Running application process termination and test environment detection for Faqih Downloader installer.
"""
import os
import sys
import time
import subprocess


def _is_running_under_pytest() -> bool:
    """Checks whether code is executing in an automated pytest test environment."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules or os.environ.get("SD_TEST_ENV"))


def terminate_running_app():
    """Terminates active application processes to allow overwriting."""
    if not sys.platform.startswith("win"):
        return
    if _is_running_under_pytest():
        mock_mod = sys.modules.get("unittest.mock")
        mock_cls = getattr(mock_mod, "Mock", tuple()) if mock_mod else ()
        magic_cls = getattr(mock_mod, "MagicMock", tuple()) if mock_mod else ()
        is_mock = (
            isinstance(subprocess.run, (mock_cls, magic_cls))
            or hasattr(subprocess.run, "mock_calls")
            or hasattr(subprocess.run, "assert_called")
            or hasattr(os.kill, "mock_calls")
        )
        if not is_mock:
            return
    cur_pid = os.getpid()
    for proc in ("FaqihDownloader.exe", "SmartDownload.exe", "TurboDownloader.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/FI", f"PID ne {cur_pid}", "/IM", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception:
            pass
    time.sleep(0.3)


kill_running_instances = terminate_running_app
