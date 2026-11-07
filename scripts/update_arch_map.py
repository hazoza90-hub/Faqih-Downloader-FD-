"""
Architecture Map Auto-Generator and Verifier (scripts/update_arch_map.py).
Scans src/faqih_downloader/, root shims, and tests/ via Python's ast module,
verifies strict line limits (<550 lines), and synchronizes GEMINI.md and AGENTS.md.
"""
import os
import sys
import ast
import json
from typing import Dict, List, Tuple, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src", "faqih_downloader")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MAX_LINES_PER_FILE = 550

# Predefined contextual responsibilities and "when to edit" hints
FILE_METADATA: Dict[str, Dict[str, str]] = {
    # Core package
    "src/faqih_downloader/__init__.py": {
        "responsibility": "Package initialization and unified namespace re-exports for the core application.",
        "when_to_edit": "Edit when exposing new subpackages or top-level public APIs."
    },
    "src/faqih_downloader/config.py": {
        "responsibility": "Configuration constants, path resolvers, and settings file I/O with caching.",
        "when_to_edit": "Edit when modifying app constants, version, default settings, or storage directories."
    },
    "src/faqih_downloader/i18n.py": {
        "responsibility": "Backward-compatible i18n import shim redirecting to locales.i18n.",
        "when_to_edit": "Edit if re-exporting additional translation functions."
    },
    "src/faqih_downloader/main.py": {
        "responsibility": "Main runtime GUI entry point initializing Tkinter and launching ModernFramelessGUI.",
        "when_to_edit": "Edit when altering CLI argument parsing at launch or main window instantiation."
    },
    "src/faqih_downloader/__main__.py": {
        "responsibility": "Package CLI entry point and CLI dispatcher for python -m faqih_downloader.",
        "when_to_edit": "Edit when modifying CLI execution arguments or package launch hooks."
    },
    "src/faqih_downloader/core/__init__.py": {
        "responsibility": "Re-exports core download engine, chunking, and candidate resolution components.",
        "when_to_edit": "Edit when adding new core download engine modules."
    },
    "src/faqih_downloader/core/candidate_extractor.py": {
        "responsibility": "HTML link extraction using regex patterns and HTML link candidate parsers.",
        "when_to_edit": "Edit when updating candidate download link parsing patterns from HTML documents."
    },
    "src/faqih_downloader/core/chunk.py": {
        "responsibility": "DownloadChunk data class, per-chunk thread state, and permissive SSL context helper.",
        "when_to_edit": "Edit when changing per-chunk data structures or SSL verification policies."
    },
    "src/faqih_downloader/core/engine.py": {
        "responsibility": "TurboDownloadEngine coordinating multi-threaded chunked downloads and rate limiting.",
        "when_to_edit": "Edit when altering download orchestration, speed monitoring, or thread lifecycle."
    },
    "src/faqih_downloader/core/engine_persistence.py": {
        "responsibility": "State persistence mixin saving and resuming partial download progress via .sd_parts.",
        "when_to_edit": "Edit when changing chunk serialization or resume manifest structure."
    },
    "src/faqih_downloader/core/engine_resumer.py": {
        "responsibility": "Engine resumer mixin validating server HTTP range support and multi-chunk compatibility.",
        "when_to_edit": "Edit when modifying HTTP range probe logic or server capability checks."
    },
    "src/faqih_downloader/core/engine_workers.py": {
        "responsibility": "Engine worker pool mixin managing download streams and dynamic midpoint splitting.",
        "when_to_edit": "Edit when modifying parallel worker thread loops or dynamic chunk splitting rules."
    },
    "src/faqih_downloader/core/history.py": {
        "responsibility": "Persistent download history manager tracking completed and active download records.",
        "when_to_edit": "Edit when modifying history record schemas or history storage format."
    },
    "src/faqih_downloader/core/html_resolver.py": {
        "responsibility": "Resolves real download candidates from web pages and validates link refreshes.",
        "when_to_edit": "Edit when improving download candidate probing or link refresh validation."
    },
    "src/faqih_downloader/core/rate_limiter.py": {
        "responsibility": "High-precision TokenBucketRateLimiter enforcing download bandwidth throttling.",
        "when_to_edit": "Edit when tuning speed limiter algorithms or bucket token replenishment."
    },
    "src/faqih_downloader/core/stream_coordinator.py": {
        "responsibility": "StreamDownloadCoordinator managing streaming media downloads and FFmpeg audio/video merges.",
        "when_to_edit": "Edit when altering streaming downloads or post-processing merging steps."
    },

    # Installer package
    "src/faqih_downloader/installer/__init__.py": {
        "responsibility": "Installer package re-exports for setup wizard and ops.",
        "when_to_edit": "Edit when changing public installer API interfaces."
    },
    "src/faqih_downloader/installer/installer_gui.py": {
        "responsibility": "Modern themed Tkinter wizard UI for installing Smart Download.",
        "when_to_edit": "Edit when altering installer wizard steps, styling, or setup progress display."
    },
    "src/faqih_downloader/installer/installer_ops.py": {
        "responsibility": "File deployment, shortcut creation, and payload extraction for Windows installation.",
        "when_to_edit": "Edit when modifying installation payload extraction or uninstaller creation."
    },
    "src/faqih_downloader/installer/installer_registry.py": {
        "responsibility": "Windows Registry manipulation for Add/Remove Programs and startup entries.",
        "when_to_edit": "Edit when changing registry keys for uninstallers or file associations."
    },

    # Locales package
    "src/faqih_downloader/locales/__init__.py": {
        "responsibility": "Locales package re-exports.",
        "when_to_edit": "Edit when modifying locales package exports."
    },
    "src/faqih_downloader/locales/ar.json": {
        "responsibility": "Complete Arabic application translations and right-to-left localized string dictionary.",
        "when_to_edit": "Edit when adding or updating Arabic translation strings."
    },
    "src/faqih_downloader/locales/en.json": {
        "responsibility": "Complete English application translations and UI text string dictionary.",
        "when_to_edit": "Edit when adding or updating English translation strings."
    },
    "src/faqih_downloader/locales/i18n.py": {
        "responsibility": "Thread-safe LocalizationManager singleton enabling dynamic language toggles.",
        "when_to_edit": "Edit when modifying translation loading or language notification callbacks."
    },

    # Services package
    "src/faqih_downloader/services/__init__.py": {
        "responsibility": "Services package namespace re-exports.",
        "when_to_edit": "Edit when exposing new background or platform service modules."
    },
    "src/faqih_downloader/services/single_instance.py": {
        "responsibility": "Single application instance enforcement using Windows named mutex or loopback socket.",
        "when_to_edit": "Edit when altering inter-instance signaling or command line forwarding."
    },
    "src/faqih_downloader/services/startup_service.py": {
        "responsibility": "Zero-elevation Windows auto-start via Run key, Task Scheduler, and Startup folder.",
        "when_to_edit": "Edit when altering Windows background startup mechanisms or startup entry checks."
    },
    "src/faqih_downloader/services/updater_service.py": {
        "responsibility": "Application auto-update manager querying GitHub Releases and launching upgrade installers.",
        "when_to_edit": "Edit when modifying GitHub release querying or update downloading mechanisms."
    },
    "src/faqih_downloader/services/preview_stream_bridge.py": {
        "responsibility": "Built-In In-Memory Preview & Control Bridge HTTP server and web API routing.",
        "when_to_edit": "Edit when modifying in-app preview HTTP bridge or web player controls."
    },
    "src/faqih_downloader/services/preview_stream_proxy.py": {
        "responsibility": "Streaming media proxy and VTT subtitle compiler for real-time video previewing.",
        "when_to_edit": "Edit when changing upstream byte-range streaming proxy or VTT subtitle generation."
    },
    "src/faqih_downloader/services/core_patch_updater.py": {
        "responsibility": "OTA hot-patch packager, atomic updater, and dynamic core loader (zero-rebuild workflow).",
        "when_to_edit": "Edit when modifying core patch packaging, plugin extraction, or dev source overriding."
    },
    "src/faqih_downloader/services/youtube_format_builder.py": {
        "responsibility": "Formats video resolution options, audio bitrates, and file size estimates from metadata.",
        "when_to_edit": "Edit when modifying YouTube/social media format extraction or presentation."
    },
    "src/faqih_downloader/services/youtube_models.py": {
        "responsibility": "Data classes and URL regex patterns for YouTube and social media platforms.",
        "when_to_edit": "Edit when updating social media domain patterns or stream metadata models."
    },
    "src/faqih_downloader/services/youtube_resolver.py": {
        "responsibility": "Backward-compatibility alias re-exporting YouTube and media resolver interfaces.",
        "when_to_edit": "Edit if re-exporting new streaming resolver functions."
    },
    "src/faqih_downloader/services/youtube_service.py": {
        "responsibility": "High-level YouTubeResolver and MediaResolver coordinating yt-dlp and FFmpeg.",
        "when_to_edit": "Edit when changing media stream extraction, cookie passing, or FFmpeg merging."
    },
    "src/faqih_downloader/services/youtube_tracks.py": {
        "responsibility": "YouTube audio dubbing and subtitle tracks extraction, language mapping, and UI track selectors.",
        "when_to_edit": "Edit when modifying audio dubbing languages, subtitle tracks parsing, or quality modal track selectors."
    },
    "src/faqih_downloader/services/subtitle_processor.py": {
        "responsibility": "Subtitle processing, VTT-to-SRT conversion, FFmpeg soft-muxing, and frame burn-in delivery modes.",
        "when_to_edit": "Edit when modifying subtitle delivery modes (srt_only, soft_embed, hard_burn) or FFmpeg subtitle embedding."
    },
    "src/faqih_downloader/services/subtitle_downloader.py": {
        "responsibility": "Subtitle downloading, VTT/XML/JSON parsing, GTX translation, and SRT persistence.",
        "when_to_edit": "Edit when modifying subtitle fetching, timedtext parsing, or auto-translation fallbacks."
    },
    "src/faqih_downloader/services/ytdlp_updater.py": {
        "responsibility": "YtDlpAutoUpdater managing dynamic in-process yt-dlp package updates in %APPDATA%.",
        "when_to_edit": "Edit when changing yt-dlp PyPI/GitHub download logic or sys.meta_path finder hooks."
    },
    "src/faqih_downloader/services/browser/__init__.py": {
        "responsibility": "Browser integration package exports.",
        "when_to_edit": "Edit when modifying browser service exports."
    },
    "src/faqih_downloader/services/browser/bridge_server.py": {
        "responsibility": "Local HTTP bridge server receiving intercepted links from browser extensions.",
        "when_to_edit": "Edit when altering HTTP endpoints or ports for extension communication."
    },
    "src/faqih_downloader/services/browser/host_manifest.py": {
        "responsibility": "Generates native messaging host manifest JSON files for Chrome and Edge.",
        "when_to_edit": "Edit when updating extension IDs or native messaging manifest schemas."
    },
    "src/faqih_downloader/services/browser/native_host.py": {
        "responsibility": "Native messaging host stdio protocol handler reading 32-bit length-prefixed messages.",
        "when_to_edit": "Edit when modifying browser extension stdio communication."
    },
    "src/faqih_downloader/services/browser/registry.py": {
        "responsibility": "Windows Registry manager configuring native messaging host entries for Chrome/Edge.",
        "when_to_edit": "Edit when changing registry paths or browser integration verification logic."
    },

    # UI package
    "src/faqih_downloader/ui/__init__.py": {
        "responsibility": "UI package exports.",
        "when_to_edit": "Edit when exposing new UI components or windows."
    },
    "src/faqih_downloader/ui/main_window.py": {
        "responsibility": "ModernFramelessGUI main application window aggregating all panel and controller mixins.",
        "when_to_edit": "Edit when adding or removing window-level mixins or altering root layout."
    },
    "src/faqih_downloader/ui/system_tray.py": {
        "responsibility": "Windows system tray integration (pystray) with minimize/restore and context menus.",
        "when_to_edit": "Edit when modifying system tray icon behavior or menu options."
    },
    "src/faqih_downloader/ui/components/__init__.py": {
        "responsibility": "Reusable UI components package exports.",
        "when_to_edit": "Edit when exposing new UI components."
    },
    "src/faqih_downloader/ui/components/base_modal.py": {
        "responsibility": "SafeModalDialog: non-blocking frameless themed modal dialog base class.",
        "when_to_edit": "Edit when modifying modal dialog styling, backdrop, or grab behavior."
    },
    "src/faqih_downloader/ui/components/tooltip.py": {
        "responsibility": "Hover tooltip widget providing contextual explanations for buttons and controls.",
        "when_to_edit": "Edit when changing tooltip styling, delay timings, or positioning."
    },

    # UI Controllers
    "src/faqih_downloader/ui/controllers/__init__.py": {
        "responsibility": "Controllers package exports.",
        "when_to_edit": "Edit when adding new controller mixins."
    },
    "src/faqih_downloader/ui/controllers/batch_download_controller.py": {
        "responsibility": "BatchDownloadControllerMixin managing multiple download candidates selection and queueing.",
        "when_to_edit": "Edit when modifying batch link selection or sequential download triggers."
    },
    "src/faqih_downloader/ui/controllers/browser_controller.py": {
        "responsibility": "BrowserControllerMixin handling background extension registration and intercepted downloads.",
        "when_to_edit": "Edit when modifying intercepted browser link handling in the GUI."
    },
    "src/faqih_downloader/ui/controllers/clipboard_controller.py": {
        "responsibility": "ClipboardControllerMixin sniffing clipboard for valid download and media URLs.",
        "when_to_edit": "Edit when modifying clipboard polling intervals, URL regexes, or sniffing logic."
    },
    "src/faqih_downloader/ui/controllers/dialog_controller.py": {
        "responsibility": "DialogControllerMixin providing thread-safe non-blocking modal dialogs.",
        "when_to_edit": "Edit when modifying safe error, warning, or confirmation dialog dispatching."
    },
    "src/faqih_downloader/ui/controllers/dispatch_controller.py": {
        "responsibility": "DispatchControllerMixin dispatching background thread tasks safely to Tkinter event loop.",
        "when_to_edit": "Edit when changing thread synchronization or GUI queue processing."
    },
    "src/faqih_downloader/ui/controllers/download_controller.py": {
        "responsibility": "DownloadControllerMixin coordinating download start, engine creation, and queue execution.",
        "when_to_edit": "Edit when modifying download trigger flow or engine callback wiring."
    },
    "src/faqih_downloader/ui/controllers/lifecycle_controller.py": {
        "responsibility": "WindowLifecycleMixin managing resource cleanup, tray minimization, and clean exit.",
        "when_to_edit": "Edit when modifying window close actions, thread cleanup, or tray exit."
    },
    "src/faqih_downloader/ui/controllers/link_refresh_controller.py": {
        "responsibility": "LinkRefreshControllerMixin handling expired download link resumption and URL substitution.",
        "when_to_edit": "Edit when altering expired link substitution or refresh dialog triggers."
    },
    "src/faqih_downloader/ui/controllers/locale_controller.py": {
        "responsibility": "LocaleControllerMixin coordinating dynamic UI text re-translation upon language switch.",
        "when_to_edit": "Edit when adding dynamic language switch observers or RTL layout adjustments."
    },
    "src/faqih_downloader/ui/controllers/media_download_controller.py": {
        "responsibility": "MediaDownloadControllerMixin composite mixin aggregating YouTube, batch, and refresh.",
        "when_to_edit": "Edit when altering composite media controller inheritance."
    },
    "src/faqih_downloader/ui/controllers/settings_controller.py": {
        "responsibility": "SettingsControllerMixin managing user preferences, cookies, and auto-categorization.",
        "when_to_edit": "Edit when adding new user preference toggles or cookies browser selection."
    },
    "src/faqih_downloader/ui/controllers/speed_limiter_controller.py": {
        "responsibility": "SpeedLimiterControllerMixin managing speed presets, slider events, and rate limits.",
        "when_to_edit": "Edit when modifying speed limiter presets or live slider adjustment handlers."
    },
    "src/faqih_downloader/ui/controllers/theme_controller.py": {
        "responsibility": "ThemeControllerMixin configuring dark theme color tokens and UI styling.",
        "when_to_edit": "Edit when changing application colors, fonts, or styling variables."
    },
    "src/faqih_downloader/ui/controllers/toast_controller.py": {
        "responsibility": "ToastControllerMixin presenting non-blocking corner toast notifications.",
        "when_to_edit": "Edit when modifying startup welcome toast or notification toast animations."
    },
    "src/faqih_downloader/ui/controllers/update_controller.py": {
        "responsibility": "UpdateControllerMixin running background checks for app and yt-dlp updates.",
        "when_to_edit": "Edit when changing background update check frequency or update notification dialogs."
    },
    "src/faqih_downloader/ui/controllers/window_controller.py": {
        "responsibility": "WindowChromeMixin managing custom frameless title bar dragging and window controls.",
        "when_to_edit": "Edit when modifying custom title bar widgets, drag handling, or window geometry."
    },
    "src/faqih_downloader/ui/controllers/youtube_download_controller.py": {
        "responsibility": "YouTubeDownloadControllerMixin analyzing streaming media formats and quality selection.",
        "when_to_edit": "Edit when modifying YouTube/social media format inspection and dialog invocation."
    },

    # UI Modals
    "src/faqih_downloader/ui/modals/__init__.py": {
        "responsibility": "Modals package exports.",
        "when_to_edit": "Edit when adding new modal dialog exports."
    },
    "src/faqih_downloader/ui/modals/browser_settings_modal.py": {
        "responsibility": "BrowserSettingsModalMixin displaying browser extension setup and diagnostic dialog.",
        "when_to_edit": "Edit when modifying browser extension configuration instructions or diagnostic steps."
    },
    "src/faqih_downloader/ui/modals/candidates_modal.py": {
        "responsibility": "MultipleCandidatesModal displaying detected web download candidates with filter badges.",
        "when_to_edit": "Edit when modifying candidate dialog multi-selection, search, or filtering controls."
    },
    "src/faqih_downloader/ui/modals/confirm_modal.py": {
        "responsibility": "DownloadConfirmationModal showing probed file details before starting download.",
        "when_to_edit": "Edit when changing pre-download confirmation dialog layout or field editing."
    },
    "src/faqih_downloader/ui/modals/confirm_modal_logic.py": {
        "responsibility": "Logic helper probing download candidate metadata for the confirmation modal.",
        "when_to_edit": "Edit when modifying candidate probing threads or URL validation."
    },
    "src/faqih_downloader/ui/modals/fetching_toast.py": {
        "responsibility": "FetchingLinkToast displaying a loading spinner toast during link inspection.",
        "when_to_edit": "Edit when modifying link resolving loading animation or cancel triggers."
    },
    "src/faqih_downloader/ui/modals/quality_modal.py": {
        "responsibility": "QualitySelectionModal presenting video resolutions and audio bitrates for media.",
        "when_to_edit": "Edit when modifying media format selection dialog, badges, or treeview."
    },
    "src/faqih_downloader/ui/modals/video_preview_modal.py": {
        "responsibility": "VidMate-style in-app video preview modal with live WebVTT subtitles and chromeless player.",
        "when_to_edit": "Edit when modifying video preview playback, WebVTT subtitle overlay, or player window launcher."
    },
    "src/faqih_downloader/ui/modals/refresh_modal.py": {
        "responsibility": "RefreshLinkModal prompting for updated download link when a session expires.",
        "when_to_edit": "Edit when changing expired link substitution dialog styling or URL validation."
    },
    "src/faqih_downloader/ui/modals/toasts.py": {
        "responsibility": "Re-exports toast notification classes for convenient imports.",
        "when_to_edit": "Edit when exposing additional toast classes."
    },
    "src/faqih_downloader/ui/modals/update_modal.py": {
        "responsibility": "AppUpdateModal displaying new release notes and one-click update actions.",
        "when_to_edit": "Edit when modifying application update presentation or release notes formatting."
    },
    "src/faqih_downloader/ui/modals/welcome_toast.py": {
        "responsibility": "StartupWelcomeToast displaying Windows startup greeting when running minimized.",
        "when_to_edit": "Edit when modifying startup toast layout or click-to-restore action."
    },

    # UI Panels
    "src/faqih_downloader/ui/panels/__init__.py": {
        "responsibility": "Panels package exports.",
        "when_to_edit": "Edit when adding new panel mixin exports."
    },
    "src/faqih_downloader/ui/panels/chunks_panel.py": {
        "responsibility": "ChunksPanelMixin rendering segmented dynamic chunk visualizer and status table.",
        "when_to_edit": "Edit when modifying segmented chunk canvas graphics or chunk details treeview."
    },
    "src/faqih_downloader/ui/panels/controls_panel.py": {
        "responsibility": "ControlsPanelMixin rendering thread selector, speed limiter controls, and action buttons.",
        "when_to_edit": "Edit when changing start/pause/cancel action buttons or limiter controls."
    },
    "src/faqih_downloader/ui/panels/history_panel.py": {
        "responsibility": "HistoryPanelMixin managing download history table and right-click context menu.",
        "when_to_edit": "Edit when modifying history treeview columns or context menu actions."
    },
    "src/faqih_downloader/ui/panels/inputs_panel.py": {
        "responsibility": "InputsPanelMixin rendering URL and destination inputs with auto-categorization button.",
        "when_to_edit": "Edit when modifying URL entry, destination browse button, or auto-cat toggle."
    },
    "src/faqih_downloader/ui/panels/metrics_panel.py": {
        "responsibility": "MetricsPanelMixin rendering overall progress bar and real-time metric cards.",
        "when_to_edit": "Edit when modifying speed, size, ETA, or thread count metric cards."
    },

    # Utils package
    "src/faqih_downloader/utils/__init__.py": {
        "responsibility": "Utils package exports.",
        "when_to_edit": "Edit when exporting new utility helpers."
    },
    "src/faqih_downloader/utils/archive_utils.py": {
        "responsibility": "Archive auto-extraction and SHA-256 file integrity verification.",
        "when_to_edit": "Edit when supporting new archive formats or hash algorithms."
    },
    "src/faqih_downloader/utils/clipboard.py": {
        "responsibility": "Cross-platform and Win32 direct clipboard text retrieval.",
        "when_to_edit": "Edit when improving clipboard access reliability on Windows."
    },
    "src/faqih_downloader/utils/dpi.py": {
        "responsibility": "Windows High-DPI awareness initialization and screen work area geometry.",
        "when_to_edit": "Edit when tuning DPI scaling factors or multi-monitor geometry detection."
    },
    "src/faqih_downloader/utils/file_ops.py": {
        "responsibility": "File categorization into subfolders (Videos, Music, etc.) and file/folder launching.",
        "when_to_edit": "Edit when modifying category subfolder mappings or OS shell execute actions."
    },
    "src/faqih_downloader/utils/magic_detector.py": {
        "responsibility": "Binary magic bytes detector determining actual file types independent of URL extensions.",
        "when_to_edit": "Edit when adding new file signature definitions."
    },
    "src/faqih_downloader/utils/speed_utils.py": {
        "responsibility": "Speed string parsing (e.g. '1.5 MB/s') and human-readable formatting.",
        "when_to_edit": "Edit when updating speed parsing regexes or unit formats."
    },
    "src/faqih_downloader/utils/tk_helpers.py": {
        "responsibility": "Tkinter resource cleanup preventing photo reference and callback memory leaks.",
        "when_to_edit": "Edit when adding memory leak mitigations for Tkinter widgets."
    },
    "src/faqih_downloader/utils/url_utils.py": {
        "responsibility": "URL parsing, filename derivation, and Content-Disposition header extraction.",
        "when_to_edit": "Edit when improving filename derivation from complex redirect URLs."
    },

    # Root entry point, shims & tools
    "faqih_downloader.py": {
        "responsibility": "Main official application entry point, CLI dispatcher, and unified symbol re-exporter.",
        "when_to_edit": "Edit when updating top-level launch hooks, CLI flags, or application initialization."
    },
    "turbo_downloader.py": {
        "responsibility": "Backward-compatibility root shim re-exporting all symbols from faqih_downloader.",
        "when_to_edit": "Edit when maintaining legacy backward-compatible import compatibility."
    },
    "browser_bridge.py": {
        "responsibility": "Backward-compatibility root shim re-exporting BrowserBridgeServer.",
        "when_to_edit": "Edit when changing browser bridge root exports."
    },
    "native_messaging_host.py": {
        "responsibility": "Backward-compatibility root shim re-exporting native messaging host functions.",
        "when_to_edit": "Edit when updating native messaging entry point."
    },
    "register_browser.py": {
        "responsibility": "Backward-compatibility root shim for browser extension registration commands.",
        "when_to_edit": "Edit when updating browser registration CLI entry point."
    },
    "updater.py": {
        "responsibility": "Backward-compatibility root shim re-exporting AppAutoUpdater and CoreHotPatchUpdater.",
        "when_to_edit": "Edit when adding top-level updater exports."
    },
    "youtube_resolver.py": {
        "responsibility": "Backward-compatibility root shim re-exporting YouTube and media resolver interfaces.",
        "when_to_edit": "Edit when updating YouTube resolver root exports."
    },
    "release_publisher.py": {
        "responsibility": "Automated GitHub Releases publisher supporting fast zero-rebuild core patch publishing.",
        "when_to_edit": "Edit when modifying release publishing workflow or asset upload logic."
    },
    "build_installer.py": {
        "responsibility": "Automated build script compiling PyInstaller bundles and Windows setup installer.",
        "when_to_edit": "Edit ONLY when user explicitly commands 'build installer' or 'ابنِ المثبت'."
    },
    "installer.py": {
        "responsibility": "Standalone installer runner executing SmartDownload setup wizard.",
        "when_to_edit": "Edit when modifying standalone installer CLI options."
    },

    # Tests
    "tests/__init__.py": {
        "responsibility": "Tests package initialization.",
        "when_to_edit": "Edit when configuring test discovery fixtures."
    },
    "tests/test_browser.py": {
        "responsibility": "Unit tests for browser extension bridge, native host stdio, and Windows registry.",
        "when_to_edit": "Edit when adding tests for browser integration features."
    },
    "tests/test_dpi_and_assets.py": {
        "responsibility": "Unit tests for Windows High-DPI scaling, icons, and asset resolution.",
        "when_to_edit": "Edit when adding tests for display scaling or asset bundling."
    },
    "tests/test_engine_core.py": {
        "responsibility": "Unit tests for TurboDownloadEngine, chunking, rate limiting, and worker pooling.",
        "when_to_edit": "Edit when testing download core algorithms and throttling."
    },
    "tests/test_engine_resume.py": {
        "responsibility": "Unit tests for download pause, resume, and .sd_parts persistence.",
        "when_to_edit": "Edit when testing download resumption and manifest serialization."
    },
    "tests/test_html_candidates.py": {
        "responsibility": "Unit tests for web page candidate link extraction and filtering.",
        "when_to_edit": "Edit when testing HTML candidate link discovery."
    },
    "tests/test_i18n.py": {
        "responsibility": "Unit tests for Arabic and English translations and runtime language toggling.",
        "when_to_edit": "Edit when adding i18n and localization test cases."
    },
    "tests/test_installer.py": {
        "responsibility": "Unit tests for installer file extraction, registry keys, and shortcuts.",
        "when_to_edit": "Edit when testing Windows installer operations."
    },
    "tests/test_main_window_actions.py": {
        "responsibility": "Unit tests for main window user actions, queueing, and callbacks.",
        "when_to_edit": "Edit when testing GUI button actions and download queueing."
    },
    "tests/test_main_window_ui.py": {
        "responsibility": "Unit tests for main window UI structure, widget creation, and layout.",
        "when_to_edit": "Edit when testing window geometry, cards, and widget hierarchies."
    },
    "tests/test_modals_confirm.py": {
        "responsibility": "Unit tests for DownloadConfirmationModal and candidate size probing.",
        "when_to_edit": "Edit when testing confirmation modal logic."
    },
    "tests/test_modals_other.py": {
        "responsibility": "Unit tests for quality, refresh, browser settings, and toast modals.",
        "when_to_edit": "Edit when testing secondary modal dialogs and toasts."
    },
    "tests/test_settings_history.py": {
        "responsibility": "Unit tests for settings persistence, auto-categorization, and history manager.",
        "when_to_edit": "Edit when testing preferences and download history operations."
    },
    "tests/test_stage4_srp_decomposition.py": {
        "responsibility": "Unit tests verifying strict SRP decomposition (<550 lines per file).",
        "when_to_edit": "Edit when adding new decomposed modules to verify strict line limits."
    },
    "tests/test_core_patch_updater.py": {
        "responsibility": "Unit tests for CoreHotPatchUpdater, packaging, rollback, and dynamic loading.",
        "when_to_edit": "Edit when testing OTA core hot-patching or zero-rebuild workflow."
    },
    "tests/test_updater.py": {
        "responsibility": "Unit tests for AppAutoUpdater, YtDlpAutoUpdater, and version unification.",
        "when_to_edit": "Edit when testing app/yt-dlp auto-updates or version comparison."
    },
    "tests/test_url_resolver.py": {
        "responsibility": "Unit tests for URL utilities, filename sanitization, and speed formatting.",
        "when_to_edit": "Edit when testing URL manipulation and parsing utilities."
    },
    "tests/test_youtube_extract.py": {
        "responsibility": "Unit tests for YouTube and social media link extraction with yt-dlp.",
        "when_to_edit": "Edit when testing social media stream resolution."
    },
    "tests/test_youtube_merge.py": {
        "responsibility": "Unit tests for FFmpeg video + audio stream merging and format building.",
        "when_to_edit": "Edit when testing FFmpeg post-processing operations."
    },
}


def analyze_python_file(file_path: str) -> Dict[str, Any]:
    """Analyzes a Python file using AST to extract classes, functions, and line count."""
    rel_path = os.path.relpath(file_path, PROJECT_ROOT).replace("\\", "/")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    lines = content.splitlines()
    line_count = len(lines)

    classes: List[str] = []
    functions: List[str] = []
    docstring = ""

    try:
        tree = ast.parse(content, filename=file_path)
        docstring = ast.get_docstring(tree) or ""
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") or node.name.startswith("__"):
                    functions.append(node.name)
                elif node.name in ("_load_locale", "_ExternalCoreFinder", "_ExternalYtDlpFinder"):
                    functions.append(node.name)
    except Exception as e:
        classes.append(f"Error parsing AST: {e}")

    meta = FILE_METADATA.get(rel_path, {})
    resp = meta.get("responsibility")
    if not resp and docstring:
        resp = docstring.strip().splitlines()[0].strip()
    if not resp:
        resp = "Module implementation for Smart Download."

    when_to = meta.get("when_to_edit", "Edit when modifying this module's features.")

    return {
        "path": rel_path,
        "line_count": line_count,
        "classes": classes,
        "functions": functions[:6],  # limit to top 6 functions to keep tables clean
        "responsibility": resp,
        "when_to_edit": when_to,
    }


def collect_all_files() -> List[Dict[str, Any]]:
    """Collects and analyzes all tracked files in src/, root shims, and tests/."""
    all_records: List[Dict[str, Any]] = []

    # 1. Source files
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for f in sorted(files):
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, PROJECT_ROOT).replace("\\", "/")
            if f.endswith(".py"):
                all_records.append(analyze_python_file(full_p))
            elif f.endswith(".json"):
                with open(full_p, "r", encoding="utf-8", errors="ignore") as fp:
                    lc = len(fp.readlines())
                meta = FILE_METADATA.get(rel_p, {})
                all_records.append({
                    "path": rel_p,
                    "line_count": lc,
                    "classes": [],
                    "functions": [],
                    "responsibility": meta.get("responsibility", "JSON data resource."),
                    "when_to_edit": meta.get("when_to_edit", "Edit when updating localized strings or configuration."),
                })

    # 2. Root shims
    root_shims = [
        "faqih_downloader.py",
        "turbo_downloader.py",
        "browser_bridge.py",
        "native_messaging_host.py",
        "register_browser.py",
        "updater.py",
        "youtube_resolver.py",
        "release_publisher.py",
        "build_installer.py",
        "installer.py",
    ]
    for rf in root_shims:
        full_p = os.path.join(PROJECT_ROOT, rf)
        if os.path.isfile(full_p):
            all_records.append(analyze_python_file(full_p))

    # 3. Tests
    for root, dirs, files in os.walk(TESTS_DIR):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for f in sorted(files):
            if f.endswith(".py"):
                full_p = os.path.join(root, f)
                all_records.append(analyze_python_file(full_p))

    return all_records


def generate_architecture_markdown(records: List[Dict[str, Any]]) -> str:
    """Generates complete GEMINI.md / AGENTS.md document."""
    lines: List[str] = []
    lines.append("# Faqih Downloader (FD) | فقيه التنزيلات — Persistent AI Architecture & Dependency Map")
    lines.append("")
    lines.append("> **Auto-generated and verified by `python scripts/update_arch_map.py`**.")
    lines.append("> This document provides the complete, authoritative architectural layout, mixin hierarchy,")
    lines.append("> data flow graph, and file-by-file inventory of Faqih Downloader (FD) | فقيه التنزيلات. Read this file at the start")
    lines.append("> of every session to immediately navigate the codebase without guessing.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. ⚠️ Strict Agent Workflow Rules (CRITICAL)")
    lines.append("")
    lines.append("### 0. ZERO-REGRESSION & SURGICAL EDIT RULE")
    lines.append("- **تعديل الملفات المحددة فقط**: يُمنع منعاً باتاً تعديل أي ملف خارج نطاق الطلب المحدد بالاسم.")
    lines.append("- **مراجعة التغييرات**: مراجعة `git diff` سطراً بسطر قبل أي Commit للتأكد من عدم حذف أي دالة أو عنصر واجهة أو إطار Tkinter.")
    lines.append("- **فحص سلامة المكونات**: تشغيل `FaqihDownloader.exe --test-startup` للتحقق الإلزامي من سلامة الأيقونات و `PIL` و `FFmpeg` والواجهة قبل الاعتماد.")
    lines.append("")
    lines.append("1. **NEVER run `PyInstaller` or `build_installer.py` automatically after code edits!**")
    lines.append("   - Compiling `.exe` binaries takes 3–5 minutes and is **strictly forbidden** during routine edits.")
    lines.append("   - Only build the installer if the user explicitly types: `\"build installer\"` or `\"ابنِ المثبت\"`.")
    lines.append("")
    lines.append("2. **Fast Unit Verification Only (<2 seconds)**:")
    lines.append("   - After editing a module, ONLY run the single test file relevant to that module:")
    lines.append("     - e.g., `python -m unittest tests/test_updater.py` (finishes in ~3s).")
    lines.append("     - e.g., `python -m unittest tests/test_stage4_srp_decomposition.py` (finishes in 0.01s).")
    lines.append("   - Do NOT run the full test suite after small edits unless requested.")
    lines.append("")
    lines.append("3. **Strict Single Responsibility Principle (<550 lines per file)**:")
    lines.append("   - Every file in `src/faqih_downloader/` must remain under **550 physical lines**.")
    lines.append("   - If adding logic causes a file to approach 550 lines, decompose it into a specialized mixin or helper module.")
    lines.append("")
    lines.append("4. **Zero-Rebuild Core Hot-Patch Workflow**:")
    lines.append("   - Core application edits do NOT require rebuilding `FaqihDownloader.exe`.")
    lines.append("   - For local development: Set `SD_DEV_SRC` or run `FaqihDownloader.exe` adjacent to `src/` to load code directly.")
    lines.append("   - For remote distribution: Run `python -c \"from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')\"` to produce a ~120 KB hot-patch in <0.5 seconds.")
    lines.append("")
    lines.append("5. **Architecture Synchronization**:")
    lines.append("   - Whenever a file, class, or method is added, deleted, or moved, execute:")
    lines.append("     ```bash")
    lines.append("     python scripts/update_arch_map.py")
    lines.append("     ```")
    lines.append("     to ensure `GEMINI.md` and `AGENTS.md` remain 100% synchronized.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. 🏛️ Class Inheritance & Connection Graph")
    lines.append("")
    lines.append("### A. ModernFramelessGUI Mixin Inheritance Hierarchy")
    lines.append("`ModernFramelessGUI` in `src/faqih_downloader/ui/main_window.py` is composed of 22 specialized mixins:")
    lines.append("")
    lines.append("```text")
    lines.append("ModernFramelessGUI (tk.Tk root)")
    lines.append("├── BrowserSettingsModalMixin (ui/modals/browser_settings_modal.py)")
    lines.append("│   └── BrowserControllerMixin (ui/controllers/browser_controller.py)")
    lines.append("├── HistoryPanelMixin (ui/panels/history_panel.py)")
    lines.append("├── ChunksPanelMixin (ui/panels/chunks_panel.py)")
    lines.append("│   └── MetricsPanelMixin (ui/panels/metrics_panel.py)")
    lines.append("├── InputsPanelMixin (ui/panels/inputs_panel.py)")
    lines.append("│   └── ControlsPanelMixin (ui/panels/controls_panel.py)")
    lines.append("├── ClipboardControllerMixin (ui/controllers/clipboard_controller.py)")
    lines.append("├── UpdateControllerMixin (ui/controllers/update_controller.py)")
    lines.append("│   └── ToastControllerMixin (ui/controllers/toast_controller.py)")
    lines.append("├── DownloadControllerMixin (ui/controllers/download_controller.py)")
    lines.append("│   └── MediaDownloadControllerMixin (ui/controllers/media_download_controller.py)")
    lines.append("│       ├── YouTubeDownloadControllerMixin (ui/controllers/youtube_download_controller.py)")
    lines.append("│       ├── BatchDownloadControllerMixin (ui/controllers/batch_download_controller.py)")
    lines.append("│       └── LinkRefreshControllerMixin (ui/controllers/link_refresh_controller.py)")
    lines.append("├── SettingsControllerMixin (ui/controllers/settings_controller.py)")
    lines.append("│   ├── LocaleControllerMixin (ui/controllers/locale_controller.py)")
    lines.append("│   └── SpeedLimiterControllerMixin (ui/controllers/speed_limiter_controller.py)")
    lines.append("└── WindowChromeMixin (ui/controllers/window_controller.py)")
    lines.append("    ├── ThemeControllerMixin (ui/controllers/theme_controller.py)")
    lines.append("    ├── DispatchControllerMixin (ui/controllers/dispatch_controller.py)")
    lines.append("    └── WindowLifecycleMixin (ui/controllers/lifecycle_controller.py)")
    lines.append("        └── DialogControllerMixin (ui/controllers/dialog_controller.py)")
    lines.append("```")
    lines.append("")
    lines.append("### B. TurboDownloadEngine & YouTubeResolver Hierarchy")
    lines.append("")
    lines.append("```text")
    lines.append("EngineResumerMixin (core/engine_resumer.py)")
    lines.append("└── EngineWorkersMixin (core/engine_workers.py)")
    lines.append("    └── TurboDownloadEngine (core/engine.py) + EnginePersistenceMixin (core/engine_persistence.py)")
    lines.append("")
    lines.append("YouTubeFormatBuilderMixin (services/youtube_format_builder.py)")
    lines.append("└── YouTubeResolver (services/youtube_service.py) -> alias MediaResolver")
    lines.append("```")
    lines.append("")
    lines.append("### C. Data & Event Flow Architecture")
    lines.append("")
    lines.append("```text")
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│ Browser Extension (Chrome / Edge / Brave / Opera)           │")
    lines.append("└──────────────┬──────────────────────────────┬───────────────┘")
    lines.append("               │ (stdio length-prefixed)      │ (HTTP POST port 9654)")
    lines.append("               ▼                              ▼")
    lines.append("  services/browser/native_host.py   services/browser/bridge_server.py")
    lines.append("               │                              │")
    lines.append("               └──────────────┬───────────────┘")
    lines.append("                              ▼")
    lines.append("              ui/controllers/browser_controller.py")
    lines.append("                              │ (dispatch_to_main_thread)")
    lines.append("                              ▼")
    lines.append("              ui/controllers/download_controller.py")
    lines.append("                     │                     │")
    lines.append("         [Media / YouTube URL]        [Direct File URL]")
    lines.append("                     ▼                     ▼")
    lines.append("          services/youtube_service.py     core/engine.py")
    lines.append("          (MediaResolver / yt-dlp)       (TurboDownloadEngine)")
    lines.append("                     │                     │")
    lines.append("                     ▼                     │")
    lines.append("          core/stream_coordinator.py       │")
    lines.append("          (FFmpeg Audio+Video Merge)       │")
    lines.append("                     │                     │")
    lines.append("                     └──────────┬──────────┘")
    lines.append("                                ▼")
    lines.append("               Real-time UI Event Dispatchers:")
    lines.append("               - ui/panels/metrics_panel.py (Speed, Size, ETA, Threads)")
    lines.append("               - ui/panels/chunks_panel.py (Visual Segment Map)")
    lines.append("               - ui/panels/history_panel.py (Persistent Record)")
    lines.append("               - ui/system_tray.py (Status tooltip & toasts)")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. 📂 Complete File-by-File Inventory & Responsibility Table")
    lines.append("")
    lines.append("| File Path | Lines | Responsibility | Key Classes / Functions | When to Edit |")
    lines.append("|:---|:---:|:---|:---|:---|")

    for rec in records:
        path = rec["path"]
        lc = rec["line_count"]
        resp = rec["responsibility"]
        when_to = rec["when_to_edit"]
        classes = rec["classes"]
        funcs = rec["functions"]

        symbols = []
        if classes:
            symbols.extend([f"`{c}`" for c in classes])
        if funcs:
            symbols.extend([f"`{f}()`" for f in funcs[:3]])
        sym_str = ", ".join(symbols) if symbols else "—"

        lines.append(f"| `{path}` | {lc} | {resp} | {sym_str} | {when_to} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. ⚡ Verification Commands Cheat Sheet")
    lines.append("")
    lines.append("| Task | Command | Typical Time |")
    lines.append("|:---|:---|:---:|")
    lines.append("| Verify OTA Core Hot-Patch | `python -m unittest tests/test_core_patch_updater.py` | ~0.5s |")
    lines.append("| Verify App & Yt-Dlp Updater | `python -m unittest tests/test_updater.py` | ~3.5s |")
    lines.append("| Verify Strict SRP Line Limits (<550) | `python -m unittest tests/test_stage4_srp_decomposition.py` | ~0.01s |")
    lines.append("| Verify Architecture Map Sync | `python scripts/update_arch_map.py --check` | ~0.15s |")
    lines.append("| Verify YouTube Extraction | `python -m unittest tests/test_youtube_extract.py` | ~1.5s |")
    lines.append("| Verify Engine Resume & Persistence | `python -m unittest tests/test_engine_resume.py` | ~1.2s |")
    lines.append("| Build Core Hot-Patch (~120 KB) | `python -c \"from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')\"` | <0.5s |")
    lines.append("")
    lines.append("*(Reminder: NEVER run PyInstaller or `build_installer.py` unless user explicitly commands: `build installer`)*")
    lines.append("")

    return "\n".join(lines)


def main():
    check_mode = "--check" in sys.argv
    records = collect_all_files()

    # 1. Verify SRP limit
    over_limit: List[Tuple[str, int]] = []
    for r in records:
        if r["path"].startswith("src/faqih_downloader/") and r["line_count"] > MAX_LINES_PER_FILE:
            over_limit.append((r["path"], r["line_count"]))

    if over_limit:
        print(f"❌ ERROR: Strict SRP violation! {len(over_limit)} files exceed {MAX_LINES_PER_FILE} lines:")
        for p, count in over_limit:
            print(f"   - {p}: {count} lines")
        sys.exit(1)

    print(f"✅ Verified {len(records)} files. All src/faqih_downloader/ files satisfy SRP (<{MAX_LINES_PER_FILE} lines).")

    new_content = generate_architecture_markdown(records)

    gemini_path = os.path.join(PROJECT_ROOT, "GEMINI.md")
    agents_path = os.path.join(PROJECT_ROOT, "AGENTS.md")

    if check_mode:
        if not os.path.isfile(gemini_path) or not os.path.isfile(agents_path):
            print("❌ GEMINI.md or AGENTS.md missing.")
            sys.exit(1)
        with open(gemini_path, "r", encoding="utf-8") as f:
            cur_gemini = f.read()
        with open(agents_path, "r", encoding="utf-8") as f:
            cur_agents = f.read()
        if cur_gemini != new_content or cur_agents != new_content:
            print("❌ GEMINI.md or AGENTS.md is out of sync with current codebase.")
            sys.exit(1)
        print("✅ GEMINI.md and AGENTS.md are 100% synchronized with codebase.")
        sys.exit(0)

    with open(gemini_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ Successfully synchronized {gemini_path} and {agents_path} ({len(new_content):,} bytes).")


if __name__ == "__main__":
    main()
