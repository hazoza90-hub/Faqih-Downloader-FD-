"""
Browser WebExtension registration and unregistration in Windows Registry for Chrome and Edge.
"""
import os
import sys
import json
from typing import Dict, List, Optional, Any

try:
    from .host_manifest import (
        APP_VERSION,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        CHROME_UPDATE_URL,
        EDGE_UPDATE_URL,
        STATIC_EXTENSION_ID,
        compute_unpacked_extension_id,
        get_project_root,
    )
except (ImportError, ValueError):
    from host_manifest import (
        APP_VERSION,
        CHROME_EXT_KEY_PREFIX,
        EDGE_EXT_KEY_PREFIX,
        CHROME_UPDATE_URL,
        EDGE_UPDATE_URL,
        STATIC_EXTENSION_ID,
        compute_unpacked_extension_id,
        get_project_root,
    )

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False


def register_browser_extensions(
    extension_id: Optional[str] = None,
    extension_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers the browser extension in Windows Registry for Chrome and Edge:
    - HKCU\\Software\\Google\\Chrome\\Extensions\\<extension_id>
    - HKCU\\Software\\Microsoft\\Edge\\Extensions\\<extension_id>
    Sets 'path', 'version', and 'update_url' where appropriate.
    """
    if not HAS_WINREG or not sys.platform.startswith("win"):
        return {
            "success": False,
            "error": "Windows Registry operations are only supported on Windows OS."
        }

    if not extension_dir:
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
            ext_candidate = os.path.join(base_dir, "extension")
            if not os.path.isdir(ext_candidate) and hasattr(sys, "_MEIPASS"):
                ext_candidate = os.path.join(sys._MEIPASS, "extension")
        else:
            ext_candidate = os.path.join(get_project_root(), "extension")
            if not os.path.isdir(ext_candidate):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                ext_candidate = os.path.join(base_dir, "extension")
        if os.path.isdir(ext_candidate):
            extension_dir = ext_candidate

    ids_to_register = [STATIC_EXTENSION_ID]
    if extension_dir and os.path.isdir(extension_dir):
        unpacked_id = compute_unpacked_extension_id(extension_dir)
        if unpacked_id not in ids_to_register:
            ids_to_register.append(unpacked_id)
    if extension_id and extension_id not in ids_to_register:
        clean_ext_id = extension_id.strip().rstrip("/").replace("chrome-extension://", "")
        if clean_ext_id not in ids_to_register:
            ids_to_register.append(clean_ext_id)

    ext_version = APP_VERSION
    if extension_dir and os.path.isfile(os.path.join(extension_dir, "manifest.json")):
        try:
            with open(os.path.join(extension_dir, "manifest.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                ext_version = data.get("version", APP_VERSION)
        except Exception:
            pass

    results = {}
    for ext_id in ids_to_register:
        # Chrome
        try:
            c_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{CHROME_EXT_KEY_PREFIX}\{ext_id}")
            if extension_dir and os.path.isdir(extension_dir):
                winreg.SetValueEx(c_key, "path", 0, winreg.REG_SZ, os.path.abspath(extension_dir))
            winreg.SetValueEx(c_key, "version", 0, winreg.REG_SZ, ext_version)
            winreg.SetValueEx(c_key, "update_url", 0, winreg.REG_SZ, CHROME_UPDATE_URL)
            winreg.CloseKey(c_key)
            results[f"Chrome_{ext_id}"] = True
        except Exception:
            results[f"Chrome_{ext_id}"] = False

        # Edge
        try:
            e_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{EDGE_EXT_KEY_PREFIX}\{ext_id}")
            if extension_dir and os.path.isdir(extension_dir):
                winreg.SetValueEx(e_key, "path", 0, winreg.REG_SZ, os.path.abspath(extension_dir))
            winreg.SetValueEx(e_key, "version", 0, winreg.REG_SZ, ext_version)
            winreg.SetValueEx(e_key, "update_url", 0, winreg.REG_SZ, EDGE_UPDATE_URL)
            winreg.CloseKey(e_key)
            results[f"Edge_{ext_id}"] = True
        except Exception:
            results[f"Edge_{ext_id}"] = False

    return {
        "success": any(results.values()) if results else False,
        "registered_ids": ids_to_register,
        "details": results
    }


def unregister_browser_extensions(extension_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Removes extension registry keys for Chrome and Edge from HKCU.
    """
    if not HAS_WINREG or not sys.platform.startswith("win"):
        return {
            "success": False,
            "error": "Windows Registry operations are only supported on Windows OS."
        }

    if extension_ids is None:
        extension_ids = [STATIC_EXTENSION_ID]
        if getattr(sys, "frozen", False):
            ext_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "extension")
        else:
            ext_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extension")
        if os.path.isdir(ext_dir):
            unpacked_id = compute_unpacked_extension_id(ext_dir)
            if unpacked_id not in extension_ids:
                extension_ids.append(unpacked_id)

    results = {}
    for ext_id in extension_ids:
        clean_ext_id = ext_id.strip().rstrip("/").replace("chrome-extension://", "")
        for browser_name, prefix in [("Chrome", CHROME_EXT_KEY_PREFIX), ("Edge", EDGE_EXT_KEY_PREFIX)]:
            full_key = rf"{prefix}\{clean_ext_id}"
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, full_key)
                results[f"{browser_name}_{clean_ext_id}"] = True
            except FileNotFoundError:
                results[f"{browser_name}_{clean_ext_id}"] = True
            except Exception:
                results[f"{browser_name}_{clean_ext_id}"] = False

    return {
        "success": all(results.values()) if results else True,
        "registry": results
    }


def is_extension_registered(browser: str = "chrome", extension_id: Optional[str] = None) -> bool:
    """Checks if browser extension registry key exists in HKCU."""
    if not HAS_WINREG or not sys.platform.startswith("win"):
        return False
    ext_id = extension_id or STATIC_EXTENSION_ID
    clean_ext_id = ext_id.strip().rstrip("/").replace("chrome-extension://", "")
    prefix = CHROME_EXT_KEY_PREFIX if browser.lower() == "chrome" else EDGE_EXT_KEY_PREFIX
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{prefix}\{clean_ext_id}", 0, winreg.KEY_READ)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False
