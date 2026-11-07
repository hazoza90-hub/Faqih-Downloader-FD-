# Faqih Downloader (FD) | فقيه التنزيلات — Persistent AI Architecture & Dependency Map

> **Auto-generated and verified by `python scripts/update_arch_map.py`**.
> This document provides the complete, authoritative architectural layout, mixin hierarchy,
> data flow graph, and file-by-file inventory of Faqih Downloader (FD) | فقيه التنزيلات. Read this file at the start
> of every session to immediately navigate the codebase without guessing.

---

## 1. ⚠️ Strict Agent Workflow Rules (CRITICAL)

### 0. ZERO-REGRESSION & SURGICAL EDIT RULE
- **تعديل الملفات المحددة فقط**: يُمنع منعاً باتاً تعديل أي ملف خارج نطاق الطلب المحدد بالاسم.
- **مراجعة التغييرات**: مراجعة `git diff` سطراً بسطر قبل أي Commit للتأكد من عدم حذف أي دالة أو عنصر واجهة أو إطار Tkinter.
- **فحص سلامة المكونات**: تشغيل `FaqihDownloader.exe --test-startup` للتحقق الإلزامي من سلامة الأيقونات و `PIL` و `FFmpeg` والواجهة قبل الاعتماد.

1. **NEVER run `PyInstaller` or `build_installer.py` automatically after code edits!**
   - Compiling `.exe` binaries takes 3–5 minutes and is **strictly forbidden** during routine edits.
   - Only build the installer if the user explicitly types: `"build installer"` or `"ابنِ المثبت"`.

2. **Fast Unit Verification Only (<2 seconds)**:
   - After editing a module, ONLY run the single test file relevant to that module:
     - e.g., `python -m unittest tests/test_updater.py` (finishes in ~3s).
     - e.g., `python -m unittest tests/test_stage4_srp_decomposition.py` (finishes in 0.01s).
   - Do NOT run the full test suite after small edits unless requested.

3. **Strict Single Responsibility Principle (<550 lines per file)**:
   - Every file in `src/faqih_downloader/` must remain under **550 physical lines**.
   - If adding logic causes a file to approach 550 lines, decompose it into a specialized mixin or helper module.

4. **Zero-Rebuild Core Hot-Patch Workflow**:
   - Core application edits do NOT require rebuilding `FaqihDownloader.exe`.
   - For local development: Set `SD_DEV_SRC` or run `FaqihDownloader.exe` adjacent to `src/` to load code directly.
   - For remote distribution: Run `python -c "from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')"` to produce a ~120 KB hot-patch in <0.5 seconds.

5. **Architecture Synchronization**:
   - Whenever a file, class, or method is added, deleted, or moved, execute:
     ```bash
     python scripts/update_arch_map.py
     ```
     to ensure `GEMINI.md` and `AGENTS.md` remain 100% synchronized.

---

## 2. 🏛️ Class Inheritance & Connection Graph

### A. ModernFramelessGUI Mixin Inheritance Hierarchy
`ModernFramelessGUI` in `src/faqih_downloader/ui/main_window.py` is composed of 22 specialized mixins:

```text
ModernFramelessGUI (tk.Tk root)
├── BrowserSettingsModalMixin (ui/modals/browser_settings_modal.py)
│   └── BrowserControllerMixin (ui/controllers/browser_controller.py)
├── HistoryPanelMixin (ui/panels/history_panel.py)
├── ChunksPanelMixin (ui/panels/chunks_panel.py)
│   └── MetricsPanelMixin (ui/panels/metrics_panel.py)
├── InputsPanelMixin (ui/panels/inputs_panel.py)
│   └── ControlsPanelMixin (ui/panels/controls_panel.py)
├── ClipboardControllerMixin (ui/controllers/clipboard_controller.py)
├── UpdateControllerMixin (ui/controllers/update_controller.py)
│   └── ToastControllerMixin (ui/controllers/toast_controller.py)
├── DownloadControllerMixin (ui/controllers/download_controller.py)
│   └── MediaDownloadControllerMixin (ui/controllers/media_download_controller.py)
│       ├── YouTubeDownloadControllerMixin (ui/controllers/youtube_download_controller.py)
│       ├── BatchDownloadControllerMixin (ui/controllers/batch_download_controller.py)
│       └── LinkRefreshControllerMixin (ui/controllers/link_refresh_controller.py)
├── SettingsControllerMixin (ui/controllers/settings_controller.py)
│   ├── LocaleControllerMixin (ui/controllers/locale_controller.py)
│   └── SpeedLimiterControllerMixin (ui/controllers/speed_limiter_controller.py)
└── WindowChromeMixin (ui/controllers/window_controller.py)
    ├── ThemeControllerMixin (ui/controllers/theme_controller.py)
    ├── DispatchControllerMixin (ui/controllers/dispatch_controller.py)
    └── WindowLifecycleMixin (ui/controllers/lifecycle_controller.py)
        └── DialogControllerMixin (ui/controllers/dialog_controller.py)
```

### B. TurboDownloadEngine & YouTubeResolver Hierarchy

```text
EngineResumerMixin (core/engine_resumer.py)
└── EngineWorkersMixin (core/engine_workers.py)
    └── TurboDownloadEngine (core/engine.py) + EnginePersistenceMixin (core/engine_persistence.py)

YouTubeFormatBuilderMixin (services/youtube_format_builder.py)
└── YouTubeResolver (services/youtube_service.py) -> alias MediaResolver
```

### C. Data & Event Flow Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Browser Extension (Chrome / Edge / Brave / Opera)           │
└──────────────┬──────────────────────────────┬───────────────┘
               │ (stdio length-prefixed)      │ (HTTP POST port 9654)
               ▼                              ▼
  services/browser/native_host.py   services/browser/bridge_server.py
               │                              │
               └──────────────┬───────────────┘
                              ▼
              ui/controllers/browser_controller.py
                              │ (dispatch_to_main_thread)
                              ▼
              ui/controllers/download_controller.py
                     │                     │
         [Media / YouTube URL]        [Direct File URL]
                     ▼                     ▼
          services/youtube_service.py     core/engine.py
          (MediaResolver / yt-dlp)       (TurboDownloadEngine)
                     │                     │
                     ▼                     │
          core/stream_coordinator.py       │
          (FFmpeg Audio+Video Merge)       │
                     │                     │
                     └──────────┬──────────┘
                                ▼
               Real-time UI Event Dispatchers:
               - ui/panels/metrics_panel.py (Speed, Size, ETA, Threads)
               - ui/panels/chunks_panel.py (Visual Segment Map)
               - ui/panels/history_panel.py (Persistent Record)
               - ui/system_tray.py (Status tooltip & toasts)
```

---

## 3. 📂 Complete File-by-File Inventory & Responsibility Table

| File Path | Lines | Responsibility | Key Classes / Functions | When to Edit |
|:---|:---:|:---|:---|:---|
| `src/faqih_downloader/__init__.py` | 112 | Package initialization and unified namespace re-exports for the core application. | `_SmartDownloadAliasLoader`, `_SmartDownloadAliasFinder`, `__getattr__()`, `__dir__()` | Edit when exposing new subpackages or top-level public APIs. |
| `src/faqih_downloader/__main__.py` | 76 | Package CLI entry point and CLI dispatcher for python -m faqih_downloader. | — | Edit when modifying CLI execution arguments or package launch hooks. |
| `src/faqih_downloader/config.py` | 308 | Configuration constants, path resolvers, and settings file I/O with caching. | `get_resource_path()`, `is_test_environment()`, `get_config_dir()` | Edit when modifying app constants, version, default settings, or storage directories. |
| `src/faqih_downloader/i18n.py` | 18 | Backward-compatible i18n import shim redirecting to locales.i18n. | — | Edit if re-exporting additional translation functions. |
| `src/faqih_downloader/main.py` | 25 | Main runtime GUI entry point initializing Tkinter and launching ModernFramelessGUI. | — | Edit when altering CLI argument parsing at launch or main window instantiation. |
| `src/faqih_downloader/core/__init__.py` | 32 | Re-exports core download engine, chunking, and candidate resolution components. | — | Edit when adding new core download engine modules. |
| `src/faqih_downloader/core/candidate_extractor.py` | 386 | HTML link extraction using regex patterns and HTML link candidate parsers. | `_HtmlCandidateExtractor`, `resolve_all_download_candidates()` | Edit when updating candidate download link parsing patterns from HTML documents. |
| `src/faqih_downloader/core/chunk.py` | 69 | DownloadChunk data class, per-chunk thread state, and permissive SSL context helper. | `DownloadChunk`, `get_permissive_ssl_context()` | Edit when changing per-chunk data structures or SSL verification policies. |
| `src/faqih_downloader/core/engine.py` | 545 | TurboDownloadEngine coordinating multi-threaded chunked downloads and rate limiting. | `TurboDownloadEngine` | Edit when altering download orchestration, speed monitoring, or thread lifecycle. |
| `src/faqih_downloader/core/engine_persistence.py` | 306 | State persistence mixin saving and resuming partial download progress via .sd_parts. | `EnginePersistenceMixin` | Edit when changing chunk serialization or resume manifest structure. |
| `src/faqih_downloader/core/engine_resumer.py` | 122 | Engine resumer mixin validating server HTTP range support and multi-chunk compatibility. | `EngineResumerMixin` | Edit when modifying HTTP range probe logic or server capability checks. |
| `src/faqih_downloader/core/engine_workers.py` | 392 | Engine worker pool mixin managing download streams and dynamic midpoint splitting. | `EngineWorkersMixin` | Edit when modifying parallel worker thread loops or dynamic chunk splitting rules. |
| `src/faqih_downloader/core/history.py` | 308 | Persistent download history manager tracking completed and active download records. | `DownloadHistoryManager` | Edit when modifying history record schemas or history storage format. |
| `src/faqih_downloader/core/html_resolver.py` | 543 | Resolves real download candidates from web pages and validates link refreshes. | `_HtmlLinkCandidateParser`, `clear_probe_cache()`, `resolve_real_download_url()`, `validate_refresh_url()` | Edit when improving download candidate probing or link refresh validation. |
| `src/faqih_downloader/core/rate_limiter.py` | 78 | High-precision TokenBucketRateLimiter enforcing download bandwidth throttling. | `TokenBucketRateLimiter` | Edit when tuning speed limiter algorithms or bucket token replenishment. |
| `src/faqih_downloader/core/stream_coordinator.py` | 538 | StreamDownloadCoordinator managing streaming media downloads and FFmpeg audio/video merges. | `StreamDownloadCoordinator` | Edit when altering streaming downloads or post-processing merging steps. |
| `src/faqih_downloader/installer/__init__.py` | 87 | Installer package re-exports for setup wizard and ops. | — | Edit when changing public installer API interfaces. |
| `src/faqih_downloader/installer/installer_gui.py` | 363 | Modern themed Tkinter wizard UI for installing Smart Download. | `InstallerGUI` | Edit when altering installer wizard steps, styling, or setup progress display. |
| `src/faqih_downloader/installer/installer_migration.py` | 270 | Automatic migration module for Faqih Downloader (FD) v2.0.2. | `terminate_all_instances()`, `migrate_legacy_installations()`, `extract_payload_lzma_archive()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/installer_ops.py` | 543 | File deployment, shortcut creation, and payload extraction for Windows installation. | `get_default_install_dir()`, `get_desktop_dir()`, `get_start_menu_programs_dir()` | Edit when modifying installation payload extraction or uninstaller creation. |
| `src/faqih_downloader/installer/installer_registry.py` | 402 | Windows Registry manipulation for Add/Remove Programs and startup entries. | `get_startup_dir()`, `enable_high_dpi_awareness()`, `create_windows_shortcut()` | Edit when changing registry keys for uninstallers or file associations. |
| `src/faqih_downloader/installer/uninstaller_runner.py` | 173 | CLI and GUI uninstallation dispatcher for Smart Download (SD). | `handle_uninstall_cli()` | Edit when modifying this module's features. |
| `src/faqih_downloader/locales/__init__.py` | 15 | Locales package re-exports. | — | Edit when modifying locales package exports. |
| `src/faqih_downloader/locales/ar.json` | 364 | Complete Arabic application translations and right-to-left localized string dictionary. | — | Edit when adding or updating Arabic translation strings. |
| `src/faqih_downloader/locales/en.json` | 364 | Complete English application translations and UI text string dictionary. | — | Edit when adding or updating English translation strings. |
| `src/faqih_downloader/locales/i18n.py` | 144 | Thread-safe LocalizationManager singleton enabling dynamic language toggles. | `LocalizationManager`, `_load_locale()`, `tr()`, `get_current_language()` | Edit when modifying translation loading or language notification callbacks. |
| `src/faqih_downloader/services/__init__.py` | 209 | Services package namespace re-exports. | — | Edit when exposing new background or platform service modules. |
| `src/faqih_downloader/services/core_patch_updater.py` | 548 | OTA hot-patch packager, atomic updater, and dynamic core loader (zero-rebuild workflow). | `_ExternalCoreFinder`, `CoreHotPatchUpdater`, `get_core_plugin_dir()`, `is_version_ge()`, `build_core_patch_zip()` | Edit when modifying core patch packaging, plugin extraction, or dev source overriding. |
| `src/faqih_downloader/services/media_env_helpers.py` | 335 | media_env_helpers.py: System environment, FFmpeg binary detection, cookie browser discovery, | `detect_installed_cookie_browsers()`, `is_ytdlp_available()`, `get_ytdlp_version()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_extractor.py` | 93 | Media extractor service providing lazy loading and background warmup for yt_dlp. | `warmup_yt_dlp_background()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview_stream_bridge.py` | 531 | Built-In In-Memory Preview & Control Bridge HTTP server and web API routing. | `PreviewSession`, `PreviewBridgeRequestHandler`, `start_preview_bridge()`, `get_preview_bridge_port()`, `register_preview_session()` | Edit when modifying in-app preview HTTP bridge or web player controls. |
| `src/faqih_downloader/services/preview_stream_proxy.py` | 233 | Streaming media proxy and VTT subtitle compiler for real-time video previewing. | `resolve_preview_video_target()`, `resolve_preview_audio_target()`, `stream_upstream_media()` | Edit when changing upstream byte-range streaming proxy or VTT subtitle generation. |
| `src/faqih_downloader/services/single_instance.py` | 176 | Single application instance enforcement using Windows named mutex or loopback socket. | `acquire_single_instance_mutex()`, `is_single_instance_mutex_held()`, `release_single_instance_mutex()` | Edit when altering inter-instance signaling or command line forwarding. |
| `src/faqih_downloader/services/startup_service.py` | 536 | Zero-elevation Windows auto-start via Run key, Task Scheduler, and Startup folder. | `get_installed_exe_path()`, `get_startup_folder()`, `get_startup_command()` | Edit when altering Windows background startup mechanisms or startup entry checks. |
| `src/faqih_downloader/services/subtitle_downloader.py` | 488 | Subtitle downloading, VTT/XML/JSON parsing, GTX translation, and SRT persistence. | `convert_vtt_to_srt()`, `download_subtitle_as_srt()` | Edit when modifying subtitle fetching, timedtext parsing, or auto-translation fallbacks. |
| `src/faqih_downloader/services/subtitle_processor.py` | 531 | Subtitle processing, VTT-to-SRT conversion, FFmpeg soft-muxing, and frame burn-in delivery modes. | `run_cancellable_ffmpeg()`, `strip_burn_tag_from_filename()`, `embed_subtitle_into_mp4()` | Edit when modifying subtitle delivery modes (srt_only, soft_embed, hard_burn) or FFmpeg subtitle embedding. |
| `src/faqih_downloader/services/subtitle_style_engine.py` | 253 | Subtitle formatting, cue deduplication, libass Arabic text sanitization, and ASS style generator. | `format_ass_timestamp()`, `parse_srt_timestamp_to_seconds()`, `normalize_and_dedupe_cues()` | Edit when modifying subtitle styles, cue rollup deduplication, or libass Arabic text formatting. |
| `src/faqih_downloader/services/updater_service.py` | 527 | Application auto-update manager querying GitHub Releases and launching upgrade installers. | `AppAutoUpdater`, `get_app_data_dir()`, `get_ytdlp_plugin_dir()`, `parse_version()` | Edit when modifying GitHub release querying or update downloading mechanisms. |
| `src/faqih_downloader/services/youtube_format_builder.py` | 519 | Formats video resolution options, audio bitrates, and file size estimates from metadata. | `YouTubeFormatBuilderMixin` | Edit when modifying YouTube/social media format extraction or presentation. |
| `src/faqih_downloader/services/youtube_models.py` | 371 | Data classes and URL regex patterns for YouTube and social media platforms. | `VideoFormatOption`, `YouTubeStreamInfo`, `is_youtube_url()`, `is_social_media_url()`, `is_ytdlp_extractor_supported()` | Edit when updating social media domain patterns or stream metadata models. |
| `src/faqih_downloader/services/youtube_resolver.py` | 30 | Backward-compatibility alias re-exporting YouTube and media resolver interfaces. | — | Edit if re-exporting new streaming resolver functions. |
| `src/faqih_downloader/services/youtube_service.py` | 543 | High-level YouTubeResolver and MediaResolver coordinating yt-dlp and FFmpeg. | `YouTubeResolver` | Edit when changing media stream extraction, cookie passing, or FFmpeg merging. |
| `src/faqih_downloader/services/youtube_tracks.py` | 343 | YouTube audio dubbing and subtitle tracks extraction, language mapping, and UI track selectors. | `extract_audio_tracks()`, `extract_subtitle_tracks()`, `build_audio_subtitle_row()` | Edit when modifying audio dubbing languages, subtitle tracks parsing, or quality modal track selectors. |
| `src/faqih_downloader/services/ytdlp_updater.py` | 529 | YtDlpAutoUpdater managing dynamic in-process yt-dlp package updates in %APPDATA%. | `_ExternalYtDlpFinder`, `YtDlpAutoUpdater` | Edit when changing yt-dlp PyPI/GitHub download logic or sys.meta_path finder hooks. |
| `src/faqih_downloader/services/browser/__init__.py` | 62 | Browser integration package exports. | — | Edit when modifying browser service exports. |
| `src/faqih_downloader/services/browser/bridge_server.py` | 380 | Local HTTP bridge server receiving intercepted links from browser extensions. | `ThreadedHTTPServer`, `BrowserBridgeHandler`, `BrowserBridgeServer` | Edit when altering HTTP endpoints or ports for extension communication. |
| `src/faqih_downloader/services/browser/host_manifest.py` | 260 | Generates native messaging host manifest JSON files for Chrome and Edge. | `compute_unpacked_extension_id()`, `get_project_root()`, `get_default_extension_origins()` | Edit when updating extension IDs or native messaging manifest schemas. |
| `src/faqih_downloader/services/browser/native_host.py` | 211 | Native messaging host stdio protocol handler reading 32-bit length-prefixed messages. | `get_binary_stdin()`, `get_binary_stdout()`, `read_message()` | Edit when modifying browser extension stdio communication. |
| `src/faqih_downloader/services/browser/registry.py` | 540 | Windows Registry manager configuring native messaging host entries for Chrome/Edge. | `register_browser_extensions()`, `unregister_browser_extensions()`, `is_extension_registered()` | Edit when changing registry paths or browser integration verification logic. |
| `src/faqih_downloader/ui/__init__.py` | 45 | UI package exports. | — | Edit when exposing new UI components or windows. |
| `src/faqih_downloader/ui/main_window.py` | 541 | ModernFramelessGUI main application window aggregating all panel and controller mixins. | `ModernFramelessGUI`, `main()` | Edit when adding or removing window-level mixins or altering root layout. |
| `src/faqih_downloader/ui/system_tray.py` | 254 | Windows system tray integration (pystray) with minimize/restore and context menus. | `SystemTrayManager` | Edit when modifying system tray icon behavior or menu options. |
| `src/faqih_downloader/ui/components/__init__.py` | 4 | Reusable UI components package exports. | — | Edit when exposing new UI components. |
| `src/faqih_downloader/ui/components/arc_spinner.py` | 136 | ArcSpinnerCanvas: Circular glowing arc spinner widget for parsing / pending cards in Smart Download (SD). | `ArcSpinnerCanvas` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/base_modal.py` | 333 | SafeModalDialog: non-blocking frameless themed modal dialog base class. | `SafeModalDialog` | Edit when modifying modal dialog styling, backdrop, or grab behavior. |
| `src/faqih_downloader/ui/components/led_matrix.py` | 173 | LedEqualizerMatrix: 16-channel x 7-row LED Equalizer Spectrum Matrix widget for Smart Download (SD). | `LedEqualizerMatrix` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/tooltip.py` | 104 | Hover tooltip widget providing contextual explanations for buttons and controls. | `ToolTip` | Edit when changing tooltip styling, delay timings, or positioning. |
| `src/faqih_downloader/ui/components/top_bar.py` | 399 | TopHeaderBarMixin: Unified Top Header Bar implementation for Smart Download (SD) v2.0.2. | `TopHeaderBarMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/waveform_visualizer.py` | 100 | WaveformVisualizerCanvas: Symmetrical audio waveform visualizer for completed audio cards in Smart Download (SD). | `WaveformVisualizerCanvas` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/__init__.py` | 41 | Controllers package exports. | — | Edit when adding new controller mixins. |
| `src/faqih_downloader/ui/controllers/batch_download_controller.py` | 83 | BatchDownloadControllerMixin managing multiple download candidates selection and queueing. | `BatchDownloadControllerMixin` | Edit when modifying batch link selection or sequential download triggers. |
| `src/faqih_downloader/ui/controllers/browser_controller.py` | 143 | BrowserControllerMixin handling background extension registration and intercepted downloads. | `BrowserControllerMixin` | Edit when modifying intercepted browser link handling in the GUI. |
| `src/faqih_downloader/ui/controllers/clipboard_controller.py` | 305 | ClipboardControllerMixin sniffing clipboard for valid download and media URLs. | `ClipboardControllerMixin`, `get_url_sniffer_platform_key()` | Edit when modifying clipboard polling intervals, URL regexes, or sniffing logic. |
| `src/faqih_downloader/ui/controllers/clipboard_dialog_mixin.py` | 323 | clipboard_dialog_mixin.py: Clipboard download confirmation dialog, URL dispatching, | `ClipboardDialogMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/dialog_controller.py` | 199 | DialogControllerMixin providing thread-safe non-blocking modal dialogs. | `DialogControllerMixin` | Edit when modifying safe error, warning, or confirmation dialog dispatching. |
| `src/faqih_downloader/ui/controllers/dispatch_controller.py` | 71 | DispatchControllerMixin dispatching background thread tasks safely to Tkinter event loop. | `DispatchControllerMixin` | Edit when changing thread synchronization or GUI queue processing. |
| `src/faqih_downloader/ui/controllers/download_callbacks_mixin.py` | 274 | download_callbacks_mixin.py: Engine progress, chunk visualization, GUI periodic tick, | `DownloadCallbacksMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/download_controller.py` | 342 | DownloadControllerMixin coordinating download start, engine creation, and queue execution. | `DownloadControllerMixin` | Edit when modifying download trigger flow or engine callback wiring. |
| `src/faqih_downloader/ui/controllers/lifecycle_controller.py` | 316 | WindowLifecycleMixin managing resource cleanup, tray minimization, and clean exit. | `WindowLifecycleMixin` | Edit when modifying window close actions, thread cleanup, or tray exit. |
| `src/faqih_downloader/ui/controllers/link_refresh_controller.py` | 97 | LinkRefreshControllerMixin handling expired download link resumption and URL substitution. | `LinkRefreshControllerMixin` | Edit when altering expired link substitution or refresh dialog triggers. |
| `src/faqih_downloader/ui/controllers/locale_controller.py` | 238 | LocaleControllerMixin coordinating dynamic UI text re-translation upon language switch. | `LocaleControllerMixin` | Edit when adding dynamic language switch observers or RTL layout adjustments. |
| `src/faqih_downloader/ui/controllers/media_download_controller.py` | 23 | MediaDownloadControllerMixin composite mixin aggregating YouTube, batch, and refresh. | `MediaDownloadControllerMixin` | Edit when altering composite media controller inheritance. |
| `src/faqih_downloader/ui/controllers/settings_controller.py` | 335 | SettingsControllerMixin managing user preferences, cookies, and auto-categorization. | `SettingsControllerMixin` | Edit when adding new user preference toggles or cookies browser selection. |
| `src/faqih_downloader/ui/controllers/speed_limiter_controller.py` | 179 | SpeedLimiterControllerMixin managing speed presets, slider events, and rate limits. | `SpeedLimiterControllerMixin` | Edit when modifying speed limiter presets or live slider adjustment handlers. |
| `src/faqih_downloader/ui/controllers/theme_controller.py` | 218 | ThemeControllerMixin configuring dark theme color tokens and UI styling. | `ThemeControllerMixin` | Edit when changing application colors, fonts, or styling variables. |
| `src/faqih_downloader/ui/controllers/toast_controller.py` | 200 | ToastControllerMixin presenting non-blocking corner toast notifications. | `ToastControllerMixin` | Edit when modifying startup welcome toast or notification toast animations. |
| `src/faqih_downloader/ui/controllers/update_controller.py` | 170 | UpdateControllerMixin running background checks for app and yt-dlp updates. | `UpdateControllerMixin` | Edit when changing background update check frequency or update notification dialogs. |
| `src/faqih_downloader/ui/controllers/window_controller.py` | 420 | WindowChromeMixin managing custom frameless title bar dragging and window controls. | `WindowChromeMixin` | Edit when modifying custom title bar widgets, drag handling, or window geometry. |
| `src/faqih_downloader/ui/controllers/window_resize_mixin.py` | 191 | WindowResizeMixin: 8-edge & corner resizing grips and border drag handlers for frameless window. | `WindowResizeMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/youtube_download_controller.py` | 463 | YouTubeDownloadControllerMixin analyzing streaming media formats and quality selection. | `YouTubeDownloadControllerMixin` | Edit when modifying YouTube/social media format inspection and dialog invocation. |
| `src/faqih_downloader/ui/modals/__init__.py` | 34 | Modals package exports. | — | Edit when adding new modal dialog exports. |
| `src/faqih_downloader/ui/modals/browser_settings_modal.py` | 544 | BrowserSettingsModalMixin displaying browser extension setup and diagnostic dialog. | `BrowserSettingsModalMixin` | Edit when modifying browser extension configuration instructions or diagnostic steps. |
| `src/faqih_downloader/ui/modals/candidates_modal.py` | 482 | MultipleCandidatesModal displaying detected web download candidates with filter badges. | `MultipleCandidatesModal` | Edit when modifying candidate dialog multi-selection, search, or filtering controls. |
| `src/faqih_downloader/ui/modals/confirm_modal.py` | 182 | DownloadConfirmationModal showing probed file details before starting download. | `DownloadConfirmationModal` | Edit when changing pre-download confirmation dialog layout or field editing. |
| `src/faqih_downloader/ui/modals/confirm_modal_logic.py` | 345 | Logic helper probing download candidate metadata for the confirmation modal. | `ConfirmModalLogicMixin` | Edit when modifying candidate probing threads or URL validation. |
| `src/faqih_downloader/ui/modals/confirm_modal_progress.py` | 223 | ConfirmModalProgressMixin: Live progress tracking, canvas drawing, metrics updating, and completion handling. | `ConfirmModalProgressMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/confirm_modal_widgets.py` | 278 | ConfirmModalWidgetsMixin: UI component builders for DownloadConfirmationModal. | `ConfirmModalWidgetsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/fetching_toast.py` | 387 | FetchingLinkToast displaying a loading spinner toast during link inspection. | `FetchingLinkToast` | Edit when modifying link resolving loading animation or cancel triggers. |
| `src/faqih_downloader/ui/modals/file_info_modal.py` | 348 | FileInfoModal: Detailed File & Link Information modal dialog for Faqih Downloader (FD) v2.0.2. | `FileInfoModal`, `open_file_info_modal()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview_html_builder.py` | 542 | Unified VidMate-Style HTML5 Preview & Download Settings Builder (preview_html_builder.py). | `generate_preview_html()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview_subtitle_studio.py` | 254 | Interactive in-video subtitle studio providing real-time styling, positioning toolbar, and drag-and-drop. | `get_studio_css()`, `get_studio_toolbar_html()`, `get_studio_js()` | Edit when modifying the live subtitle studio toolbar, CSS presets, or video overlay controls. |
| `src/faqih_downloader/ui/modals/quality_modal.py` | 545 | QualitySelectionModal presenting video resolutions and audio bitrates for media. | `QualitySelectionModal` | Edit when modifying media format selection dialog, badges, or treeview. |
| `src/faqih_downloader/ui/modals/quality_modal_helpers.py` | 371 | Helper functions and banner builder for QualitySelectionModal (quality_modal_helpers.py). | `attach_selected_tracks_to_option()`, `sync_modal_selection_to_staged()`, `resolve_final_dest()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality_tracks_ui.py` | 218 | quality_tracks_ui.py: UI widgets for audio tracks and subtitle options in QualitySelectionModal. | `build_audio_subtitle_row()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/refresh_modal.py` | 492 | RefreshLinkModal prompting for updated download link when a session expires. | `RefreshLinkModal` | Edit when changing expired link substitution dialog styling or URL validation. |
| `src/faqih_downloader/ui/modals/settings_modal.py` | 510 | SettingsModal: Frameless dark application settings dialog with per-platform sniffer filtering, | `SettingsModal` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings_modal_extra.py` | 299 | SettingsModalExtraMixin: Speed Limiter and Engine Log tab builders for SettingsModal in Smart Download (SD). | `SettingsModalExtraMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings_modal_tabs.py` | 408 | SettingsModalTabsMixin: Tab building logic for SettingsModal in Smart Download (SD). | `SettingsModalTabsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/toasts.py` | 10 | Re-exports toast notification classes for convenient imports. | — | Edit when exposing additional toast classes. |
| `src/faqih_downloader/ui/modals/update_modal.py` | 365 | AppUpdateModal displaying new release notes and one-click update actions. | `AppUpdateModal` | Edit when modifying application update presentation or release notes formatting. |
| `src/faqih_downloader/ui/modals/vault_restore_modal.py` | 449 | VaultRestoreModal: Selective file restoration modal dialog for Completed Vault in Smart Download (SD). | `VaultRestoreModal` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/video_preview_modal.py` | 342 | VidMate-style in-app video preview modal with live WebVTT subtitles and chromeless player. | `open_video_preview()` | Edit when modifying video preview playback, WebVTT subtitle overlay, or player window launcher. |
| `src/faqih_downloader/ui/modals/welcome_toast.py` | 312 | StartupWelcomeToast displaying Windows startup greeting when running minimized. | `StartupWelcomeToast` | Edit when modifying startup toast layout or click-to-restore action. |
| `src/faqih_downloader/ui/panels/__init__.py` | 18 | Panels package exports. | — | Edit when adding new panel mixin exports. |
| `src/faqih_downloader/ui/panels/chunks_panel.py` | 520 | ChunksPanelMixin rendering segmented dynamic chunk visualizer and status table. | `ChunksPanelMixin` | Edit when modifying segmented chunk canvas graphics or chunk details treeview. |
| `src/faqih_downloader/ui/panels/controls_panel.py` | 426 | ControlsPanelMixin rendering thread selector, speed limiter controls, and action buttons. | `_StateButton`, `ControlsPanelMixin` | Edit when changing start/pause/cancel action buttons or limiter controls. |
| `src/faqih_downloader/ui/panels/hidden_compat_panel.py` | 295 | HiddenCompatPanelMixin: Preserves 100% of internal widgets and variables expected by tests and controllers. | `_CompatButton`, `HiddenCompatPanelMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/history_panel.py` | 287 | HistoryPanelMixin managing download history table and right-click context menu. | `HistoryPanelMixin` | Edit when modifying history treeview columns or context menu actions. |
| `src/faqih_downloader/ui/panels/inputs_panel.py` | 190 | InputsPanelMixin rendering URL and destination inputs with auto-categorization button. | `InputsPanelMixin` | Edit when modifying URL entry, destination browse button, or auto-cat toggle. |
| `src/faqih_downloader/ui/panels/kanban_active_mixin.py` | 228 | KanbanActiveColumnMixin: Column 2 (Active Turbo Streams) management for Smart Download (SD). | `KanbanActiveColumnMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_card_graphics.py` | 218 | kanban_card_graphics.py: Thumbnail extraction, icon drawing, and progress bar graphics | `draw_neon_progress_bar()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_cards.py` | 366 | Kanban Card Widgets and Rounded Glass Builders for Smart Download (SD) v2.0.2. | `create_empty_state()`, `build_queued_card()`, `build_vault_card()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_panel.py` | 336 | KanbanPanelMixin: 3-Column dynamic pipeline workspace for Smart Download (SD) v2.0.2. | `KanbanPanelMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_staged_helpers.py` | 307 | kanban_staged_helpers.py: Staged Link Card builder, context menu, and URL probing | `show_staged_context_menu()`, `build_staged_link_card()`, `render_col1_staged_cards()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_staged_prober.py` | 387 | kanban_staged_prober.py: Staged URL probers and download launch workers | `stage_media_option_in_col1()`, `probe_and_stage_pasted_url()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_vault_helpers.py` | 360 | Completed Vault helpers: filtering pills, context menus, and pagination controls for Smart Download (SD). | `get_entry_category()`, `filter_vault_entries()`, `build_vault_filter_pills()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_vault_ops.py` | 222 | kanban_vault_ops.py: Completed Vault filesystem operations, disk scanning, | `clear_completed_vault_entries()`, `scan_unregistered_disk_files()`, `restore_vault_entries_from_disk()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_options_actions.py` | 342 | MediaOptionsActionsMixin: Actions, modal triggers, preview handlers, and download starters | `MediaOptionsActionsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_options_bar.py` | 390 | MediaOptionsBarMixin: Main-window media format, dubbing audio, and subtitle options bar. | `MediaOptionsBarMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/metrics_panel.py` | 99 | MetricsPanelMixin rendering overall progress bar and real-time metric cards. | `MetricsPanelMixin` | Edit when modifying speed, size, ETA, or thread count metric cards. |
| `src/faqih_downloader/utils/__init__.py` | 85 | Utils package exports. | `__getattr__()`, `__dir__()` | Edit when exporting new utility helpers. |
| `src/faqih_downloader/utils/archive_utils.py` | 172 | Archive auto-extraction and SHA-256 file integrity verification. | `calculate_file_integrity()`, `auto_unpack_archive()` | Edit when supporting new archive formats or hash algorithms. |
| `src/faqih_downloader/utils/clipboard.py` | 75 | Cross-platform and Win32 direct clipboard text retrieval. | `get_clipboard_text()` | Edit when improving clipboard access reliability on Windows. |
| `src/faqih_downloader/utils/dpi.py` | 83 | Windows High-DPI awareness initialization and screen work area geometry. | `enable_high_dpi_awareness()`, `get_windows_work_area()` | Edit when tuning DPI scaling factors or multi-monitor geometry detection. |
| `src/faqih_downloader/utils/file_ops.py` | 449 | File categorization into subfolders (Videos, Music, etc.) and file/folder launching. | `get_file_category_and_icon()`, `resolve_categorized_path()`, `resolve_existing_download_path()` | Edit when modifying category subfolder mappings or OS shell execute actions. |
| `src/faqih_downloader/utils/magic_detector.py` | 88 | Binary magic bytes detector determining actual file types independent of URL extensions. | `MagicBytesDetector` | Edit when adding new file signature definitions. |
| `src/faqih_downloader/utils/speed_utils.py` | 91 | Speed string parsing (e.g. '1.5 MB/s') and human-readable formatting. | `parse_speed_limit()`, `format_speed()` | Edit when updating speed parsing regexes or unit formats. |
| `src/faqih_downloader/utils/tk_helpers.py` | 397 | Tkinter resource cleanup preventing photo reference and callback memory leaks. | `animate_window_open()`, `animate_window_close()` | Edit when adding memory leak mitigations for Tkinter widgets. |
| `src/faqih_downloader/utils/url_utils.py` | 393 | URL parsing, filename derivation, and Content-Disposition header extraction. | `is_downloadable_url()`, `clean_download_filename()`, `derive_download_filename()` | Edit when improving filename derivation from complex redirect URLs. |
| `src/faqih_downloader/utils/window_effects.py` | 363 | Window effects and rounded glass Canvas styling for Smart Download (SD). | `RoundedGlassCard`, `apply_acrylic_or_mica_effect()`, `draw_rounded_rect()`, `draw_glow_border()` | Edit when modifying this module's features. |
| `faqih_downloader.py` | 461 | Main official application entry point, CLI dispatcher, and unified symbol re-exporter. | `_SmartDownloadAliasLoader`, `_SmartDownloadAliasFinder`, `_FaqihDownloaderShim` | Edit when updating top-level launch hooks, CLI flags, or application initialization. |
| `turbo_downloader.py` | 58 | Backward-compatibility root shim re-exporting all symbols from faqih_downloader. | `_TurboDownloaderCompatShim` | Edit when maintaining legacy backward-compatible import compatibility. |
| `browser_bridge.py` | 24 | Backward-compatibility root shim re-exporting BrowserBridgeServer. | — | Edit when changing browser bridge root exports. |
| `native_messaging_host.py` | 29 | Backward-compatibility root shim re-exporting native messaging host functions. | — | Edit when updating native messaging entry point. |
| `register_browser.py` | 37 | Backward-compatibility root shim for browser extension registration commands. | — | Edit when updating browser registration CLI entry point. |
| `updater.py` | 48 | Backward-compatibility root shim re-exporting AppAutoUpdater and CoreHotPatchUpdater. | — | Edit when adding top-level updater exports. |
| `youtube_resolver.py` | 65 | Backward-compatibility root shim re-exporting YouTube and media resolver interfaces. | `_YouTubeResolverShim` | Edit when updating YouTube resolver root exports. |
| `release_publisher.py` | 353 | Automated GitHub Releases publisher supporting fast zero-rebuild core patch publishing. | `log()`, `get_git_credentials()`, `api_request()` | Edit when modifying release publishing workflow or asset upload logic. |
| `build_installer.py` | 420 | Automated build script compiling PyInstaller bundles and Windows setup installer. | `clean_stale_shadow_modules()`, `verify_exe_startup()`, `clean_stale_dist_artifacts()` | Edit ONLY when user explicitly commands 'build installer' or 'ابنِ المثبت'. |
| `installer.py` | 119 | Standalone installer runner executing SmartDownload setup wizard. | `_InstallerShim`, `main()` | Edit when modifying standalone installer CLI options. |
| `tests/__init__.py` | 11 | Tests package initialization. | — | Edit when configuring test discovery fixtures. |
| `tests/conftest.py` | 81 | Module implementation for Smart Download. | `_SmartDownloadAliasLoader`, `_SmartDownloadAliasFinder` | Edit when modifying this module's features. |
| `tests/test_browser.py` | 631 | Unit tests for browser extension bridge, native host stdio, and Windows registry. | `TestBrowserBridgeServer`, `TestBrowserBridgeConcurrency`, `TestExtensionManifestAndAssets`, `TestNativeMessagingHostProtocol`, `TestBrowserRegistryIntegration`, `setUpModule()`, `tearDownModule()` | Edit when adding tests for browser integration features. |
| `tests/test_bugfixes.py` | 3735 | Automated unit and integration tests for Part 1 (Subtitle Hard-Burn fixes & GTX translation fallback) | `TestSubtitleProcessorAndGTXFallback`, `TestVideoPreviewModal`, `TestHardenedFFmpeg`, `TestPreviewStreamBridgeAndUnifiedVidMatePlayer`, `TestPart1To4CriticalBugfixes`, `TestWindowMaximizeAndTikTokDirectFixes`, `TestGeometryAndSanitizationAndTikTokDeduplication`, `TestClipboardPlatformFilteringAndSettings`, `TestMainToolbarCleanup`, `TestStartupAndWelcomeToastBugfixes` | Edit when modifying this module's features. |
| `tests/test_concurrent_redownload_and_tags.py` | 501 | Unit tests verifying concurrent re-download path uniqueness, | `TestConcurrentRedownloadAndTags` | Edit when modifying this module's features. |
| `tests/test_core_patch_updater.py` | 424 | Unit tests for CoreHotPatchUpdater, packaging, rollback, and dynamic loading. | `_MockStreamResp`, `TestCoreHotPatchAndZeroRebuildWorkflow` | Edit when testing OTA core hot-patching or zero-rebuild workflow. |
| `tests/test_dpi_and_assets.py` | 398 | Unit tests for Windows High-DPI scaling, icons, and asset resolution. | `TestDPIAndAssets`, `setUpModule()`, `tearDownModule()` | Edit when adding tests for display scaling or asset bundling. |
| `tests/test_engine_core.py` | 794 | Unit tests for TurboDownloadEngine, chunking, rate limiting, and worker pooling. | `MockServerHandler`, `TestTurboDownloader`, `TestSmartDownloadBrandingAndParts`, `setUpModule()`, `tearDownModule()` | Edit when testing download core algorithms and throttling. |
| `tests/test_engine_resume.py` | 485 | Unit tests for download pause, resume, and .sd_parts persistence. | `MockHeaderInspectHandler`, `TestEngineCustomHeaders`, `TestStreamCoordinatorIntegration`, `TestSmartDownloadPartsDirectory`, `TestHeadlessDecoupling`, `setUpModule()`, `tearDownModule()` | Edit when testing download resumption and manifest serialization. |
| `tests/test_html_candidates.py` | 825 | Unit tests for web page candidate link extraction and filtering. | `MockHtmlResolverHandler`, `TestHtmlLinkResolverAndStartupToast`, `MockMultiCandidateServer`, `TestMultipleDownloadCandidates`, `setUpModule()`, `tearDownModule()` | Edit when testing HTML candidate link discovery. |
| `tests/test_i18n.py` | 467 | Unit tests for Arabic and English translations and runtime language toggling. | `TestBilingualLocalization`, `setUpModule()`, `tearDownModule()` | Edit when adding i18n and localization test cases. |
| `tests/test_installer.py` | 1128 | Unit tests for installer file extraction, registry keys, and shortcuts. | `TestWindowsInstallerLogic`, `TestStandaloneExeBuild`, `setUpModule()`, `tearDownModule()` | Edit when testing Windows installer operations. |
| `tests/test_kanban_pipeline.py` | 285 | Comprehensive unit tests for 100% Dynamic 3-Column Kanban Pipeline in Smart Download (SD) v2.0.2: | `TestKanbanPipeline` | Edit when modifying this module's features. |
| `tests/test_main_window_actions.py` | 787 | Unit tests for main window user actions, queueing, and callbacks. | `TestClipboardNonBlockingInterception`, `TestClipboardSnifferAndUrlValidation`, `setUpModule()`, `tearDownModule()` | Edit when testing GUI button actions and download queueing. |
| `tests/test_main_window_ui.py` | 866 | Unit tests for main window UI structure, widget creation, and layout. | `TestBackgroundAndMinimizedLaunch`, `TestSystemTrayAndBackgroundMinimization`, `TestClipboardSequenceRecopying`, `TestBackgroundStartupNotificationAndTray`, `setUpModule()`, `tearDownModule()` | Edit when testing window geometry, cards, and widget hierarchies. |
| `tests/test_media_options_and_continuity.py` | 256 | Unit tests verifying Media Options Bar UI wiring and Dubbing & Subtitle continuity fixes. | `TestMediaOptionsAndContinuity` | Edit when modifying this module's features. |
| `tests/test_modals_confirm.py` | 783 | Unit tests for DownloadConfirmationModal and candidate size probing. | `TestTDMDownloadConfirmationDialog`, `TestTDMConfirmationAndStandaloneProgress`, `setUpModule()`, `tearDownModule()` | Edit when testing confirmation modal logic. |
| `tests/test_modals_other.py` | 744 | Unit tests for quality, refresh, browser settings, and toast modals. | `TestQualitySelectionModalGUI`, `TestInstantFetchingLinkToast`, `setUpModule()`, `tearDownModule()` | Edit when testing secondary modal dialogs and toasts. |
| `tests/test_rebranding_and_improvements.py` | 1878 | Unit tests verifying the 5 radical improvements and rebranding in Faqih Downloader (FD): | `TestRebrandingAndImprovements`, `TestPhase2SecurityAndHardening` | Edit when modifying this module's features. |
| `tests/test_settings_history.py` | 825 | Unit tests for settings persistence, auto-categorization, and history manager. | `TestWindowsStartupRegistryIntegration`, `TestDownloadHistoryAndCategorization`, `setUpModule()`, `tearDownModule()` | Edit when testing preferences and download history operations. |
| `tests/test_stage4_srp_decomposition.py` | 345 | Unit tests verifying strict SRP decomposition (<550 lines per file). | `TestUIControllersSRP`, `TestUIPanelsSRP`, `TestCoreAndUtilsSRP` | Edit when adding new decomposed modules to verify strict line limits. |
| `tests/test_stage6_performance.py` | 263 | Unit test suite verifying Stage 6: Ultra-Performance, Low-Latency & High-Throughput Optimization. | `TestStage6PerformanceOptimizations` | Edit when modifying this module's features. |
| `tests/test_stage7_security_stress.py` | 470 | Unit and stress test suite verifying Stage 7: Enterprise Security Hardening & Heavy Stress Resilience. | `TestZipTarSlipSecurity`, `TestBridgeServerOriginCSRFSecurity`, `TestFilenameSanitizationAndWindowsReserved`, `TestFileRedirectSchemeSecurity`, `TestStressAndHeavyLoadResilience` | Edit when modifying this module's features. |
| `tests/test_stage8_2_live_ux.py` | 415 | Live Tkinter GUI Verification for Stage 8.2 UX & Window Lifecycle Overhaul. | `TestStage82LiveUX` | Edit when modifying this module's features. |
| `tests/test_stage8_dubbing_subtitles.py` | 735 | Unit tests for Stage 8: YouTube Multi-Language Audio Dubbing & Subtitle Selection/Embedding. | `DummyBuilder`, `TestYouTubeTracks` | Edit when modifying this module's features. |
| `tests/test_stage9_1_and_10_e2e.py` | 260 | Comprehensive Unit & E2E Verification for Smart Download Stages 9.1 & 10. | `TestStage9_1_And_10_Verification` | Edit when modifying this module's features. |
| `tests/test_stage9_2_stabilization.py` | 326 | Comprehensive verification test suite for Stage 9.2: | `TestStage9_2Stabilization` | Edit when modifying this module's features. |
| `tests/test_stage9_runtime_fixes.py` | 597 | Unit and integration tests for Stage 9: Comprehensive Runtime & UX Overhaul. | `TestSubtitleConversionStage9`, `TestBurnSubtitleEncodingAndPaths`, `TestStreamCoordinatorMultiThreading`, `DummyMockApp`, `TestOpenInMainAppAndMediaOptionsBar`, `TestFetchingToastSafety`, `TestSubtitleAutoSelection`, `TestHistoryRedownloadQuality` | Edit when modifying this module's features. |
| `tests/test_stream_and_staged_fixes.py` | 455 | Unit tests for StreamCoordinator dubbing fault tolerance, | `TestStreamCoordinatorDubbingFixes`, `TestSubtitleFilenameTagAccuracy`, `TestMediaOptionsBarAndStagedCard` | Edit when modifying this module's features. |
| `tests/test_updater.py` | 562 | Unit tests for AppAutoUpdater, YtDlpAutoUpdater, and version unification. | `_MockHttpResp`, `TestVersionComparisonAndUnification`, `TestYtDlpAutoUpdater`, `TestAppAutoUpdaterAndModal` | Edit when testing app/yt-dlp auto-updates or version comparison. |
| `tests/test_url_resolver.py` | 725 | Unit tests for URL utilities, filename sanitization, and speed formatting. | `MockRefreshLinkServerHandler`, `TestRefreshExpiredLinks`, `TestSpeedFormatting`, `setUpModule()`, `tearDownModule()` | Edit when testing URL manipulation and parsing utilities. |
| `tests/test_visual_defects_fix.py` | 297 | Unit tests for visual defects fix: | `TestVisualDefectsFix` | Edit when modifying this module's features. |
| `tests/test_youtube_extract.py` | 730 | Unit tests for YouTube and social media link extraction with yt-dlp. | `TestYouTubeDetectionAndSanitization`, `TestYouTubeResolver`, `TestSocialMediaDetectionAndSanitization`, `TestSocialMediaResolverAndExtraction`, `TestVideoQualityFormatExtraction`, `setUpModule()`, `tearDownModule()` | Edit when testing social media stream resolution. |
| `tests/test_youtube_merge.py` | 831 | Unit tests for FFmpeg video + audio stream merging and format building. | `TestYouTubeSafeConcurrencyAndErrorHandling`, `TestBrowserCookiesAndMP3Extraction`, `setUpModule()`, `tearDownModule()` | Edit when testing FFmpeg post-processing operations. |

---

## 4. ⚡ Verification Commands Cheat Sheet

| Task | Command | Typical Time |
|:---|:---|:---:|
| Verify OTA Core Hot-Patch | `python -m unittest tests/test_core_patch_updater.py` | ~0.5s |
| Verify App & Yt-Dlp Updater | `python -m unittest tests/test_updater.py` | ~3.5s |
| Verify Strict SRP Line Limits (<550) | `python -m unittest tests/test_stage4_srp_decomposition.py` | ~0.01s |
| Verify Architecture Map Sync | `python scripts/update_arch_map.py --check` | ~0.15s |
| Verify YouTube Extraction | `python -m unittest tests/test_youtube_extract.py` | ~1.5s |
| Verify Engine Resume & Persistence | `python -m unittest tests/test_engine_resume.py` | ~1.2s |
| Build Core Hot-Patch (~120 KB) | `python -c "from updater import build_core_patch_zip; build_core_patch_zip('dist/FaqihDownloader-CorePatch.zip')"` | <0.5s |

*(Reminder: NEVER run PyInstaller or `build_installer.py` unless user explicitly commands: `build installer`)*
