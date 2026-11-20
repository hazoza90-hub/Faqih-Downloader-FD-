"""
Installer operations subpackage for Faqih Downloader:
- constants: Installation constants and registry keys
- paths: Desktop, start menu, and user startup directory resolvers
- process_guard: Process termination and running instance guards
- payload: Source binary discovery and resilient file copies
- installer_flow: Full application installation workflow
- uninstaller_flow: Clean uninstallation and registry removal
"""
from ..installer_registry import (
    create_windows_shortcut,
    register_startup_entries,
    unregister_startup_entries,
    register_uninstall_entry,
    unregister_uninstall_entry,
)
from .constants import (
    DEFAULT_INSTALL_DIR,
    UNINSTALL_REG_KEY,
    STARTUP_REG_KEY,
    STARTUP_REG_KEY_NAME,
    LEGACY_STARTUP_REG_KEY_NAME,
    TASK_NAME,
    LEGACY_TASK_NAME,
    get_default_install_dir,
)
from .paths import (
    get_desktop_dir,
    get_start_menu_programs_dir,
    get_startup_dir,
    is_admin,
)
from .process_guard import (
    _is_running_under_pytest,
    terminate_running_app,
    kill_running_instances,
)
from .payload import (
    find_payload_sources,
    get_payload_dir,
    _copy_file_with_retry,
)
from .installer_flow import (
    install_application,
    perform_installation,
    run_silent_install,
)
from .uninstaller_flow import (
    uninstall_application,
)

create_shortcut = create_windows_shortcut
register_uninstaller = register_uninstall_entry

__all__ = [
    "DEFAULT_INSTALL_DIR",
    "UNINSTALL_REG_KEY",
    "STARTUP_REG_KEY",
    "STARTUP_REG_KEY_NAME",
    "LEGACY_STARTUP_REG_KEY_NAME",
    "TASK_NAME",
    "LEGACY_TASK_NAME",
    "get_default_install_dir",
    "get_desktop_dir",
    "get_start_menu_programs_dir",
    "get_startup_dir",
    "is_admin",
    "_is_running_under_pytest",
    "terminate_running_app",
    "kill_running_instances",
    "find_payload_sources",
    "get_payload_dir",
    "_copy_file_with_retry",
    "install_application",
    "perform_installation",
    "run_silent_install",
    "uninstall_application",
    "create_windows_shortcut",
    "create_shortcut",
    "register_startup_entries",
    "unregister_startup_entries",
    "register_uninstall_entry",
    "register_uninstaller",
    "unregister_uninstall_entry",
]
