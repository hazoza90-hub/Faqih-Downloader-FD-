# -*- coding: utf-8 -*-
"""
PyInstaller entry-point for FaqihDownloader-Setup.exe.
Maintained in scripts/ to avoid module/package name collisions with root faqih_downloader.py.
"""
import os
import sys
import json
import argparse
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_base_dir, "src")
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import faqih_downloader.services.browser.registry as _registry_mod
import faqih_downloader.services.browser.host_manifest as _host_manifest_mod

sys.modules.setdefault("register_browser", _registry_mod)
sys.modules.setdefault("host_manifest", _host_manifest_mod)

from faqih_downloader.installer import (
    APP_NAME,
    DEFAULT_INSTALL_DIR,
    install_application,
    uninstall_application,
    InstallerGUI,
)


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Installer & Setup Utility", prefix_chars="-/")
    parser.add_argument("--silent", "/S", "-s", action="store_true", help="Run unattended installation/uninstallation")
    parser.add_argument("--uninstall", "/U", "-u", action="store_true", help="Uninstall application")
    parser.add_argument("--dir", type=str, default=DEFAULT_INSTALL_DIR, help="Target installation folder")
    parser.add_argument("--no-launch", action="store_true", help="Do not launch application after installation")
    parser.add_argument("--launch", action="store_true", help="Launch application after silent installation")
    parser.add_argument("--no-shortcuts", action="store_true", help="Do not create desktop or start menu shortcuts")
    parser.add_argument("--no-browser", action="store_true", help="Do not register browser native messaging")
    parser.add_argument("--no-startup", action="store_true", help="Do not register auto-start on boot")

    args, _ = parser.parse_known_args()

    exe_name = os.path.basename(sys.executable).lower()
    mode = "uninstall" if (args.uninstall or "/U" in sys.argv or "--uninstall" in sys.argv or "uninstall" in exe_name) else "install"
    silent = args.silent or "/S" in sys.argv or "--silent" in sys.argv

    target_dir = args.dir
    if mode == "uninstall" and args.dir == DEFAULT_INSTALL_DIR:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(exe_dir, "SmartDownload.exe")) or os.path.isfile(os.path.join(exe_dir, "TurboDownloader.exe")):
            target_dir = exe_dir

    if silent:
        if mode == "install":
            res = install_application(
                target_dir=target_dir,
                create_desktop=not args.no_shortcuts,
                create_start_menu=not args.no_shortcuts,
                register_browser=not args.no_browser,
                register_startup=not args.no_startup,
            )
            if args.launch and res.get("success") and os.path.isfile(res.get("exe_path", "")):
                try:
                    subprocess.Popen([res["exe_path"]], cwd=os.path.dirname(res["exe_path"]))
                except Exception:
                    pass
            print(json.dumps(res, indent=2))
            sys.exit(0 if res.get("success") else 1)
        else:
            res = uninstall_application(target_dir=target_dir)
            print(json.dumps(res, indent=2))
            sys.exit(0 if res.get("success") else 1)

    import tkinter as tk
    root = tk.Tk()
    InstallerGUI(root, mode=mode, target_dir=target_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
