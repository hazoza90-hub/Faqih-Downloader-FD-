"""
Automated Test Module for Smart Download (SD)
"""
import os
import sys
import tempfile
import time
import json
import shutil
import struct
import hashlib
import ssl
import re
import unittest
import threading
import subprocess
import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
from unittest.mock import patch, MagicMock
from typing import List, Dict, Optional, Tuple, Any

# Ensure project root and src/ are in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ["SD_DISABLE_SYSTEM_TRAY"] = "1"
os.environ["SD_DISABLE_STARTUP_TOAST"] = "1"
os.environ["SD_DISABLE_AUTO_UPDATE"] = "1"
os.environ["SD_LANGUAGE"] = "en"
try:
    import pytest
except ImportError:
    pytest = None

if pytest is not None:
    @pytest.fixture(autouse=True)
    def isolate_installer_system(tmp_path):
        """Autouse fixture isolating tests from real user desktop, start menu, startup folder, and registry."""
        fake_dt = str(tmp_path / "FakeDesktop")
        fake_sm = str(tmp_path / "FakeStartMenu")
        fake_su = str(tmp_path / "FakeStartup")
        os.makedirs(fake_dt, exist_ok=True)
        os.makedirs(fake_sm, exist_ok=True)
        os.makedirs(fake_su, exist_ok=True)

        # Backup HKCU Run and Uninstall registry entries if on Windows
        saved_run_val = None
        saved_uninst_vals = None
        has_winreg = False
        try:
            import winreg
            has_winreg = True
        except ImportError:
            has_winreg = False

        if has_winreg and sys.platform.startswith("win"):
            # Backup Run value
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as rk:
                    saved_run_val = winreg.QueryValueEx(rk, "FaqihDownloader")
            except Exception:
                saved_run_val = None

            # Backup Uninstall values
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FaqihDownloader", 0, winreg.KEY_READ) as uk:
                    saved_uninst_vals = []
                    info = winreg.QueryInfoKey(uk)
                    for i in range(info[1]):
                        saved_uninst_vals.append(winreg.EnumValue(uk, i))
            except Exception:
                saved_uninst_vals = None

        with patch("faqih_downloader.installer.installer_ops.get_desktop_dir", return_value=fake_dt), \
             patch("faqih_downloader.installer.installer_ops.get_start_menu_programs_dir", return_value=fake_sm), \
             patch("faqih_downloader.installer.installer_registry.get_startup_dir", return_value=fake_su):
            try:
                yield
            finally:
                if has_winreg and sys.platform.startswith("win"):
                    # Restore Run key
                    if saved_run_val is not None:
                        try:
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as rk:
                                winreg.SetValueEx(rk, "FaqihDownloader", 0, saved_run_val[1], saved_run_val[0])
                        except Exception:
                            pass
                    # Restore Uninstall key
                    if saved_uninst_vals is not None:
                        try:
                            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\FaqihDownloader") as uk:
                                for name, val, typ in saved_uninst_vals:
                                    winreg.SetValueEx(uk, name, 0, typ, val)
                        except Exception:
                            pass

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None  # type: ignore
    ttk = None  # type: ignore

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from youtube_resolver import (
    is_youtube_url,
    is_social_media_url,
    is_media_url,
    extract_youtube_id,
    extract_media_platform,
    extract_media_id,
    sanitize_filename,
    is_ytdlp_available,
    has_ffmpeg,
    find_ffmpeg_bin,
    update_ytdlp_engine,
    get_ytdlp_version,
    YouTubeResolver,
    MediaResolver,
    YouTubeStreamInfo,
    MediaStreamInfo,
    VideoFormatOption,
    format_filesize,
    SUPPORTED_COOKIE_BROWSERS,
    detect_installed_cookie_browsers,
)
from browser_bridge import BrowserBridgeServer, BrowserBridgeHandler, DEFAULT_BRIDGE_PORT
from native_messaging_host import read_message, send_message, handle_payload
from register_browser import (
    register_native_host,
    unregister_native_host,
    check_and_register_browser,
    register_browser_extensions,
    unregister_browser_extensions,
    is_extension_registered,
    is_registered as is_browser_registered,
    get_status as get_browser_reg_status,
    compute_unpacked_extension_id,
    generate_host_manifest,
    get_default_extension_origins,
)
import installer
from turbo_downloader import (
    TurboDownloadEngine,
    SmartDownloadEngine,
    StreamDownloadCoordinator,
    TokenBucketRateLimiter,
    get_permissive_ssl_context,
    SafeModalDialog,
    ModernFramelessGUI,
    QualitySelectionModal,
    DownloadConfirmationModal,
    FetchingLinkToast,
    validate_refresh_url,
    RefreshLinkModal,
    RefreshLinkDialog,
    DownloadChunk,
    is_downloadable_url,
    get_clipboard_text,
    derive_download_filename,
    COMMON_DOWNLOAD_EXTENSIONS,
    is_startup_enabled,
    enable_startup,
    disable_startup,
    get_startup_command,
    get_startup_entry,
    notify_running_instance,
    WINDOWS_RUN_KEY,
    STARTUP_REG_KEY_NAME,
    SystemTrayManager,
    load_settings,
    save_settings,
    get_setting,
    set_setting,
    parse_speed_limit,
    open_downloaded_file,
    open_containing_folder,
    CATEGORY_SUBFOLDERS,
    resolve_categorized_path,
    DownloadHistoryManager,
    get_app_config_dir,
    resolve_real_download_url,
    StartupWelcomeToast,
    LocalizationManager,
    enable_high_dpi_awareness,
    get_resource_path,
)


def setUpModule():
    os.environ["SD_LANGUAGE"] = "en"
    try:
        set_setting("language", "en")
        LocalizationManager.reset_instance("en")
    except Exception:
        pass


def tearDownModule():
    try:
        LocalizationManager.reset_instance()
    except Exception:
        pass

class TestWindowsInstallerLogic(unittest.TestCase):
    """Verifies standalone Windows Installer logic, zero-elevation paths, and shortcuts."""

    def test_default_install_dir_and_constants(self):
        self.assertEqual(installer.APP_ID, "FaqihDownloader")
        self.assertEqual(installer.APP_NAME, "Faqih Downloader (FD)")
        self.assertTrue(installer.DEFAULT_INSTALL_DIR.endswith(r"Programs\FaqihDownloader"))
        # Ensure path is user-level inside LocalAppData (zero admin/UAC elevation needed)
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            self.assertTrue(installer.DEFAULT_INSTALL_DIR.lower().startswith(local_app_data.lower()))

    def test_register_and_unregister_uninstall_entry(self):
        if not sys.platform.startswith("win"):
            self.skipTest("Windows Registry tests only run on Windows OS.")

        import tempfile, winreg
        with tempfile.TemporaryDirectory() as tmp_dir:
            exe_path = os.path.join(tmp_dir, "FaqihDownloader.exe")
            with open(exe_path, "w") as f:
                f.write("mock")
            uninst_path = os.path.join(tmp_dir, "Uninstall.exe")
            with open(uninst_path, "w") as f:
                f.write("mock")

            # Pre-create legacy uninstall key to simulate upgrading from old version
            legacy_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, installer.LEGACY_UNINSTALL_REG_KEY)
            winreg.SetValueEx(legacy_key, "DisplayName", 0, winreg.REG_SZ, "Legacy TurboDownloader")
            winreg.CloseKey(legacy_key)

            reg_ok = installer.register_uninstall_entry(tmp_dir, exe_path, uninst_path)
            self.assertTrue(reg_ok)

            # Query uninstall key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.UNINSTALL_REG_KEY)
            disp_name, _ = winreg.QueryValueEx(key, "DisplayName")
            uninst_cmd, _ = winreg.QueryValueEx(key, "UninstallString")
            quiet_uninst_cmd, _ = winreg.QueryValueEx(key, "QuietUninstallString")
            no_modify, _ = winreg.QueryValueEx(key, "NoModify")
            winreg.CloseKey(key)

            self.assertEqual(disp_name, "Faqih Downloader (FD)")
            # Verify legacy key was cleanly migrated/deleted
            with self.assertRaises(FileNotFoundError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.LEGACY_UNINSTALL_REG_KEY)
            self.assertIn("Uninstall.exe", uninst_cmd)
            self.assertIn("--uninstall", uninst_cmd)
            self.assertIn("--silent", quiet_uninst_cmd)
            self.assertEqual(no_modify, 1)

            # Clean up
            unreg_ok = installer.unregister_uninstall_entry()
            self.assertTrue(unreg_ok)

            # Verify key is gone
            with self.assertRaises(FileNotFoundError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.UNINSTALL_REG_KEY)

    def test_create_windows_shortcut(self):
        if not sys.platform.startswith("win"):
            self.skipTest("Shortcut test only runs on Windows OS.")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = os.path.join(tmp_dir, "app.exe")
            with open(target, "w") as f:
                f.write("mock")
            shortcut = os.path.join(tmp_dir, "TestShortcut.lnk")

            ok = installer.create_windows_shortcut(target, shortcut, description="Test App")
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(shortcut))

    def test_legacy_shortcuts_cleanup_on_upgrade(self):
        """Verifies that legacy Turbo Download Manager Pro.lnk shortcuts are cleaned up upon installation."""
        if not sys.platform.startswith("win"):
            self.skipTest("Windows shortcut test only runs on Windows OS.")

        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_desktop, \
             tempfile.TemporaryDirectory() as tmp_start, \
             tempfile.TemporaryDirectory() as tmp_target:

            legacy_dt_lnk = os.path.join(tmp_desktop, "Turbo Download Manager Pro.lnk")
            with open(legacy_dt_lnk, "w") as f:
                f.write("legacy shortcut")

            legacy_sm_lnk = os.path.join(tmp_start, "Turbo Download Manager Pro.lnk")
            with open(legacy_sm_lnk, "w") as f:
                f.write("legacy shortcut")

            with patch.object(installer, "get_desktop_dir", return_value=tmp_desktop), \
                 patch.object(installer, "get_start_menu_programs_dir", return_value=tmp_start), \
                 patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                 patch("faqih_downloader.installer.installer_ops.register_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"):
                res = installer.install_application(
                    target_dir=tmp_target,
                    create_desktop=True,
                    create_start_menu=True,
                    register_browser=False
                )
                self.assertTrue(res.get("success"))
                self.assertFalse(os.path.exists(legacy_dt_lnk), "Legacy desktop shortcut must be removed")
                self.assertFalse(os.path.exists(legacy_sm_lnk), "Legacy start menu shortcut must be removed")
                self.assertTrue(os.path.exists(os.path.join(tmp_desktop, f"{installer.APP_NAME}.lnk")), "New desktop shortcut must exist")

    def test_install_and_uninstall_lifecycle(self):
        if not sys.platform.startswith("win"):
            self.skipTest("Installer tests only run on Windows OS.")

        import tempfile
        progress_events = []

        def _cb(pct, msg):
            progress_events.append((pct, msg))

        with tempfile.TemporaryDirectory() as tmp_dir:
            install_target = os.path.join(tmp_dir, "InstalledTurbo")

            with patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                 patch("faqih_downloader.installer.installer_ops.register_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_uninstall_entry"):
                # Execute install into test folder
                res = installer.install_application(
                    target_dir=install_target,
                    create_desktop=False,
                    create_start_menu=False,
                    register_browser=False,
                    progress_cb=_cb
                )
                self.assertTrue(res.get("success"))
                self.assertTrue(os.path.isdir(install_target))
                self.assertTrue(os.path.isfile(os.path.join(install_target, "FaqihDownloader.exe")))
                self.assertFalse(os.path.isfile(os.path.join(install_target, "SmartDownload.exe")), "SmartDownload.exe must NOT be present in modern installation")
                self.assertFalse(os.path.isfile(os.path.join(install_target, "TurboDownloader.exe")), "TurboDownloader.exe must NOT be present in modern installation")
                self.assertTrue(os.path.isfile(os.path.join(install_target, "app_icon.ico")))
                self.assertTrue(len(progress_events) >= 5)
                self.assertEqual(progress_events[-1][0], 1.0)

                # Execute uninstall
                un_progress = []
                un_res = installer.uninstall_application(
                    target_dir=install_target,
                    progress_cb=lambda p, m: un_progress.append((p, m))
                )
                self.assertTrue(un_res.get("success"))
                self.assertTrue(len(un_progress) >= 4)
                self.assertEqual(un_progress[-1][0], 1.0)
                self.assertFalse(os.path.exists(install_target))

    def test_installer_purges_legacy_turbodownloader_binaries(self):
        """Verifies that install_application actively deletes existing TurboDownloader.exe and turbo_downloader.exe."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            install_target = os.path.join(tmp_dir, "TargetFolder")
            os.makedirs(install_target, exist_ok=True)
            legacy1 = os.path.join(install_target, "TurboDownloader.exe")
            legacy2 = os.path.join(install_target, "turbo_downloader.exe")
            with open(legacy1, "wb") as f:
                f.write(b"legacy1")
            with open(legacy2, "wb") as f:
                f.write(b"legacy2")

            self.assertTrue(os.path.isfile(legacy1))

            with patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                 patch("faqih_downloader.installer.installer_ops.register_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"):
                res = installer.install_application(
                    target_dir=install_target,
                    create_desktop=False,
                    create_start_menu=False,
                    register_browser=False,
                )
            self.assertTrue(res.get("success"))
            self.assertTrue(os.path.isfile(os.path.join(install_target, "FaqihDownloader.exe")))
            self.assertFalse(os.path.isfile(os.path.join(install_target, "SmartDownload.exe")), "SmartDownload.exe must be purged")
            self.assertFalse(os.path.isfile(legacy1))
            self.assertFalse(os.path.isfile(legacy2))

    def test_installer_startup_registration_and_uninstallation(self):
        """Verifies that install_application registers auto-start entries (Run registry, Scheduled Task, Startup shortcut) and uninstall_application removes them."""
        if not sys.platform.startswith("win"):
            self.skipTest("Installer startup tests only run on Windows OS.")

        import tempfile
        import winreg
        from unittest.mock import patch, MagicMock

        orig_reg = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
                orig_reg, _ = winreg.QueryValueEx(key, installer.STARTUP_REG_KEY_NAME)
        except Exception:
            pass

        try:
            with tempfile.TemporaryDirectory() as tmp_target, \
                 tempfile.TemporaryDirectory() as tmp_startup:

                recorded_commands = []
                orig_subprocess_run = subprocess.run

                def mock_subprocess_run(cmd, *args, **kwargs):
                    recorded_commands.append(cmd)
                    if isinstance(cmd, list) and len(cmd) > 0 and "schtasks.exe" in str(cmd[0]):
                        m = MagicMock()
                        m.returncode = 0
                        m.stdout = "SUCCESS"
                        m.stderr = ""
                        return m
                    return orig_subprocess_run(cmd, *args, **kwargs)

                with patch.object(installer, "get_startup_dir", return_value=tmp_startup), \
                     patch("subprocess.run", side_effect=mock_subprocess_run), \
                     patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                     patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"), \
                     patch("faqih_downloader.installer.installer_ops.unregister_uninstall_entry"):

                    res = installer.install_application(
                        target_dir=tmp_target,
                        create_desktop=False,
                        create_start_menu=False,
                        register_browser=False,
                        register_startup=True
                    )
                    self.assertTrue(res.get("success"))
                    self.assertIn("startup_registered", res)
                    self.assertTrue(res["startup_registered"].get("run_key"))
                    self.assertFalse(res["startup_registered"].get("scheduled_task"))
                    self.assertFalse(res["startup_registered"].get("startup_shortcut"))

                    # 1. Assert HKCU Run registry value exists and points to installed exe --minimized
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
                        run_val, _ = winreg.QueryValueEx(key, installer.STARTUP_REG_KEY_NAME)
                        expected_exes = [os.path.abspath(os.path.join(tmp_target, "FaqihDownloader.exe"))]
                        self.assertTrue(any(e.lower() in run_val.lower() for e in expected_exes))
                        self.assertTrue(run_val.endswith(" --minimized"))

                    # 2. Assert silent startup shortcut does not exist (preventing duplicate boot processes)
                    startup_lnk = os.path.join(tmp_startup, f"{installer.APP_NAME}.lnk")
                    self.assertFalse(os.path.isfile(startup_lnk), "Startup folder shortcut must not exist when Run key succeeds")

                    # 3. Assert schtasks.exe /Create was NOT called when Run key succeeds
                    schtasks_create_calls = [
                        c for c in recorded_commands
                        if isinstance(c, list) and len(c) > 0 and "schtasks.exe" in str(c[0]) and "/Create" in c
                    ]
                    self.assertEqual(len(schtasks_create_calls), 0, "schtasks.exe /Create must not be called when Run key succeeds")

                    # Now execute uninstallation
                    un_res = installer.uninstall_application(target_dir=tmp_target)
                    self.assertTrue(un_res.get("success"))

                    # 1. Assert HKCU Run registry value was deleted
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
                        with self.assertRaises(FileNotFoundError):
                            winreg.QueryValueEx(key, installer.STARTUP_REG_KEY_NAME)

                    # 2. Assert Startup folder shortcut was deleted
                    self.assertFalse(os.path.exists(startup_lnk), "Startup folder shortcut must be deleted after uninstall")

                    # 3. Assert schtasks.exe was invoked to delete the task
                    schtasks_delete_calls = [
                        c for c in recorded_commands
                        if isinstance(c, list) and len(c) > 0 and "schtasks.exe" in str(c[0]) and "/Delete" in c
                    ]
                    self.assertTrue(len(schtasks_delete_calls) >= 1, "schtasks.exe /Delete must be called during uninstall")
                    del_cmd = schtasks_delete_calls[0]
                    self.assertIn("/TN", del_cmd)
                    self.assertIn(installer.TASK_NAME, del_cmd)
        finally:
            if orig_reg is not None:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY) as key:
                    winreg.SetValueEx(key, installer.STARTUP_REG_KEY_NAME, 0, winreg.REG_SZ, orig_reg)
            else:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, installer.STARTUP_REG_KEY_NAME)
                except Exception:
                    pass

    def test_installer_startup_disabled_clean_state(self):
        """Verifies that install_application(register_startup=False) cleans up pre-existing startup entries and does not enable startup."""
        if not sys.platform.startswith("win"):
            self.skipTest("Installer startup tests only run on Windows OS.")

        import tempfile
        import winreg
        from unittest.mock import patch

        orig_reg = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
                orig_reg, _ = winreg.QueryValueEx(key, installer.STARTUP_REG_KEY_NAME)
        except Exception:
            pass

        try:
            with tempfile.TemporaryDirectory() as tmp_target, \
                 tempfile.TemporaryDirectory() as tmp_startup:

                # Pre-populate a fake startup shortcut
                fake_lnk = os.path.join(tmp_startup, f"{installer.APP_NAME}.lnk")
                with open(fake_lnk, "wb") as f:
                    f.write(b"FAKE_LNK")

                with patch.object(installer, "get_startup_dir", return_value=tmp_startup), \
                     patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                     patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"), \
                     patch("faqih_downloader.installer.installer_ops.unregister_uninstall_entry"):
                    res = installer.install_application(
                        target_dir=tmp_target,
                        create_desktop=False,
                        create_start_menu=False,
                        register_browser=False,
                        register_startup=False
                    )
                    self.assertTrue(res.get("success"))
                    self.assertFalse(os.path.exists(fake_lnk), "Pre-existing startup shortcut must be cleaned up when register_startup=False")
        finally:
            if orig_reg is not None:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY) as key:
                    winreg.SetValueEx(key, installer.STARTUP_REG_KEY_NAME, 0, winreg.REG_SZ, orig_reg)
            else:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, installer.STARTUP_REG_KEY_NAME)
                except Exception:
                    pass

    def test_build_installer_payload_deduplication(self):
        """Verifies build_installer.prepare_payload() bundles ONLY FaqihDownloader.exe and excludes SmartDownload/TurboDownloader."""
        import build_installer
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dist, tempfile.TemporaryDirectory() as tmp_payload:
            mock_exe = os.path.join(tmp_dist, "FaqihDownloader.exe")
            with open(mock_exe, "wb") as f:
                f.write(b"MOCK_BINARY_DATA")

            with patch.object(build_installer, "DIST_DIR", tmp_dist), \
                 patch.object(build_installer, "PAYLOAD_DIR", tmp_payload):
                build_installer.prepare_payload()

                bundled_files = os.listdir(tmp_payload)
                self.assertTrue("FaqihDownloader.exe" in bundled_files or "payload.lzma.zip" in bundled_files, "FaqihDownloader.exe or payload.lzma.zip must be bundled")
                self.assertNotIn("SmartDownload.exe", bundled_files, "SmartDownload.exe must NOT be duplicated in payload")
                self.assertNotIn("TurboDownloader.exe", bundled_files, "TurboDownloader.exe must NOT be duplicated in payload")

    def test_build_installer_payload_copies_real_registry(self):
        """Verifies prepare_payload copies real registry.py and host_manifest.py, runnable standalone."""
        import build_installer
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dist, tempfile.TemporaryDirectory() as tmp_payload:
            mock_exe = os.path.join(tmp_dist, "FaqihDownloader.exe")
            with open(mock_exe, "wb") as f:
                f.write(b"MOCK_BINARY_DATA")

            with patch.object(build_installer, "DIST_DIR", tmp_dist), \
                 patch.object(build_installer, "PAYLOAD_DIR", tmp_payload):
                build_installer.prepare_payload()

                reg_copy = os.path.join(tmp_payload, "register_browser.py")
                hm_copy = os.path.join(tmp_payload, "host_manifest.py")
                self.assertTrue(os.path.isfile(reg_copy), "register_browser.py must be present in payload")
                self.assertTrue(os.path.isfile(hm_copy), "host_manifest.py must be present in payload")
                with open(reg_copy, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertNotIn("from faqih_downloader.services.browser.registry import *", content, "Payload register_browser.py must not be the root shim")
                self.assertIn("compute_unpacked_extension_id", content, "Payload must contain full registry logic")

                # Verify register_browser.py in payload executes standalone without relative import errors
                res = subprocess.run([sys.executable, reg_copy, "--status"], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, f"Payload register_browser.py execution failed: {res.stderr}")

    def test_install_application_clean_folder_and_purges_stale_files(self):
        """Verifies install_application does not copy bloat and actively removes stale scripts and uninstaller binaries."""
        with tempfile.TemporaryDirectory() as tmp_target:
            # Pre-populate stale files from previous install
            stale_names = ["register_browser.py", "host_manifest.py", "app_icon.png", "uninstall.bat", "Uninstall.exe", "turbo_host.bat"]
            for name in stale_names:
                with open(os.path.join(tmp_target, name), "w") as f:
                    f.write("stale")

            with patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                 patch("faqih_downloader.installer.installer_ops.register_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.register_uninstall_entry", return_value=True) as mock_reg_uninst:
                res = installer.install_application(
                    target_dir=tmp_target,
                    create_desktop=False,
                    create_start_menu=False,
                    register_browser=False,
                )

            self.assertTrue(res.get("success"))
            exe_dest = os.path.join(tmp_target, "FaqihDownloader.exe")
            self.assertEqual(res.get("uninstaller_path"), exe_dest)
            self.assertTrue(os.path.isfile(exe_dest))
            self.assertFalse(os.path.isfile(os.path.join(tmp_target, "SmartDownload.exe")))
            self.assertTrue(os.path.isfile(os.path.join(tmp_target, "app_icon.ico")))

            # Ensure all stale files were removed
            for name in stale_names:
                self.assertFalse(os.path.exists(os.path.join(tmp_target, name)), f"Stale file {name} must be removed from target directory")

            # Ensure register_uninstall_entry was called with uninstaller_path == exe_dest
            mock_reg_uninst.assert_called_once()
            args = mock_reg_uninst.call_args[0]
            self.assertEqual(args[2], exe_dest)

    def test_handle_uninstall_cli_silent(self):
        """Verifies handle_uninstall_cli with --silent calls uninstall_application and exits cleanly."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            with patch("faqih_downloader.installer.uninstaller_runner.uninstall_application", return_value={"success": True}) as mock_uninst, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall", "--silent", "--dir", tmp_target])
                mock_uninst.assert_called_once_with(target_dir=os.path.abspath(tmp_target))
                mock_exit.assert_called_once_with(0)

    def test_handle_uninstall_cli_frozen_clones_to_temp(self):
        """Verifies handle_uninstall_cli when frozen inside target clones executable to temp and spawns with --uninstall-gui."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            fake_exe = os.path.join(tmp_target, "FaqihDownloader.exe")
            with open(fake_exe, "wb") as f:
                f.write(b"MOCK_EXE")

            with patch("sys.frozen", True, create=True), \
                 patch("sys.executable", fake_exe), \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall", "--dir", tmp_target])
                mock_popen.assert_called_once()
                spawn_args = mock_popen.call_args[0][0]
                self.assertIn("--uninstall-gui", spawn_args)
                self.assertIn("--dir", spawn_args)
                self.assertIn(os.path.abspath(tmp_target), spawn_args)
                self.assertTrue(spawn_args[0].lower().endswith(("faqihdownloader-uninstaller.exe", "smartdownload-uninstaller.exe")))
                mock_exit.assert_called_once_with(0)

    def test_terminate_running_app_excludes_current_pid(self):
        """Verifies terminate_running_app includes 'PID ne <current_pid>' in taskkill arguments."""
        from faqih_downloader.installer.installer_ops import terminate_running_app

        with patch("sys.platform", "win32"), \
             patch("subprocess.run") as mock_run, \
             patch("os.getpid", return_value=99999):
            terminate_running_app()
            self.assertIn(mock_run.call_count, (2, 3))
            for call in mock_run.call_args_list:
                args = call[0][0]
                self.assertIn("taskkill", args)
                self.assertIn("/FI", args)
                self.assertIn("PID ne 99999", args)

    def test_handle_uninstall_cli_frozen_case_insensitive_path(self):
        """Verifies handle_uninstall_cli handles Windows drive letter case mismatch between executable and target_dir."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            target_norm = os.path.abspath(tmp_target)
            # Create a path with alternate casing for the drive letter
            drive, rest = os.path.splitdrive(target_norm)
            alt_drive = drive.lower() if drive.isupper() else drive.upper()
            alt_target = alt_drive + rest
            fake_exe = os.path.join(alt_target, "FaqihDownloader.exe")

            with open(os.path.join(target_norm, "FaqihDownloader.exe"), "wb") as f:
                f.write(b"MOCK_EXE")

            with patch("sys.frozen", True, create=True), \
                 patch("sys.executable", fake_exe), \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall", "--dir", target_norm])
                mock_popen.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_handle_uninstall_cli_temp_lock_fallback(self):
        """Verifies handle_uninstall_cli falls back to PID-specific temp file when default temp uninstaller is locked."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            fake_exe = os.path.join(tmp_target, "FaqihDownloader.exe")
            with open(fake_exe, "wb") as f:
                f.write(b"MOCK_EXE")

            orig_copy2 = shutil.copy2
            def mock_copy2(src, dst):
                if dst.lower().endswith(("faqihdownloader-uninstaller.exe", "smartdownload-uninstaller.exe")):
                    raise PermissionError("File locked by active uninstaller")
                return orig_copy2(src, dst)

            with patch("sys.frozen", True, create=True), \
                 patch("sys.executable", fake_exe), \
                 patch("shutil.copy2", side_effect=mock_copy2), \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall", "--dir", tmp_target])
                mock_popen.assert_called_once()
                spawn_args = mock_popen.call_args[0][0]
                self.assertTrue("uninstaller-" in spawn_args[0].lower())
                mock_exit.assert_called_once_with(0)

    def test_handle_uninstall_cli_frozen_silent_clones_to_temp(self):
        """Verifies handle_uninstall_cli when frozen and --silent clones executable to temp and spawns with --uninstall-worker."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            fake_exe = os.path.join(tmp_target, "FaqihDownloader.exe")
            with open(fake_exe, "wb") as f:
                f.write(b"MOCK_EXE")

            with patch("sys.frozen", True, create=True), \
                 patch("sys.executable", fake_exe), \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall", "--silent", "--dir", tmp_target])
                mock_popen.assert_called_once()
                spawn_args = mock_popen.call_args[0][0]
                self.assertIn("--uninstall-worker", spawn_args)
                self.assertIn("--silent", spawn_args)
                self.assertIn("--dir", spawn_args)
                self.assertIn(os.path.abspath(tmp_target), spawn_args)
                self.assertTrue(spawn_args[0].lower().endswith(("faqihdownloader-uninstaller.exe", "smartdownload-uninstaller.exe")))
                mock_exit.assert_called_once_with(0)

    def test_handle_uninstall_cli_worker_mode(self):
        """Verifies handle_uninstall_cli in worker mode runs uninstall_application, schedules cleanup and exits."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        with tempfile.TemporaryDirectory() as tmp_target:
            with patch("faqih_downloader.installer.uninstaller_runner.uninstall_application", return_value={"success": True}) as mock_uninst, \
                 patch("faqih_downloader.installer.uninstaller_runner._schedule_temp_uninstaller_cleanup") as mock_cleanup, \
                 patch("sys.exit", side_effect=SystemExit(0)) as mock_exit:
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(["--uninstall-worker", "--silent", "--dir", tmp_target])
                mock_uninst.assert_called_once_with(target_dir=os.path.abspath(tmp_target))
                mock_cleanup.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_handle_uninstall_cli_dir_argument_syntax(self):
        """Verifies handle_uninstall_cli correctly parses --dir=<path> and POSIX paths starting with '/'."""
        from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli

        test_cases = [
            (["--uninstall", "--silent", "--dir=/tmp/my_app"], os.path.abspath("/tmp/my_app")),
            (["--uninstall", "--silent", "-dir=/tmp/my_app"], os.path.abspath("/tmp/my_app")),
            (["--uninstall", "--silent", "/dir=/tmp/my_app"], os.path.abspath("/tmp/my_app")),
            (["--uninstall", "--silent", "--dir", "/tmp/my_app"], os.path.abspath("/tmp/my_app")),
        ]
        for cmd_args, expected_dir in test_cases:
            with patch("faqih_downloader.installer.uninstaller_runner.uninstall_application", return_value={"success": True}) as mock_uninst, \
                 patch("sys.exit", side_effect=SystemExit(0)):
                with self.assertRaises(SystemExit):
                    handle_uninstall_cli(cmd_args)
                mock_uninst.assert_called_once_with(target_dir=expected_dir)

        # Flag followed by another flag (--silent) should not accept the flag as dir
        with patch("faqih_downloader.installer.uninstaller_runner.uninstall_application", return_value={"success": True}) as mock_uninst, \
             patch("sys.exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                handle_uninstall_cli(["--uninstall", "--dir", "--silent"])
            from faqih_downloader.installer.installer_ops import DEFAULT_INSTALL_DIR
            mock_uninst.assert_called_once_with(target_dir=os.path.abspath(DEFAULT_INSTALL_DIR))

    def test_early_single_instance_guard_bypasses_all_uninstall_variants(self):
        """Verifies early_single_instance_guard bypasses mutex checks for all case/syntax variants of uninstall flags."""
        from faqih_downloader.services.single_instance import early_single_instance_guard

        variants = ["--uninstall", "--UNINSTALL", "/u", "/U", "-u", "-U", "/uninstall", "/UNINSTALL", "-uninstall", "--uninstall-worker"]
        for flag in variants:
            with patch("sys.argv", ["SmartDownload.exe", flag]), \
                 patch("faqih_downloader.services.single_instance.acquire_single_instance_mutex") as mock_acq, \
                 patch("faqih_downloader.services.single_instance.notify_running_instance") as mock_notify:
                early_single_instance_guard()
                mock_acq.assert_not_called()
                mock_notify.assert_not_called()

    def test_schedule_temp_uninstaller_cleanup_encodes_powershell_base64(self):
        """Verifies _schedule_temp_uninstaller_cleanup spawns PowerShell with base64 EncodedCommand targeting PID and self exe."""
        import base64
        from faqih_downloader.installer.uninstaller_runner import _schedule_temp_uninstaller_cleanup

        fake_temp_exe = os.path.join(tempfile.gettempdir(), "SmartDownload-Uninstaller.exe")
        with patch("sys.frozen", True, create=True), \
             patch("sys.platform", "win32"), \
             patch("sys.executable", fake_temp_exe), \
             patch("subprocess.Popen") as mock_popen:
            _schedule_temp_uninstaller_cleanup()
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            self.assertEqual(call_args[0], "powershell")
            self.assertIn("-EncodedCommand", call_args)
            b64_idx = call_args.index("-EncodedCommand") + 1
            encoded_str = call_args[b64_idx]
            decoded_ps = base64.b64decode(encoded_str).decode("utf-16le")
            self.assertIn(f"Get-Process -Id {os.getpid()}", decoded_ps)
            self.assertIn("Remove-Item", decoded_ps)
            self.assertIn("SmartDownload-Uninstaller.exe", decoded_ps)

    def test_release_publisher_excludes_standalone_and_deletes_stale_asset(self):
        """Verifies release_publisher deletes stale SmartDownload.exe asset and uploads only setup + patch in --full-build."""
        import release_publisher

        initial_assets = [
            {"id": 101, "name": "SmartDownload.exe", "size": 100, "state": "uploaded", "browser_download_url": "https://fake/sd"},
            {"id": 102, "name": "FaqihDownloader-Setup.exe", "size": 200, "state": "uploaded", "browser_download_url": "https://fake/setup"},
        ]
        final_assets = [
            {"id": 102, "name": "FaqihDownloader-Setup.exe", "size": 200, "state": "uploaded", "browser_download_url": "https://fake/setup"},
            {"id": 103, "name": "FaqihDownloader-CorePatch.zip", "size": 200, "state": "uploaded", "browser_download_url": "https://fake/patch"},
        ]
        api_calls = []

        def mock_api_request(url, token, data=None, method="GET", headers=None):
            api_calls.append((method, url, data))
            if "releases/tags/" in url:
                return 200, {"id": 1234, "upload_url": "https://uploads.github.com/assets{?name,label}"}
            if "/releases/1234" in url and method == "GET":
                assets_to_return = final_assets if any(c[0] == "DELETE" for c in api_calls) else initial_assets
                return 200, {"id": 1234, "upload_url": "https://uploads.github.com/assets{?name,label}", "assets": list(assets_to_return)}
            if "/assets/101" in url and method == "DELETE":
                return 204, {}
            return 200, {"id": 999, "name": "uploaded", "state": "uploaded", "size": 200, "browser_download_url": "https://fake"}

        with patch("sys.argv", ["release_publisher.py", "--full-build"]), \
             patch("release_publisher.get_git_credentials", return_value=("mock_user", "mock_tok")), \
             patch("release_publisher.api_request", side_effect=mock_api_request), \
             patch("release_publisher.build_core_patch_zip"), \
             patch("release_publisher.upload_asset_with_curl", return_value={"id": 999, "browser_download_url": "https://fake", "size": 200}), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=200):
            release_publisher.main()

            del_calls = [c for c in api_calls if c[0] == "DELETE" and "assets/101" in c[1]]
            self.assertEqual(len(del_calls), 1, "Must delete stale SmartDownload.exe asset from release")

    def test_release_publisher_include_standalone_flag(self):
        """Verifies release_publisher retains and uploads FaqihDownloader.exe when --include-standalone is passed."""
        import release_publisher

        initial_assets = [
            {"id": 101, "name": "FaqihDownloader.exe", "size": 100, "state": "uploaded", "browser_download_url": "https://fake/sd"},
        ]
        final_assets = [
            {"id": 101, "name": "FaqihDownloader.exe", "size": 100, "state": "uploaded", "browser_download_url": "https://fake/sd"},
            {"id": 102, "name": "FaqihDownloader-Setup.exe", "size": 100, "state": "uploaded", "browser_download_url": "https://fake/setup"},
            {"id": 103, "name": "FaqihDownloader-CorePatch.zip", "size": 100, "state": "uploaded", "browser_download_url": "https://fake/patch"},
        ]
        api_calls = []
        uploaded = []

        def mock_api_request(url, token, data=None, method="GET", headers=None):
            api_calls.append((method, url, data))
            if "releases/tags/" in url:
                return 200, {"id": 1234, "upload_url": "https://uploads.github.com/assets{?name,label}"}
            if "/releases/1234" in url and method == "GET":
                assets_to_return = final_assets if uploaded else initial_assets
                return 200, {"id": 1234, "upload_url": "https://uploads.github.com/assets{?name,label}", "assets": list(assets_to_return)}
            return 200, {}

        def mock_upload(url, token, file_path):
            uploaded.append(os.path.basename(file_path))
            return {"id": 999, "browser_download_url": "https://fake", "size": 100}

        with patch("sys.argv", ["release_publisher.py", "--full-build", "--include-standalone"]), \
             patch("release_publisher.get_git_credentials", return_value=("mock_user", "mock_tok")), \
             patch("release_publisher.api_request", side_effect=mock_api_request), \
             patch("release_publisher.build_core_patch_zip"), \
             patch("release_publisher.upload_asset_with_curl", side_effect=mock_upload), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=100):
            release_publisher.main()

            del_calls = [c for c in api_calls if c[0] == "DELETE" and "assets/101" in c[1]]
            self.assertEqual(len(del_calls), 0, "Must NOT delete FaqihDownloader.exe when --include-standalone is passed")

    def test_release_publisher_missing_standalone_raises_filenotfound(self):
        """Verifies release_publisher raises FileNotFoundError when --include-standalone is passed but binary does not exist."""
        import release_publisher

        def mock_isfile(p):
            if "FaqihDownloader.exe" in p:
                return False
            return True

        with patch("sys.argv", ["release_publisher.py", "--full-build", "--include-standalone"]), \
             patch("release_publisher.get_git_credentials", return_value=("mock_user", "mock_tok")), \
             patch("release_publisher.api_request", return_value=(200, {"id": 1234, "upload_url": "https://uploads.github.com/{?name}"})), \
             patch("release_publisher.build_core_patch_zip"), \
             patch("os.path.isfile", side_effect=mock_isfile), \
             patch("os.path.getsize", return_value=100):
            with self.assertRaises(FileNotFoundError):
                release_publisher.main()

    def test_installer_gui_initialization_grab_free(self):
        """Verifies Tkinter InstallerGUI creates without grab lock and has responsive layout."""
        import tkinter as tk
        root = None
        for attempt in range(4):
            try:
                root = tk.Tk()
                break
            except Exception:
                if attempt == 3:
                    raise
                import time
                time.sleep(0.1)
        root.withdraw()
        try:
            gui = installer.InstallerGUI(root, mode="install")
            self.assertEqual(gui.mode, "install")
            # Verify grab-free: root must NOT have active grab lock
            self.assertIsNone(root.grab_current(), "Installer GUI must be grab-free without modal lock")
            # Verify UI elements exist
            self.assertTrue(hasattr(gui, "entry_dir"))
            self.assertTrue(hasattr(gui, "btn_action"))
            self.assertTrue(hasattr(gui, "btn_cancel"))
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_installer_gui_finish_button_enabled_after_completion(self):
        """Verifies Finish button is in 'normal' state and clickable after completion."""
        import tkinter as tk
        root = None
        for attempt in range(4):
            try:
                root = tk.Tk()
                break
            except Exception:
                if attempt == 3:
                    raise
                import time
                time.sleep(0.1)
        root.withdraw()
        try:
            gui = installer.InstallerGUI(root, mode="install")
            gui.btn_action.config(state="disabled")
            self.assertEqual(gui.btn_action.cget("state"), "disabled")
            gui._render_completed_screen(success=True, message="Installed successfully", exe_path="")
            self.assertEqual(gui.btn_action.cget("state"), "normal")
            self.assertEqual(gui.btn_action.cget("text"), "Finish")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_shell_desktop_and_programs_directory_resolution(self):
        """Verifies get_desktop_dir and get_start_menu_programs_dir return valid existing folders."""
        desktop_dir = installer.get_desktop_dir()
        programs_dir = installer.get_start_menu_programs_dir()
        self.assertTrue(os.path.isdir(desktop_dir), f"Desktop folder {desktop_dir} must exist")
        self.assertTrue(os.path.isdir(programs_dir), f"Programs folder {programs_dir} must exist")

    def test_uninstaller_binary_mode_detection(self):
        """Verifies that running with an uninstaller binary name defaults to uninstall mode."""
        with patch("sys.executable", "C:\\Programs\\SmartDownload\\Uninstall.exe"):
            exe_name = os.path.basename(sys.executable).lower()
            is_uninst = "uninstall" in exe_name
            self.assertTrue(is_uninst)
            mode = "uninstall" if is_uninst else "install"
            self.assertEqual(mode, "uninstall")

    def test_installer_shim_bidirectional_monkeypatching(self):
        """Verifies _InstallerShim synchronizes monkeypatches bidirectionally between installer and ops/reg/gui."""
        import faqih_downloader.installer.installer_ops as ops

        # Patching sub-module propagates to root installer shim
        with patch.object(ops, "find_payload_sources", return_value={"mock_test": True}):
            self.assertEqual(installer.find_payload_sources(), {"mock_test": True})

        # Patching root installer shim propagates to sub-module
        with patch.object(installer, "find_payload_sources", return_value={"mock_test_2": True}):
            self.assertEqual(ops.find_payload_sources(), {"mock_test_2": True})

    def test_register_startup_entries_canonical_run_key(self):
        """Verifies register_startup_entries uses HKCU Run as canonical, cleans duplicates, and skips redundant tasks."""
        if not sys.platform.startswith("win"):
            self.skipTest("Windows-only test")
        from faqih_downloader.installer.installer_registry import register_startup_entries
        from unittest.mock import MagicMock, patch

        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.CreateKey.return_value.__enter__.return_value = mock_key
        mock_winreg.REG_SZ = 1
        mock_winreg.REG_BINARY = 3

        with patch("faqih_downloader.installer.installer_registry.HAS_WINREG", True), \
             patch("faqih_downloader.installer.installer_registry.winreg", mock_winreg), \
             patch("faqih_downloader.installer.installer_registry.get_startup_dir", return_value="C:\\FakeStartup"), \
             patch("subprocess.run") as mock_subproc:
            res = register_startup_entries("C:\\FakePath\\SmartDownload.exe")
            self.assertTrue(res["run_key"])
            self.assertFalse(res["scheduled_task"])
            self.assertFalse(res["startup_shortcut"])
            # Verify schtasks /Delete was called to clean up duplicate tasks
            del_calls = [c for c in mock_subproc.call_args_list if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "/Delete"]
            self.assertGreaterEqual(len(del_calls), 1)

    def test_register_startup_entries_fallback_when_run_key_fails(self):
        """Verifies register_startup_entries falls back to Scheduled Task and Shortcut when HKCU Run fails."""
        if not sys.platform.startswith("win"):
            self.skipTest("Windows-only test")
        from faqih_downloader.installer.installer_registry import register_startup_entries
        from unittest.mock import MagicMock, patch

        mock_winreg = MagicMock()
        mock_winreg.CreateKey.side_effect = PermissionError("Access denied")

        mock_proc_ok = MagicMock()
        mock_proc_ok.returncode = 0

        # Scenario 1: Run key fails, Scheduled Task succeeds
        with patch("faqih_downloader.installer.installer_registry.HAS_WINREG", True), \
             patch("faqih_downloader.installer.installer_registry.winreg", mock_winreg), \
             patch("subprocess.run", return_value=mock_proc_ok) as mock_subproc:
            res = register_startup_entries("C:\\FakePath\\SmartDownload.exe")
            self.assertFalse(res["run_key"])
            self.assertTrue(res["scheduled_task"])
            self.assertFalse(res["startup_shortcut"])

        # Scenario 2: Run key fails AND Scheduled Task fails -> falls back to shortcut
        mock_proc_fail = MagicMock()
        mock_proc_fail.returncode = 1
        with patch("faqih_downloader.installer.installer_registry.HAS_WINREG", True), \
             patch("faqih_downloader.installer.installer_registry.winreg", mock_winreg), \
             patch("subprocess.run", return_value=mock_proc_fail), \
             patch("faqih_downloader.installer.installer_registry.get_startup_dir", return_value="C:\\FakeStartup"), \
             patch("faqih_downloader.installer.installer_registry.create_windows_shortcut", return_value=True) as mock_shortcut:
            res = register_startup_entries("C:\\FakePath\\SmartDownload.exe")
            self.assertFalse(res["run_key"])
            self.assertFalse(res["scheduled_task"])
            self.assertTrue(res["startup_shortcut"])
            mock_shortcut.assert_called_once()


class TestStandaloneExeBuild(unittest.TestCase):
    """Verifies that the PyInstaller standalone Windows executable exists and has valid PE structure."""

    def test_exe_binary_properties(self):
        dist_dir = os.path.join(PROJECT_ROOT, "dist")
        exe_path = os.path.join(dist_dir, "FaqihDownloader.exe")
        self.assertTrue(os.path.exists(exe_path), f"FaqihDownloader.exe not found at {exe_path}")
        file_size = os.path.getsize(exe_path)
        self.assertGreater(file_size, 5 * 1024 * 1024, f"Binary size {file_size} is suspiciously small")

    def test_exe_binary_header_pe_signature(self):
        dist_dir = os.path.join(PROJECT_ROOT, "dist")
        exe_path = os.path.join(dist_dir, "FaqihDownloader.exe")
        with open(exe_path, "rb") as f:
            header = f.read(2)
        self.assertEqual(header, b"MZ", "Executable missing valid Windows PE MZ header")

    def test_exe_binary_startup_verification(self):
        dist_dir = os.path.join(PROJECT_ROOT, "dist")
        exe_path = os.path.join(dist_dir, "FaqihDownloader.exe")
        if not os.path.exists(exe_path):
            self.skipTest(f"{exe_path} not found")
        # Run with --test-startup (DEVNULL for windowed GUI executables)
        proc = subprocess.run([exe_path, "--test-startup"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        self.assertEqual(proc.returncode, 0, f"Standalone exe failed to start cleanly with returncode {proc.returncode}")

    def test_exe_binary_minimized_background_launch(self):
        dist_dir = os.path.join(PROJECT_ROOT, "dist")
        exe_path = os.path.join(dist_dir, "FaqihDownloader.exe")
        if not os.path.exists(exe_path):
            self.skipTest(f"{exe_path} not found")
        proc = subprocess.Popen([exe_path, "--minimized", "--force-new-instance"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            connected = False
            for _ in range(40):
                time.sleep(0.4)
                try:
                    req = urllib.request.Request("http://127.0.0.1:9242/ping")
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        if resp.status == 200:
                            connected = True
                            break
                except Exception:
                    pass
            self.assertTrue(connected, "Standalone binary with --minimized failed to activate loopback server")
        finally:
            try:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            time.sleep(0.5)

    def test_clean_stale_shadow_modules(self):
        """Verifies that clean_stale_shadow_modules purges shadow files from __pycache__ and root."""
        from build_installer import clean_stale_shadow_modules
        pycache_dir = os.path.join(PROJECT_ROOT, "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        dummy_pyc = os.path.join(pycache_dir, "faqih_downloader.cpython-999.pyc")
        with open(dummy_pyc, "w") as f:
            f.write("dummy")
        self.assertTrue(os.path.isfile(dummy_pyc))
        clean_stale_shadow_modules()
        self.assertFalse(os.path.isfile(dummy_pyc), "Dummy shadow pyc was not removed by clean_stale_shadow_modules")

    def test_install_application_purges_stale_core_plugin(self):
        """Verifies that install_application purges %APPDATA%\\SmartDownload\\core_plugin."""
        from faqih_downloader.installer import install_application
        from faqih_downloader.services.core_patch_updater import get_core_plugin_dir

        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_plugin = os.path.join(tmp_dir, "core_plugin")
            os.makedirs(dummy_plugin, exist_ok=True)
            dummy_file = os.path.join(dummy_plugin, "stale.txt")
            with open(dummy_file, "w") as f:
                f.write("stale")

            target_install = os.path.join(tmp_dir, "install_target")
            with patch("faqih_downloader.services.core_patch_updater.get_core_plugin_dir", return_value=dummy_plugin), \
                 patch("faqih_downloader.installer.installer_ops.terminate_running_app"), \
                 patch("faqih_downloader.installer.installer_ops.register_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.unregister_startup_entries"), \
                 patch("faqih_downloader.installer.installer_ops.register_uninstall_entry"):
                install_application(
                    target_dir=target_install,
                    register_browser=False,
                    create_desktop=False,
                    create_start_menu=False,
                    register_startup=False,
                )
            self.assertFalse(os.path.exists(dummy_plugin), "stale core_plugin directory was not purged during installation")

    def test_purge_stale_core_plugin_in_builder(self):
        """Verifies that purge_stale_core_plugin in build_installer removes the core_plugin directory."""
        from build_installer import purge_stale_core_plugin
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_plugin = os.path.join(tmp_dir, "core_plugin")
            os.makedirs(dummy_plugin, exist_ok=True)
            with patch("faqih_downloader.services.core_patch_updater.get_core_plugin_dir", return_value=dummy_plugin):
                purge_stale_core_plugin()
            self.assertFalse(os.path.exists(dummy_plugin), "purge_stale_core_plugin failed to remove directory")


if __name__ == "__main__":
    unittest.main()

