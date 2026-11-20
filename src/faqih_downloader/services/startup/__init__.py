"""
Windows startup registry, Task Scheduler, and Startup shortcut management subpackage for Faqih Downloader:
- constants: Registry keys and Task Scheduler constants
- command_resolver: Installed executable and startup command resolvers
- shortcut_helper: Windows shortcut (.lnk) creation helper
- startup_manager: Startup enabled status, enable, disable, and query manager
"""
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
    get_installed_exe_path,
    get_startup_folder,
    get_startup_dir,
    _parse_startup_cmd,
    _extract_exe_from_cmd,
    get_startup_command,
)
from .shortcut_helper import (
    _create_startup_shortcut,
)
from .startup_manager import (
    is_startup_enabled,
    enable_startup,
    disable_startup,
    get_startup_entry,
)

__all__ = [
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
