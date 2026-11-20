"""
Backward-compatibility shim for browser registration.
Re-exports functionality from extension_registry, host_registry, and browser_detector.
"""
try:
    from .host_manifest import (
        HOST_NAME,
        HOST_DESCRIPTION,
        APP_VERSION,
        LEGACY_HOST_NAME,
        LEGACY_CHROME_REG_KEY,
        LEGACY_EDGE_REG_KEY,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        CHROME_UPDATE_URL,
        EDGE_UPDATE_URL,
        STATIC_EXTENSION_ID,
        compute_unpacked_extension_id,
        get_project_root,
        get_default_extension_origins,
        generate_host_manifest,
        generate_launcher_batch,
    )
    from .extension_registry import (
        HAS_WINREG,
        register_browser_extensions,
        unregister_browser_extensions,
        is_extension_registered,
    )
    from .host_registry import (
        register_native_host,
        unregister_native_host,
        is_registered,
        get_status,
    )
    from .browser_detector import (
        check_and_register_browser,
        main,
    )
except (ImportError, ValueError):
    from host_manifest import (
        HOST_NAME,
        HOST_DESCRIPTION,
        APP_VERSION,
        LEGACY_HOST_NAME,
        LEGACY_CHROME_REG_KEY,
        LEGACY_EDGE_REG_KEY,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        CHROME_UPDATE_URL,
        EDGE_UPDATE_URL,
        STATIC_EXTENSION_ID,
        compute_unpacked_extension_id,
        get_project_root,
        get_default_extension_origins,
        generate_host_manifest,
        generate_launcher_batch,
    )
    from extension_registry import (
        HAS_WINREG,
        register_browser_extensions,
        unregister_browser_extensions,
        is_extension_registered,
    )
    from host_registry import (
        register_native_host,
        unregister_native_host,
        is_registered,
        get_status,
    )
    from browser_detector import (
        check_and_register_browser,
        main,
    )

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore

__all__ = [
    "HOST_NAME",
    "HOST_DESCRIPTION",
    "APP_VERSION",
    "LEGACY_HOST_NAME",
    "LEGACY_CHROME_REG_KEY",
    "LEGACY_EDGE_REG_KEY",
    "CHROME_REG_KEY",
    "EDGE_REG_KEY",
    "CHROME_EXT_KEY_PREFIX",
    "EDGE_EXT_KEY_PREFIX",
    "CHROME_UPDATE_URL",
    "EDGE_UPDATE_URL",
    "STATIC_EXTENSION_ID",
    "compute_unpacked_extension_id",
    "get_project_root",
    "get_default_extension_origins",
    "generate_host_manifest",
    "generate_launcher_batch",
    "HAS_WINREG",
    "winreg",
    "register_browser_extensions",
    "unregister_browser_extensions",
    "is_extension_registered",
    "register_native_host",
    "unregister_native_host",
    "is_registered",
    "get_status",
    "check_and_register_browser",
    "main",
]

if __name__ == "__main__":
    main()
