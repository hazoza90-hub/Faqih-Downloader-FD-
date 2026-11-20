"""
Idempotent, self-healing browser integration detector and registration CLI for Faqih Downloader.
"""
import os
import sys
import json
import time
from typing import Dict, Optional, Any

try:
    from .host_manifest import (
        HOST_NAME,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        STATIC_EXTENSION_ID,
        get_project_root,
    )
except (ImportError, ValueError):
    from host_manifest import (
        HOST_NAME,
        CHROME_REG_KEY,
        EDGE_REG_KEY,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        STATIC_EXTENSION_ID,
        get_project_root,
    )

from .extension_registry import register_browser_extensions as _local_register_extensions
from .host_registry import (
    register_native_host as _local_register_native_host,
    unregister_native_host as _local_unregister_native_host,
    get_status as _local_get_status,
)

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False


def _get_reg_op(name: str, fallback_fn: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.services.browser.registry")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback_fn


def check_and_register_browser(
    force: bool = False,
    target_dir: Optional[str] = None,
    extension_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Idempotent and self-healing browser integration registration:
    1. Idempotent check (< 5ms): checks if NativeMessagingHosts registry keys for Chrome & Edge
       exist, point to the current manifest path, and the manifest file exists on disk.
    2. Also checks if extension registry keys exist.
    3. If already registered with the correct path, skips silently in < 5ms without overhead.
    4. If keys are missing or path changed, self-heals by cleanly updating the manifest
       and registry keys.
    """
    if not HAS_WINREG or not sys.platform.startswith("win"):
        return {"success": False, "skipped": True, "reason": "Not Windows OS"}

    t_start = time.perf_counter()

    if not target_dir:
        if getattr(sys, "frozen", False):
            target_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            target_dir = get_project_root()

    expected_manifest_path = os.path.normcase(os.path.abspath(os.path.join(target_dir, f"{HOST_NAME}.json")))
    ext_dir = os.path.join(target_dir, "extension")
    ext_id = extension_id or STATIC_EXTENSION_ID

    needs_registration = force

    if not needs_registration:
        # 1. Check manifest file existence and validate launcher target
        if not os.path.isfile(expected_manifest_path):
            needs_registration = True
        else:
            try:
                with open(expected_manifest_path, "r", encoding="utf-8") as mf:
                    mf_data = json.load(mf)
                mf_launcher = mf_data.get("path", "")
                if not mf_launcher or not os.path.isfile(mf_launcher):
                    needs_registration = True
                elif os.path.normcase(os.path.dirname(os.path.abspath(mf_launcher))) != os.path.normcase(os.path.abspath(target_dir)):
                    needs_registration = True
            except Exception:
                needs_registration = True

        if not needs_registration:
            # 2. Check Chrome NativeMessagingHost
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHROME_REG_KEY, 0, winreg.KEY_READ)
                val, _ = winreg.QueryValueEx(k, "")
                winreg.CloseKey(k)
                if not val or os.path.normcase(os.path.abspath(val)) != expected_manifest_path:
                    needs_registration = True
            except Exception:
                needs_registration = True

        if not needs_registration:
            # 3. Check Edge NativeMessagingHost
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, EDGE_REG_KEY, 0, winreg.KEY_READ)
                val, _ = winreg.QueryValueEx(k, "")
                winreg.CloseKey(k)
                if not val or os.path.normcase(os.path.abspath(val)) != expected_manifest_path:
                    needs_registration = True
            except Exception:
                needs_registration = True

        if not needs_registration:
            # 4. Check Chrome Extension key
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{CHROME_EXT_KEY_PREFIX}\{ext_id}", 0, winreg.KEY_READ)
                if os.path.isdir(ext_dir):
                    p_val, _ = winreg.QueryValueEx(k, "path")
                    if os.path.normcase(os.path.abspath(p_val)) != os.path.normcase(os.path.abspath(ext_dir)):
                        needs_registration = True
                winreg.CloseKey(k)
            except Exception:
                needs_registration = True

        if not needs_registration:
            # 5. Check Edge Extension key
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{EDGE_EXT_KEY_PREFIX}\{ext_id}", 0, winreg.KEY_READ)
                if os.path.isdir(ext_dir):
                    p_val, _ = winreg.QueryValueEx(k, "path")
                    if os.path.normcase(os.path.abspath(p_val)) != os.path.normcase(os.path.abspath(ext_dir)):
                        needs_registration = True
                winreg.CloseKey(k)
            except Exception:
                needs_registration = True

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    if not needs_registration:
        return {
            "success": True,
            "idempotent": True,
            "healed": False,
            "manifest_path": expected_manifest_path,
            "duration_ms": elapsed_ms,
            "message": "Already correctly registered (<5ms check)."
        }

    # Perform self-healing registration
    reg_host_fn = _get_reg_op("register_native_host", _local_register_native_host)
    reg_ext_fn = _get_reg_op("register_browser_extensions", _local_register_extensions)

    native_res = reg_host_fn(extension_id=ext_id, target_dir=target_dir)
    ext_res = reg_ext_fn(extension_id=ext_id, extension_dir=ext_dir if os.path.isdir(ext_dir) else None)

    total_ms = (time.perf_counter() - t_start) * 1000.0
    return {
        "success": native_res.get("success", False),
        "idempotent": False,
        "healed": True,
        "manifest_path": native_res.get("manifest_path", expected_manifest_path),
        "native_host": native_res,
        "extensions": ext_res,
        "duration_ms": total_ms
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Smart Download (SD) Browser Registration Utility")
    parser.add_argument("--register", action="store_true", help="Register Native Messaging Host in Windows Registry")
    parser.add_argument("--unregister", action="store_true", help="Unregister Native Messaging Host and Extensions")
    parser.add_argument("--status", action="store_true", help="Check current registration status")
    parser.add_argument("--check-and-register", action="store_true", help="Idempotent and self-healing registration check")
    parser.add_argument("--extension-id", type=str, default="", help="Optional extension ID to allow in manifest")

    args = parser.parse_args()

    unreg_fn = _get_reg_op("unregister_native_host", _local_unregister_native_host)
    status_fn = _get_reg_op("get_status", _local_get_status)
    check_fn = _get_reg_op("check_and_register_browser", check_and_register_browser)
    reg_fn = _get_reg_op("register_native_host", _local_register_native_host)

    if args.unregister:
        res = unreg_fn()
        print(json.dumps(res, indent=2))
    elif args.status:
        res = status_fn()
        print(json.dumps(res, indent=2))
    elif args.check_and_register:
        res = check_fn(extension_id=args.extension_id or None)
        print(json.dumps(res, indent=2))
    else:
        # Default action: register
        res = reg_fn(extension_id=args.extension_id or None)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
