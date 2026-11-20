"""
ModernFramelessGUI: Complete Dark-themed, frameless, dynamic chunking download manager GUI.
"""
from __future__ import annotations

import sys
import os
import queue
import weakref
import threading
from typing import List, Optional, Any, Dict, Union, Tuple

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from ...config import (
    get_setting as _cfg_get_setting,
    is_test_environment as _cfg_is_test_env,
    DEFAULT_SNIFFER_PLATFORMS,
)
from ...locales.i18n import LocalizationManager
from ...core.engine import TurboDownloadEngine
from ...core.stream_coordinator import StreamDownloadCoordinator
from ...core.history import DownloadHistoryManager
from ...services.startup_service import (
    is_startup_enabled as _svc_is_startup_enabled,
    enable_startup as _svc_enable_startup,
)
from ...services.browser.bridge_server import (
    BrowserBridgeServer as _svc_BrowserBridgeServer,
    DEFAULT_BRIDGE_PORT,
)
from ..system_tray import SystemTrayManager as _ui_SystemTrayManager

from ..components.top_bar import TopHeaderBarMixin
from ..panels.kanban_panel import KanbanPanelMixin
from ..panels.hidden_compat_panel import HiddenCompatPanelMixin
from ..modals.browser_settings_modal import BrowserSettingsModalMixin
from ..panels.history_panel import HistoryPanelMixin
from ..panels.chunks_panel import ChunksPanelMixin
from ..panels.inputs_panel import InputsPanelMixin
from ..panels.media_options_bar import MediaOptionsBarMixin
from ..controllers.clipboard_controller import ClipboardControllerMixin
from ..controllers.update_controller import UpdateControllerMixin
from ..controllers.download_controller import DownloadControllerMixin
from ..controllers.settings_controller import SettingsControllerMixin
from ..controllers.window_controller import WindowChromeMixin


def _get_mw_attr(name: str, fallback: Any) -> Any:
    mod = sys.modules.get("faqih_downloader.ui.main_window")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback


class ModernFramelessGUI(
    TopHeaderBarMixin,
    KanbanPanelMixin,
    HiddenCompatPanelMixin,
    BrowserSettingsModalMixin,
    HistoryPanelMixin,
    ChunksPanelMixin,
    InputsPanelMixin,
    MediaOptionsBarMixin,
    ClipboardControllerMixin,
    UpdateControllerMixin,
    DownloadControllerMixin,
    SettingsControllerMixin,
    WindowChromeMixin,
):
    """
    Sleek Frameless Window GUI with:
    - Custom draggable dark title bar with minimize and close controls.
    - Windows OS taskbar integration via ctypes.
    - Per-download manual rate limiter controls (presets, custom KB/s, dynamic slider).
    - TDM-style visual segmented chunk progress bar.
    - Real-time performance metrics (speed, progress, ETA, active threads).
    - Detailed chunk status table and event logging console.
    """
    def __init__(self, root: Any, start_hidden: Optional[bool] = None, initial_url: Optional[str] = None):
        self.root = root
        if start_hidden is None:
            start_hidden = any(arg.lower() in ("--background", "-background", "/background",
                                                "--minimized", "-minimized", "/minimized")
                               for arg in sys.argv[1:])
        self._start_hidden: bool = bool(start_hidden)
        self._was_started_hidden: bool = bool(start_hidden)
        is_startup_fn = _get_mw_attr("is_startup_enabled", _svc_is_startup_enabled)
        self._startup_enabled: bool = bool(is_startup_fn())
        get_setting_fn = _get_mw_attr("get_setting", _cfg_get_setting)
        if get_setting_fn("startup_enabled", None) is True and not self._startup_enabled:
            def _async_enable_startup():
                try:
                    enable_startup_fn = _get_mw_attr("enable_startup", _svc_enable_startup)
                    enable_startup_fn(minimized=True)
                    self._startup_enabled = True
                except Exception:
                    pass
            threading.Thread(target=_async_enable_startup, daemon=True).start()
        self.minimize_to_tray: bool = bool(get_setting_fn("minimize_to_tray", True))
        self.auto_categorize_folders: bool = bool(get_setting_fn("auto_categorize_folders", True))
        self.history_manager = DownloadHistoryManager()
        self.cookies_browser: str = str(get_setting_fn("cookies_browser", "auto") or "auto")
        self.cookies_file: str = str(get_setting_fn("cookies_file", "") or "")
        self.engine: Optional[Union[TurboDownloadEngine, StreamDownloadCoordinator]] = None
        self.speed_limit: float = 0.0
        self._yt_cancel_event = threading.Event()
        self._fetch_cancel_event = threading.Event()
        self._quality_modal: Optional[tk.Toplevel] = None
        self._confirm_modal: Optional[tk.Toplevel] = None
        self._candidates_modal: Optional[tk.Toplevel] = None
        self._update_modal: Optional[tk.Toplevel] = None
        self._fetching_toast: Optional[Any] = None
        self._bg_toast: Optional[tk.Toplevel] = None
        self._refresh_job = None
        self._update_check_job = None
        self._closing = False
        self._log_jobs: List[Any] = []
        self._gui_dispatch_queue: queue.Queue = queue.Queue()

        # Clipboard URL Sniffer (Automatic clipboard monitor)
        self._clipboard_sniffer_active: bool = bool(get_setting_fn("clipboard_sniffer_active", True))
        self.sniffer_platforms: Dict[str, bool] = dict(get_setting_fn("sniffer_platforms", DEFAULT_SNIFFER_PLATFORMS) or DEFAULT_SNIFFER_PLATFORMS)
        self._auto_start_clipboard: bool = True
        self._last_clipboard_url: Optional[str] = None
        self._last_clipboard_seq: Optional[int] = None
        self._clipboard_job = None
        self._clipboard_poll_interval = 500  # ms

        # DPI Scaling & Metrics Calculation
        try:
            dpi = float(self.root.winfo_fpixels('1i'))
        except Exception:
            dpi = 96.0
        self.dpi = dpi if dpi > 0 else 96.0
        self.dpi_scale = max(1.0, self.dpi / 96.0)

        # Configure Tk font scaling ratio to match physical monitor DPI
        try:
            self.root.tk.call('tk', 'scaling', self.dpi / 72.0)
        except Exception:
            pass

        # Window Configuration (DPI Aware)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = int(980 * self.dpi_scale)
        target_h = int(760 * self.dpi_scale)
        self.width = min(target_w, max(850, int(sw * 0.92)))
        self.height = min(target_h, max(650, int(sh * 0.88)))
        self._setup_window()
        self._init_theme()

        # Fast-Path: Initialize System Tray Manager and schedule background notification early
        tray_mgr_cls = _get_mw_attr("SystemTrayManager", _ui_SystemTrayManager)
        self.tray_manager = tray_mgr_cls(self)
        try:
            self.tray_manager.start()
        except Exception:
            pass

        self._bg_notify_job = None
        if self._start_hidden and os.environ.get("SD_DISABLE_STARTUP_TOAST") != "1":
            try:
                self._bg_notify_job = self.root.after(80, self._show_background_startup_notification)
            except Exception:
                pass

        self._build_ui()

        if initial_url:
            try:
                self.entry_url.delete(0, tk.END)
                self.entry_url.insert(0, initial_url)
            except Exception:
                pass

        # Initialize Browser Bridge loopback IPC server using weakref callbacks
        _weak_self = weakref.ref(self)

        def _bridge_dl(task):
            g = _weak_self()
            if g is not None and not getattr(g, "_closing", False):
                g._on_browser_download_received(task)

        def _bridge_log(msg):
            g = _weak_self()
            if g is not None and not getattr(g, "_closing", False):
                g.log(msg)

        def _bridge_show():
            g = _weak_self()
            if g is not None and not getattr(g, "_closing", False):
                g.dispatch_to_main_thread(g.restore_window)

        bridge_server_cls = _get_mw_attr("BrowserBridgeServer", _svc_BrowserBridgeServer)
        self.bridge_server = bridge_server_cls(
            port=DEFAULT_BRIDGE_PORT,
            on_download=_bridge_dl,
            on_log=_bridge_log,
            on_show=_bridge_show
        )
        self.bridge_server.start()

        # Initialize Clipboard URL Sniffer (TDM-style auto detection)
        self._init_clipboard_sniffer()

        # Configure window close and destroy protocols
        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self.root.bind("<Destroy>", self._on_root_destroyed, add="+")
        except Exception:
            pass

        # Start periodic GUI refresh timer
        self._refresh_job = self.root.after(100, self._gui_refresh_tick)

        # Idempotent and non-blocking embedded browser self-registration
        is_test_env_fn = _get_mw_attr("is_test_environment", _cfg_is_test_env)
        if os.environ.get("SD_DISABLE_AUTO_REGISTER") != "1" and not is_test_env_fn():
            self._start_browser_self_registration()

        self._download_queue: List[Tuple[str, str, int, float]] = []
        self._candidates_modal: Optional[tk.Toplevel] = None
        LocalizationManager.get_instance().register_observer(self._update_ui_language)

        # Non-blocking background check for application and yt-dlp updates
        if os.environ.get("SD_DISABLE_AUTO_UPDATE") != "1" and not is_test_env_fn():
            try:
                self._update_check_job = self.root.after(2500, self._start_auto_update_check)
            except Exception:
                pass
        if not is_test_env_fn():
            try:
                from ...services.media_extractor import warmup_yt_dlp_background
                warmup_yt_dlp_background(3.0)
            except Exception:
                pass

    def _build_ui(self):
        """Constructs all GUI elements: Top Header Bar and 3-Column Kanban Workspace."""
        # Main Outer Border Frame
        main_border = tk.Frame(self.root, bg="#232734", padx=1, pady=1)
        main_border.pack(fill=tk.BOTH, expand=True)
        self.main_border = main_border
        if hasattr(self, "_setup_border_resizing"):
            self._setup_border_resizing(main_border)

        self.container = tk.Frame(main_border, bg="#0b0e14")
        self.container.pack(fill=tk.BOTH, expand=True)

        # 1. Unified Top Navigation Header (Cloud Icon, Brand, URL + Paste, Save to, Download, Settings, Lang)
        self._build_unified_header_bar(self.container)

        # Media options bar host frame (Quality, Dubbing, Subtitles)
        self.media_bar_host = tk.Frame(self.container, bg="#0b0e14", padx=10, pady=2)
        if hasattr(self, "_build_media_options_bar"):
            self._build_media_options_bar(self.media_bar_host)

        # 2. 3-Column Kanban Pipeline Workspace
        self._build_kanban_pipeline(self.container)

        # 3. Compatibility Infrastructure (maintains 100% of internal test/controller widgets)
        self._build_compat_infrastructure(self.container)

        # Ensure resize grips remain above container frames
        if hasattr(self, "_lift_resize_grips"):
            self._lift_resize_grips()


# Backward-compatible GUI aliases
TurboDownloaderGUI = ModernFramelessGUI
DownloaderApp = ModernFramelessGUI
SmartDownloadGUI = ModernFramelessGUI
SmartDownloadApp = ModernFramelessGUI

__all__ = [
    "ModernFramelessGUI",
    "TurboDownloaderGUI",
    "DownloaderApp",
    "SmartDownloadGUI",
    "SmartDownloadApp",
]
