"""
Main official entry-point for Faqih Downloader (FD) | فقيه التنزيلات.
Modular architecture packages are located under src/faqih_downloader/.
This entry-point exposes all symbols, CLI handlers, and starts the GUI application.
"""
__version__ = "2.0.2"

import sys
import os
import time

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

_pkg_dir = os.path.join(_src_dir, "faqih_downloader")
if os.path.isdir(_pkg_dir):
    __path__ = [_pkg_dir]

import importlib
import importlib.abc
import importlib.util

class _SmartDownloadAliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str):
        self.target_name = target_name

    def create_module(self, spec):
        mod = importlib.import_module(self.target_name)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class _SmartDownloadAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == "smart_download" or fullname.startswith("smart_download."):
            target_name = "faqih_downloader" + fullname[14:]
            try:
                spec = importlib.util.find_spec(target_name)
                if spec is not None:
                    alias_spec = importlib.util.spec_from_loader(
                        fullname,
                        _SmartDownloadAliasLoader(target_name),
                        origin=spec.origin,
                        is_package=spec.submodule_search_locations is not None,
                    )
                    alias_spec.submodule_search_locations = spec.submodule_search_locations
                    return alias_spec
            except Exception:
                pass
        return None


if not any(isinstance(f, _SmartDownloadAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _SmartDownloadAliasFinder())

if __name__ in sys.modules:
    sys.modules["smart_download"] = sys.modules[__name__]

# Fast-path for --test-startup verification
if "--test-startup" in sys.argv:
    t0 = time.time()
    _src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if os.path.isdir(_src_dir) and _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    import faqih_downloader.services.youtube_service as youtube_resolver
    t1 = time.time()
    import faqih_downloader.services.browser.bridge_server as browser_bridge
    t2 = time.time()
    import faqih_downloader.services.browser.native_host as native_messaging_host
    t3 = time.time()
    import faqih_downloader.services.browser.registry as register_browser
    t4 = time.time()
    import yt_dlp
    t5 = time.time()
    avail = youtube_resolver.is_ytdlp_available()
    t6 = time.time()
    try:
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(), "test_startup_timing.txt")
        with open(log_path, "w") as f:
            f.write(f"ytdlp_res={t1-t0:.2f}s, bridge={t2-t1:.2f}s, nat={t3-t2:.2f}s, reg={t4-t3:.2f}s, ytdlp={t5-t4:.2f}s, avail={t6-t5:.2f}s, total={t6-t0:.2f}s\n")
    except Exception:
        pass
    if not avail:
        os._exit(1)
    os._exit(0)

# Subprocess handler for standalone --preview-html window
if "--preview-html" in sys.argv:
    try:
        idx = sys.argv.index("--preview-html")
        if idx + 1 < len(sys.argv):
            html_target = sys.argv[idx + 1]
            import webview
            webview.create_window("Faqih Downloader — Video Preview", html_target, width=860, height=560)
            webview.start()
    except Exception:
        pass
    os._exit(0)

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Fast-path for uninstaller execution
if any(arg.lower() in ("--uninstall", "-uninstall", "/uninstall", "/u", "-u", "--uninstall-gui") for arg in sys.argv[1:]):
    from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli
    handle_uninstall_cli()

# Initialize Dynamic Core Loader (Zero-Rebuild Dev Mode & OTA Hot-Patch Plugin)
try:
    from faqih_downloader.services.core_patch_updater import init_core_loader
    init_core_loader()
except Exception:
    pass

# Early Single-Instance Mutex Check: import before heavy modules (Tkinter, PIL, pystray, yt-dlp)
from faqih_downloader.services.single_instance import (
    acquire_single_instance_mutex,
    release_single_instance_mutex,
    notify_running_instance,
    is_single_instance_mutex_held,
    early_single_instance_guard,
)

if __name__ == "__main__":
    early_single_instance_guard()

# Initialize DPI awareness
from faqih_downloader.utils.dpi import enable_high_dpi_awareness, get_windows_work_area
enable_high_dpi_awareness()

# Re-export all config & constants
from faqih_downloader.config import (
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
    get_resource_path,
    get_config_dir,
    get_app_config_dir,
    get_settings_file_path,
    load_settings,
    save_settings,
    get_setting,
    set_setting,
)

# Re-export i18n
from faqih_downloader.locales.i18n import (
    LocalizationManager,
    tr,
    get_current_language,
    set_current_language,
    TRANSLATIONS,
)

# Re-export utils
from faqih_downloader.utils.clipboard import _win32_clipboard_get, get_clipboard_text
from faqih_downloader.utils.url_utils import (
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
from faqih_downloader.utils.speed_utils import parse_speed_limit as parse_speed_limit_direct, format_speed as format_speed_direct
from faqih_downloader.utils.magic_detector import MagicBytesDetector as MagicBytesDetector_direct
from faqih_downloader.utils.archive_utils import calculate_file_integrity as calculate_file_integrity_direct, auto_unpack_archive as auto_unpack_archive_direct
from faqih_downloader.utils.file_ops import (
    MagicBytesDetector,
    calculate_file_integrity,
    auto_unpack_archive,
    get_file_category_and_icon,
    CATEGORY_SUBFOLDERS,
    resolve_categorized_path,
    open_downloaded_file,
    open_containing_folder,
    generate_unique_destination_path,
    apply_media_filename_tags,
)
from faqih_downloader.utils.tk_helpers import (
    _detach_photo_tk,
    _detach_widget_tk_refs,
    _drain_bg_tk_callbacks,
)

# Re-export core
from faqih_downloader.core.rate_limiter import TokenBucketRateLimiter
from faqih_downloader.core.chunk import DownloadChunk, get_permissive_ssl_context, _SSL_CONTEXT_LOCK
from faqih_downloader.core.html_resolver import (
    _HtmlCandidateExtractor,
    resolve_all_download_candidates,
    _HtmlLinkCandidateParser,
    resolve_real_download_url,
    validate_refresh_url,
)
from faqih_downloader.core.engine import TurboDownloadEngine
from faqih_downloader.core.engine_resumer import EngineResumerMixin
from faqih_downloader.core.engine_workers import EngineWorkersMixin
from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
from faqih_downloader.core.history import DownloadHistoryManager

# Re-export services
from faqih_downloader.services.startup_service import (
    IS_WINDOWS,
    WINDOWS_RUN_KEY,
    STARTUP_REG_KEY_NAME,
    LEGACY_STARTUP_REG_KEY_NAME,
    TASK_NAME,
    LEGACY_TASK_NAME,
    get_installed_exe_path,
    get_startup_folder,
    get_startup_dir,
    _parse_startup_cmd,
    _extract_exe_from_cmd,
    _create_startup_shortcut,
    get_startup_command,
    is_startup_enabled,
    enable_startup,
    disable_startup,
    get_startup_entry,
)
from faqih_downloader.services.single_instance import (
    notify_running_instance,
    acquire_single_instance_mutex,
    release_single_instance_mutex,
    is_single_instance_mutex_held,
    early_single_instance_guard,
)
from faqih_downloader.services.media_extractor import (
    _get_yt_dlp,
    warmup_yt_dlp_background,
)
from faqih_downloader.services.youtube_service import (
    YouTubeResolver,
    YouTubeFormatBuilderMixin,
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
    is_ytdlp_extractor_supported,
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
from faqih_downloader.services.youtube_tracks import (
    extract_audio_tracks,
    extract_subtitle_tracks,
    convert_vtt_to_srt,
    download_subtitle_as_srt,
    embed_subtitle_into_mp4,
    handle_subtitles_post_download,
    build_audio_subtitle_row,
)
from faqih_downloader.services.updater_service import (
    parse_version,
    is_newer_version,
    is_version_ge,
    YtDlpAutoUpdater,
    _ExternalYtDlpFinder,
    AppAutoUpdater,
    get_ytdlp_plugin_dir,
    build_core_patch_zip,
    CoreHotPatchUpdater,
    _ExternalCoreFinder,
    get_core_plugin_dir,
    init_core_loader,
)
from faqih_downloader.services.browser.bridge_server import BrowserBridgeServer, DEFAULT_BRIDGE_PORT
from faqih_downloader.services.browser.registry import (
    register_native_host,
    unregister_native_host,
    check_and_register_browser,
    register_browser_extensions,
    unregister_browser_extensions,
    is_registered as is_browser_registered,
    is_extension_registered,
    get_status as get_browser_reg_status,
    compute_unpacked_extension_id,
    get_project_root,
    get_default_extension_origins,
    generate_host_manifest,
    generate_launcher_batch,
)

# Re-export UI & Controllers
from faqih_downloader.ui.controllers.download_controller import DownloadControllerMixin
from faqih_downloader.ui.controllers.media_download_controller import MediaDownloadControllerMixin
from faqih_downloader.ui.controllers.youtube_download_controller import YouTubeDownloadControllerMixin
from faqih_downloader.ui.controllers.batch_download_controller import BatchDownloadControllerMixin
from faqih_downloader.ui.controllers.link_refresh_controller import LinkRefreshControllerMixin
from faqih_downloader.ui.controllers.settings_controller import SettingsControllerMixin
from faqih_downloader.ui.controllers.locale_controller import LocaleControllerMixin
from faqih_downloader.ui.controllers.speed_limiter_controller import SpeedLimiterControllerMixin
from faqih_downloader.ui.controllers.dialog_controller import DialogControllerMixin
from faqih_downloader.ui.controllers.lifecycle_controller import WindowLifecycleMixin
from faqih_downloader.ui.controllers.toast_controller import ToastControllerMixin
from faqih_downloader.ui.controllers.update_controller import UpdateControllerMixin
from faqih_downloader.ui.controllers.theme_controller import ThemeControllerMixin
from faqih_downloader.ui.controllers.dispatch_controller import DispatchControllerMixin
from faqih_downloader.ui.controllers.window_controller import WindowChromeMixin
from faqih_downloader.ui.controllers.browser_controller import BrowserControllerMixin
from faqih_downloader.ui.panels.metrics_panel import MetricsPanelMixin
from faqih_downloader.ui.panels.chunks_panel import ChunksPanelMixin
from faqih_downloader.ui.panels.controls_panel import ControlsPanelMixin
from faqih_downloader.ui.panels.inputs_panel import InputsPanelMixin
from faqih_downloader.ui.panels.history_panel import HistoryPanelMixin
from faqih_downloader.ui.components.top_bar import TopHeaderBarMixin
from faqih_downloader.ui.panels.kanban_panel import KanbanPanelMixin
from faqih_downloader.ui.panels.hidden_compat_panel import HiddenCompatPanelMixin
from faqih_downloader.ui.components.base_modal import SafeModalDialog
from faqih_downloader.ui.components.tooltip import ToolTip
from faqih_downloader.ui.modals.toasts import FetchingLinkToast, StartupWelcomeToast
from faqih_downloader.ui.modals.quality_modal import QualitySelectionModal
from faqih_downloader.ui.modals.settings_modal import SettingsModal
from faqih_downloader.ui.modals.settings_modal_tabs import SettingsModalTabsMixin
from faqih_downloader.ui.modals.settings_modal_extra import SettingsModalExtraMixin
from faqih_downloader.ui.modals.confirm_modal import (
    DownloadConfirmationModal,
    DownloadConfirmationDialog,
    DownloadConfirmModal,
    ConfirmModalLogicMixin,
)
from faqih_downloader.ui.modals.candidates_modal import MultipleCandidatesModal
from faqih_downloader.ui.modals.refresh_modal import RefreshLinkModal, RefreshLinkDialog
from faqih_downloader.ui.modals.update_modal import AppUpdateModal
from faqih_downloader.ui.system_tray import SystemTrayManager, PYSTRAY_AVAILABLE
from faqih_downloader.ui.main_window import (
    ModernFramelessGUI,
    main,
    SmartDownloadEngine,
    TurboDownloaderGUI,
    DownloaderApp,
    SmartDownloadGUI,
)

import types

_SYNC_ACTIVE = False

class _FaqihDownloaderShim(types.ModuleType):
    def __getattr__(self, name):
        if name == "yt_dlp":
            from faqih_downloader.services.media_extractor import _get_yt_dlp
            return _get_yt_dlp()
        return super().__getattr__(name)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        global _SYNC_ACTIVE
        if _SYNC_ACTIVE or name.startswith("__"):
            return
        try:
            _SYNC_ACTIVE = True
            for mod in list(sys.modules.values()):
                if mod is not None and getattr(mod, "__name__", "").startswith("faqih_downloader"):
                    if hasattr(mod, name):
                        try:
                            setattr(mod, name, value)
                        except Exception:
                            pass
            yr = sys.modules.get("youtube_resolver")
            if yr is not None and hasattr(yr, name):
                try:
                    setattr(yr, name, value)
                except Exception:
                    pass
            td = sys.modules.get("turbo_downloader")
            if td is not None and hasattr(td, name):
                try:
                    super(type(td), td).__setattr__(name, value)
                except Exception:
                    try:
                        setattr(td, name, value)
                    except Exception:
                        pass
        finally:
            _SYNC_ACTIVE = False

if __name__ in sys.modules:
    sys.modules[__name__].__class__ = _FaqihDownloaderShim

if __name__ == "__main__":
    main()
