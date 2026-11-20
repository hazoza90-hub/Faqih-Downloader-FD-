"""
Installation constants and Windows Registry keys for Faqih Downloader.
"""
import os
from ..installer_registry import APP_ID


def get_default_install_dir() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.expanduser(r"~\AppData\Local")
    return os.path.normpath(os.path.join(local_app_data, "Programs", APP_ID))


DEFAULT_INSTALL_DIR = get_default_install_dir()
UNINSTALL_REG_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"

STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REG_KEY_NAME = "FaqihDownloader"
LEGACY_STARTUP_REG_KEY_NAME = "SmartDownload"
TASK_NAME = "FaqihDownloaderAutoStart"
LEGACY_TASK_NAME = "SmartDownloadAutoStart"
