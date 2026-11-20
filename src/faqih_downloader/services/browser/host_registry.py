"""
Native messaging host registration and status verification in Windows Registry for Chrome and Edge.
"""
import os
import sys
from typing import Dict, Optional, Any

try:
    from .host_manifest import (
        HOST_NAME,
        LEGACY_CHROME_REG_KEY,
        LEGACY_EDGE_REG_KEY,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        get_project_root,
        get_default_extension_origins,
        generate_host_manifest,
        generate_launcher_batch,
    )
except (ImportError, ValueError):
    from host_manifest import (
        HOST_NAME,
        LEGACY_CHROME_REG_KEY,
        LEGACY_EDGE_REG_KEY,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        get_project_root,
        get_default_extension_origins,
        generate_host_manifest,
        generate_launcher_batch,
    )

try:
    from .extension_registry import (
        register_browser_extensions as _local_register_extensions,
        unregister_browser_extensions as _local_unregister_extensions,
        is_extension_registered as _local_is_extension_registered,
    )
except (ImportError, ValueError):
    from extension_registry import (
        register_browser_extensions as _local_register_extensions,
        unregister_browser_extensions as _local_unregister_extensions,
        is_extension_registered as _local_is_extension_registered,
    )

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    winreg = None
    HAS_WINREG = False


def _get_winreg():
    for mod_name in ("faqih_downloader.services.browser.registry", "register_browser"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "winreg") and getattr(mod, "winreg") is not None:
            return getattr(mod, "winreg")
    return winreg


def _get_has_winreg():
    for mod_name in ("faqih_downloader.services.browser.registry", "register_browser"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "HAS_WINREG"):
            return getattr(mod, "HAS_WINREG")
    return HAS_WINREG


def _get_reg_op(name: str, fallback_fn: Any) -> Any:
    for mod_name in ("faqih_downloader.services.browser.registry", "register_browser"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, name):
            return getattr(mod, name)
    return fallback_fn


def register_native_host(
    extension_id: Optional[str] = None,
    target_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers the Native Messaging Host in Windows Registry for both Chrome and Edge:
    1. Creates launcher batch script.
    2. Writes host manifest JSON.
    3. Adds registry keys in HKCU for NativeMessagingHosts and Extensions.
    """
    wreg = _get_winreg()
    has_wreg = _get_has_winreg()
    if not has_wreg or not sys.platform.startswith("win") or wreg is None:
        return {
            "success": False,
            "error": "Windows Registry operations are only supported on Windows OS."
        }

    if not target_dir:
        if getattr(sys, "frozen", False):
            target_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            target_dir = get_project_root()

    os.makedirs(target_dir, exist_ok=True)

    bat_path = os.path.join(target_dir, "fd_host.bat")
    generate_launcher_batch(bat_path)

    json_path = os.path.join(target_dir, f"{HOST_NAME}.json")
    allowed_origins = get_default_extension_origins(extension_id=extension_id, target_dir=target_dir)
    manifest_abs_path = generate_host_manifest(bat_path, json_path, allowed_origins)

    # Actively remove stale legacy files from target_dir
    for stale_name in ("sd_host.bat", "turbo_host.bat", "com.smartdownload.host.json", "com.turbodownloader.host.json"):
        stale_p = os.path.join(target_dir, stale_name)
        if os.path.exists(stale_p):
            try:
                os.remove(stale_p)
            except Exception:
                pass

    # 2. Write Native Messaging Host to Windows Registry
    registry_results = {}
    for browser_name, reg_key_path in [
        ("Chrome", CHROME_REG_KEY),
        ("Edge", EDGE_REG_KEY)
    ]:
        try:
            key = wreg.CreateKey(wreg.HKEY_CURRENT_USER, reg_key_path)
            wreg.SetValue(key, "", wreg.REG_SZ, manifest_abs_path)
            wreg.CloseKey(key)
            registry_results[browser_name] = True
        except Exception:
            registry_results[browser_name] = False

        # Clean legacy keys (com.smartdownload.host and com.turbodownloader.host)
        for old_host in ("com.smartdownload.host", "com.turbodownloader.host"):
            try:
                old_k = reg_key_path.replace(HOST_NAME, old_host)
                wreg.DeleteKey(wreg.HKEY_CURRENT_USER, old_k)
            except Exception:
                pass

    # 3. Write Extension keys to Windows Registry
    ext_dir = os.path.join(target_dir, "extension")
    reg_ext_fn = _get_reg_op("register_browser_extensions", _local_register_extensions)
    ext_results = reg_ext_fn(
        extension_id=extension_id,
        extension_dir=ext_dir if os.path.isdir(ext_dir) else None
    )

    all_success = all(registry_results.values())
    return {
        "success": all_success,
        "manifest_path": manifest_abs_path,
        "launcher_path": os.path.abspath(bat_path),
        "registry": registry_results,
        "allowed_origins": allowed_origins,
        "extensions": ext_results
    }


def unregister_native_host(unregister_extensions: bool = True) -> Dict[str, Any]:
    """
    Removes native messaging registry entries for Chrome and Edge from HKCU.
    Also cleans up legacy SmartDownload and TurboDownloader host keys.
    Optionally unregisters extension keys.
    """
    wreg = _get_winreg()
    has_wreg = _get_has_winreg()
    if not has_wreg or not sys.platform.startswith("win") or wreg is None:
        return {
            "success": False,
            "error": "Windows Registry operations are only supported on Windows OS."
        }

    results = {}
    for browser_name, reg_key_path in [
        ("Chrome", CHROME_REG_KEY),
        ("Edge", EDGE_REG_KEY)
    ]:
        # Delete primary key
        try:
            wreg.DeleteKey(wreg.HKEY_CURRENT_USER, reg_key_path)
            results[browser_name] = True
        except FileNotFoundError:
            results[browser_name] = True
        except Exception:
            results[browser_name] = False

        # Clean legacy keys
        for old_host in ("com.smartdownload.host", "com.turbodownloader.host"):
            try:
                old_k = reg_key_path.replace(HOST_NAME, old_host)
                wreg.DeleteKey(wreg.HKEY_CURRENT_USER, old_k)
            except Exception:
                pass

    ext_results = None
    if unregister_extensions:
        unreg_ext_fn = _get_reg_op("unregister_browser_extensions", _local_unregister_extensions)
        ext_results = unreg_ext_fn()

    return {
        "success": all(results.values()),
        "registry": results,
        "extensions": ext_results
    }


def is_registered(browser: str = "chrome") -> bool:
    """
    Checks if Native Messaging Host registry key exists and points to a valid manifest file.
    Checks primary com.smartdownload.host first, then falls back to legacy com.turbodownloader.host.
    """
    wreg = _get_winreg()
    has_wreg = _get_has_winreg()
    if not has_wreg or not sys.platform.startswith("win") or wreg is None:
        return False

    is_chrome = browser.lower() == "chrome"
    primary_key = CHROME_REG_KEY if is_chrome else EDGE_REG_KEY
    legacy_key = LEGACY_CHROME_REG_KEY if is_chrome else LEGACY_EDGE_REG_KEY

    for reg_key_path in [primary_key, legacy_key]:
        try:
            key = wreg.OpenKey(wreg.HKEY_CURRENT_USER, reg_key_path, 0, wreg.KEY_READ)
            manifest_path, _ = wreg.QueryValueEx(key, "")
            wreg.CloseKey(key)
            if manifest_path and os.path.isfile(manifest_path):
                return True
        except Exception:
            continue
    return False


def get_status() -> Dict[str, Any]:
    """
    Returns registration status for Chrome and Edge along with manifest path.
    """
    is_reg_fn = _get_reg_op("is_registered", is_registered)
    is_ext_reg_fn = _get_reg_op("is_extension_registered", _local_is_extension_registered)

    chrome_ok = is_reg_fn("chrome")
    edge_ok = is_reg_fn("edge")
    chrome_ext_ok = is_ext_reg_fn("chrome")
    edge_ext_ok = is_ext_reg_fn("edge")

    manifest_path = ""
    wreg = _get_winreg()
    has_wreg = _get_has_winreg()
    if has_wreg and wreg is not None:
        for reg_key_path in [CHROME_REG_KEY, EDGE_REG_KEY]:
            try:
                key = wreg.OpenKey(wreg.HKEY_CURRENT_USER, reg_key_path, 0, wreg.KEY_READ)
                val, _ = wreg.QueryValueEx(key, "")
                wreg.CloseKey(key)
                if val:
                    manifest_path = val
                    break
            except Exception:
                pass

    return {
        "chrome_registered": chrome_ok,
        "edge_registered": edge_ok,
        "chrome_extension_registered": chrome_ext_ok,
        "edge_extension_registered": edge_ext_ok,
        "is_registered": chrome_ok or edge_ok,
        "manifest_path": manifest_path
    }
