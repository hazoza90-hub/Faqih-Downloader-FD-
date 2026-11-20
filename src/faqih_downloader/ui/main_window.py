"""
Backward-compatibility shim for main_window.
Re-exports ModernFramelessGUI, main, and all legacy constants and helper symbols.
"""
from __future__ import annotations

import sys
import os
import threading
from typing import Any

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except Exception:
    tk = ttk = messagebox = filedialog = None  # type: ignore

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from ..config import (
    get_resource_path,
    get_config_dir,
    get_app_config_dir,
    get_settings_file_path,
    is_test_environment,
    load_settings,
    save_settings,
    get_setting,
    set_setting,
    APP_NAME,
    APP_TITLE,
    APP_ID,
    APP_VERSION,
    APP_AUTHOR,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
    DEFAULT_USER_AGENT,
    CHUNK_SIZE_KB,
    MAX_CONCURRENT_CHUNKS,
    DEFAULT_CHUNKS,
    MIN_CHUNK_BYTES,
    BUFFER_SIZE,
    DEFAULT_SNIFFER_PLATFORMS,
)
from ..locales.i18n import (
    LocalizationManager,
    tr,
    get_current_language,
    set_current_language,
    TRANSLATIONS,
)
from ..utils.dpi import enable_high_dpi_awareness, get_windows_work_area
from ..utils.clipboard import _win32_clipboard_get, get_clipboard_text
from ..utils.url_utils import (
    COMMON_DOWNLOAD_EXTENSIONS,
    WEB_SCRIPT_EXTENSIONS,
    is_downloadable_url,
    clean_download_filename,
    derive_download_filename,
    is_potential_html_url,
    parse_filename_from_cd_header,
    parse_speed_limit,
    format_speed,
)
from ..utils.file_ops import (
    MagicBytesDetector,
    calculate_file_integrity,
    auto_unpack_archive,
    get_file_category_and_icon,
    CATEGORY_SUBFOLDERS,
    resolve_categorized_path,
    open_downloaded_file,
    open_containing_folder,
)
from ..utils.tk_helpers import (
    _detach_photo_tk,
    _detach_widget_tk_refs,
    _drain_bg_tk_callbacks,
)
from ..core.rate_limiter import TokenBucketRateLimiter
from ..core.chunk import DownloadChunk, get_permissive_ssl_context, _SSL_CONTEXT_LOCK
from ..core.html_resolver import (
    _HtmlCandidateExtractor,
    resolve_all_download_candidates,
    _HtmlLinkCandidateParser,
    resolve_real_download_url,
    validate_refresh_url,
)
from ..core.engine import TurboDownloadEngine
from ..core.stream_coordinator import StreamDownloadCoordinator
from ..core.history import DownloadHistoryManager

from ..services.startup_service import (
    IS_WINDOWS,
    GWL_STYLE,
    GWL_EXSTYLE,
    WS_EX_APPWINDOW,
    WS_EX_TOOLWINDOW,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    SW_HIDE,
    SW_MINIMIZE,
    SW_RESTORE,
    SW_SHOW,
    get_installed_exe_path,
    get_startup_folder,
    get_startup_dir,
    is_startup_enabled,
    enable_startup,
    disable_startup,
    get_startup_entry,
)
from ..services.single_instance import (
    notify_running_instance,
    acquire_single_instance_mutex,
    is_single_instance_mutex_held,
    release_single_instance_mutex,
)
from ..services.youtube_service import (
    YouTubeResolver,
    MediaResolver,
    is_youtube_url,
    is_social_media_url,
    is_media_url,
    extract_youtube_id,
    extract_media_platform,
    extract_media_id,
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
    has_ffmpeg,
    find_ffmpeg_bin,
    sanitize_filename,
    YouTubeStreamInfo,
    MediaStreamInfo,
    VideoFormatOption,
    format_filesize,
    SUPPORTED_COOKIE_BROWSERS,
    detect_installed_cookie_browsers,
)
from ..services.updater_service import (
    parse_version,
    is_newer_version,
    YtDlpAutoUpdater,
    AppAutoUpdater,
    get_ytdlp_plugin_dir,
)
from ..services.browser.bridge_server import BrowserBridgeServer, DEFAULT_BRIDGE_PORT
from ..services.browser.registry import (
    register_native_host,
    unregister_native_host,
    check_and_register_browser,
    register_browser_extensions,
    unregister_browser_extensions,
    is_registered as is_browser_registered,
    get_status as get_browser_reg_status,
)

from .components.base_modal import SafeModalDialog
from .components.tooltip import ToolTip
from .modals.toasts import FetchingLinkToast, StartupWelcomeToast
from .modals.quality_modal import QualitySelectionModal
from .modals.confirm_modal import (
    DownloadConfirmationModal,
    DownloadConfirmationDialog,
    DownloadConfirmModal,
)
from .modals.candidates_modal import MultipleCandidatesModal
from .modals.refresh_modal import RefreshLinkModal, RefreshLinkDialog
from .modals.update_modal import AppUpdateModal
from .system_tray import SystemTrayManager, PYSTRAY_AVAILABLE

from .components.top_bar import TopHeaderBarMixin
from .panels.kanban_panel import KanbanPanelMixin
from .panels.hidden_compat_panel import HiddenCompatPanelMixin
from .modals.browser_settings_modal import BrowserSettingsModalMixin
from .panels.history_panel import HistoryPanelMixin
from .panels.chunks_panel import ChunksPanelMixin
from .panels.inputs_panel import InputsPanelMixin
from .panels.media_options_bar import MediaOptionsBarMixin
from .controllers.clipboard_controller import ClipboardControllerMixin
from .controllers.update_controller import UpdateControllerMixin
from .controllers.download_controller import DownloadControllerMixin
from .controllers.settings_controller import SettingsControllerMixin
from .controllers.window_controller import WindowChromeMixin

from .app import (
    ModernFramelessGUI,
    TurboDownloaderGUI,
    DownloaderApp,
    SmartDownloadGUI,
    SmartDownloadApp,
    SmartDownloadEngine,
    main,
)

__all__ = [
    "ModernFramelessGUI",
    "TurboDownloaderGUI",
    "DownloaderApp",
    "SmartDownloadGUI",
    "SmartDownloadApp",
    "SmartDownloadEngine",
    "main",
    "TopHeaderBarMixin",
    "KanbanPanelMixin",
    "HiddenCompatPanelMixin",
    "BrowserSettingsModalMixin",
    "HistoryPanelMixin",
    "ChunksPanelMixin",
    "InputsPanelMixin",
    "MediaOptionsBarMixin",
    "ClipboardControllerMixin",
    "UpdateControllerMixin",
    "DownloadControllerMixin",
    "SettingsControllerMixin",
    "WindowChromeMixin",
    "SystemTrayManager",
    "BrowserBridgeServer",
    "TurboDownloadEngine",
    "StreamDownloadCoordinator",
    "DownloadHistoryManager",
    "YouTubeResolver",
    "MediaResolver",
    "DEFAULT_SNIFFER_PLATFORMS",
    "is_startup_enabled",
    "enable_startup",
    "disable_startup",
    "acquire_single_instance_mutex",
    "is_single_instance_mutex_held",
    "notify_running_instance",
    "release_single_instance_mutex",
    "is_test_environment",
    "get_setting",
    "set_setting",
]

if __name__ == "__main__":
    main()
