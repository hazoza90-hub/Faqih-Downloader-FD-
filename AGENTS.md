# Faqih Downloader (FD) | فقيه التنزيلات — Persistent AI Architecture & Dependency Map

> CRITICAL RULE (DO NOT VIOLATE): NEVER run `build_installer.py` or `release_publisher.py` or upload `FaqihDownloader-Setup.exe` / release binaries to GitHub Releases automatically after code edits. Only build or upload the installer to GitHub when the user explicitly commands 'ارفع برنامج التسطيب على جيت هاب' or 'upload installer to GitHub'.

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
| `src/faqih_downloader/__main__.py` | 74 | Package CLI entry point and CLI dispatcher for python -m faqih_downloader. | — | Edit when modifying CLI execution arguments or package launch hooks. |
| `src/faqih_downloader/config.py` | 321 | Configuration constants, path resolvers, and settings file I/O with caching. | `get_resource_path()`, `is_test_environment()`, `get_config_dir()` | Edit when modifying app constants, version, default settings, or storage directories. |
| `src/faqih_downloader/i18n.py` | 18 | Backward-compatible i18n import shim redirecting to locales.i18n. | — | Edit if re-exporting additional translation functions. |
| `src/faqih_downloader/main.py` | 29 | Main runtime GUI entry point initializing Tkinter and launching ModernFramelessGUI. | `main()` | Edit when altering CLI argument parsing at launch or main window instantiation. |
| `src/faqih_downloader/core/__init__.py` | 32 | Re-exports core download engine, chunking, and candidate resolution components. | — | Edit when adding new core download engine modules. |
| `src/faqih_downloader/core/candidate_extractor.py` | 386 | HTML link extraction using regex patterns and HTML link candidate parsers. | `_HtmlCandidateExtractor`, `resolve_all_download_candidates()` | Edit when updating candidate download link parsing patterns from HTML documents. |
| `src/faqih_downloader/core/chunk.py` | 88 | DownloadChunk data class, per-chunk thread state, and permissive SSL context helper. | `DownloadChunk`, `get_permissive_ssl_context()` | Edit when changing per-chunk data structures or SSL verification policies. |
| `src/faqih_downloader/core/engine.py` | 137 | TurboDownloadEngine coordinating multi-threaded chunked downloads and rate limiting. | `TurboDownloadEngine` | Edit when altering download orchestration, speed monitoring, or thread lifecycle. |
| `src/faqih_downloader/core/engine_persistence.py` | 352 | State persistence mixin saving and resuming partial download progress via .sd_parts. | `EnginePersistenceMixin` | Edit when changing chunk serialization or resume manifest structure. |
| `src/faqih_downloader/core/engine_resumer.py` | 21 | Engine resumer mixin validating server HTTP range support and multi-chunk compatibility. | — | Edit when modifying HTTP range probe logic or server capability checks. |
| `src/faqih_downloader/core/engine_workers.py` | 32 | Engine worker pool mixin managing download streams and dynamic midpoint splitting. | — | Edit when modifying parallel worker thread loops or dynamic chunk splitting rules. |
| `src/faqih_downloader/core/history.py` | 315 | Persistent download history manager tracking completed and active download records. | `DownloadHistoryManager` | Edit when modifying history record schemas or history storage format. |
| `src/faqih_downloader/core/html_resolver.py` | 38 | Resolves real download candidates from web pages and validates link refreshes. | — | Edit when improving download candidate probing or link refresh validation. |
| `src/faqih_downloader/core/rate_limiter.py` | 78 | High-precision TokenBucketRateLimiter enforcing download bandwidth throttling. | `TokenBucketRateLimiter` | Edit when tuning speed limiter algorithms or bucket token replenishment. |
| `src/faqih_downloader/core/stream_coordinator.py` | 113 | StreamDownloadCoordinator managing streaming media downloads and FFmpeg audio/video merges. | `StreamDownloadCoordinator` | Edit when altering streaming downloads or post-processing merging steps. |
| `src/faqih_downloader/core/coordinator/__init__.py` | 25 | coordinator package: Controls, progress, engine bridge, post-hooks, lifecycle, MP3 transcoding, single-stream, dual-stream, and merger modules. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/controls.py` | 87 | controls.py: Coordinator logging, running/paused state, speed limiting, start/pause/resume/cancel/shutdown. | `CoordinatorControlsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/dual_merger.py` | 55 | dual_merger.py: Dual-stream audio completeness recovery, FFmpeg video+audio merge, and completion emission. | `merge_dual_streams()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/dual_stream.py` | 148 | dual_stream.py: Parallel dual-stream (video + audio) download execution and worker draining. | `run_dual_stream_download()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/engine_bridge.py` | 58 | engine_bridge.py: Engine instantiation, URL refresh, and active engine metadata delegation. | `CoordinatorEngineBridgeMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/lifecycle.py` | 19 | lifecycle.py: Thin composition mixin aggregating coordinator controls, progress, engine bridge, and post-hooks. | `CoordinatorLifecycleMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/mp3_transcoder.py` | 51 | mp3_transcoder.py: FFmpeg MP3 audio transcoding post-step for audio-only MP3 downloads. | `transcode_audio_to_mp3()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/post_hooks.py` | 43 | post_hooks.py: Coordinator temporary path cleanup, subtitle prefetching, and post-download clip/subtitle hooks. | `CoordinatorPostHooksMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/progress.py` | 113 | progress.py: Coordinator chunk snapshot aggregation, size estimation, and progress/stage emission. | `CoordinatorProgressMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/coordinator/single_stream.py` | 89 | single_stream.py: Progressive and single-stream download execution. | `run_single_stream_download()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/__init__.py` | 39 | Engine parts subpackage: Socket helpers, keep-alive wrapper, connection pool, | — | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/chunk_worker.py` | 505 | EngineChunkWorkerMixin: Chunk worker loops, network socket I/O, range streaming, and error aborts. | `EngineChunkWorkerMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/conn_pool.py` | 171 | EngineConnPoolMixin: HTTP(S) connection pooling, keep-alive reuse, and socket lifecycle management. | `EngineConnPoolMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/dynamic_split.py` | 53 | EngineDynamicSplitMixin: Adaptive Dynamic Midpoint Splitting Mechanism. | `EngineDynamicSplitMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/keepalive_wrapper.py` | 87 | _KeepAliveResponseWrapper: HTTPResponse wrapper for jitter-resilient read streaming and pause handling. | `_KeepAliveResponseWrapper` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/lifecycle.py` | 158 | Engine lifecycle management mixin: startup, speed control, chunk snapshots, pause, resume, cancel, and cleanup. | `EngineLifecycleMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/metrics.py` | 76 | EngineMetricsMixin: Download transfer speed calculation (EMA smoothing), ETA estimation, and progress emission. | `EngineMetricsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/prober.py` | 184 | Engine server capabilities prober mixin: HEAD/GET range probing, redirect handling, and clen extraction. | `EngineProberMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/resumer.py` | 159 | EngineResumerMixin: Download link updating, URL refresh validation, and chunk resume coordination. | `EngineResumerMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/socket_utils.py` | 56 | Socket configuration and windowed URL construction helpers. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/supervisor.py` | 159 | Engine supervisor loop mixin: chunk scheduling, worker lifecycle, dynamic splitting, and completion assembly. | `EngineSupervisorMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/engine_parts/workers.py` | 18 | EngineWorkersMixin: Composition mixin uniting chunk worker loops, dynamic splitting, | `EngineWorkersMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/__init__.py` | 31 | Resolver subpackage: Host validation, HTML candidate parsing, probe caching, | — | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/host_guard.py` | 28 | Host validation and SSRF protection helpers. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/html_parser.py` | 33 | HTML link candidate parser for extracting download hyperlinks from landing pages. | `_HtmlLinkCandidateParser` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/probe_cache.py` | 31 | In-memory cache for probed download URLs. | `clear_probe_cache()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/refresh_validator.py` | 151 | validate_refresh_url: expired-link refresh URL validation via HEAD and GET Range requests. | `validate_refresh_url()` | Edit when modifying this module's features. |
| `src/faqih_downloader/core/resolver/url_resolver.py` | 338 | resolve_real_download_url: HTTP redirect probing, HTML landing detection, and candidate resolution. | `resolve_real_download_url()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/__init__.py` | 87 | Installer package re-exports for setup wizard and ops. | — | Edit when changing public installer API interfaces. |
| `src/faqih_downloader/installer/installer_gui.py` | 363 | Modern themed Tkinter wizard UI for installing Smart Download. | `InstallerGUI` | Edit when altering installer wizard steps, styling, or setup progress display. |
| `src/faqih_downloader/installer/installer_migration.py` | 270 | Automatic migration module for Faqih Downloader (FD) v2.0.2. | `terminate_all_instances()`, `migrate_legacy_installations()`, `extract_payload_lzma_archive()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/installer_ops.py` | 89 | File deployment, shortcut creation, and payload extraction for Windows installation. | — | Edit when modifying installation payload extraction or uninstaller creation. |
| `src/faqih_downloader/installer/installer_registry.py` | 402 | Windows Registry manipulation for Add/Remove Programs and startup entries. | `get_startup_dir()`, `enable_high_dpi_awareness()`, `create_windows_shortcut()` | Edit when changing registry keys for uninstallers or file associations. |
| `src/faqih_downloader/installer/uninstaller_runner.py` | 173 | CLI and GUI uninstallation dispatcher for Smart Download (SD). | `handle_uninstall_cli()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/__init__.py` | 85 | Installer operations subpackage for Faqih Downloader: | — | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/constants.py` | 22 | Installation constants and Windows Registry keys for Faqih Downloader. | `get_default_install_dir()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/installer_flow.py` | 235 | Application installation workflow and shortcut/registry registration for Faqih Downloader. | `install_application()`, `run_silent_install()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/paths.py` | 77 | System paths, shell folders (Desktop, Start Menu, Startup), and elevation checks for Faqih Downloader. | `get_desktop_dir()`, `get_start_menu_programs_dir()`, `get_startup_dir()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/payload.py` | 91 | Installer payload file discovery and resilient file copy operations for Faqih Downloader. | `find_payload_sources()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/process_guard.py` | 45 | Running application process termination and test environment detection for Faqih Downloader installer. | `terminate_running_app()` | Edit when modifying this module's features. |
| `src/faqih_downloader/installer/ops/uninstaller_flow.py` | 160 | Application uninstallation workflow and file/registry cleanup for Faqih Downloader. | `uninstall_application()` | Edit when modifying this module's features. |
| `src/faqih_downloader/locales/__init__.py` | 15 | Locales package re-exports. | — | Edit when modifying locales package exports. |
| `src/faqih_downloader/locales/ar.json` | 375 | Complete Arabic application translations and right-to-left localized string dictionary. | — | Edit when adding or updating Arabic translation strings. |
| `src/faqih_downloader/locales/en.json` | 375 | Complete English application translations and UI text string dictionary. | — | Edit when adding or updating English translation strings. |
| `src/faqih_downloader/locales/i18n.py` | 171 | Thread-safe LocalizationManager singleton enabling dynamic language toggles. | `LocalizationManager`, `_load_locale()`, `tr()`, `get_current_language()` | Edit when modifying translation loading or language notification callbacks. |
| `src/faqih_downloader/services/__init__.py` | 209 | Services package namespace re-exports. | — | Edit when exposing new background or platform service modules. |
| `src/faqih_downloader/services/audio_and_chapters_engine.py` | 286 | Smart chapters extractor from metadata/description and studio audio booster/voice normalizer. | `build_smart_auto_chapters()`, `extract_video_chapters()`, `get_studio_audio_boost_filter()` | Edit when modifying chapter extraction regexes or studio audio boost filters/FFmpeg processing. |
| `src/faqih_downloader/services/core_patch_updater.py` | 35 | OTA hot-patch packager, atomic updater, and dynamic core loader (zero-rebuild workflow). | — | Edit when modifying core patch packaging, plugin extraction, or dev source overriding. |
| `src/faqih_downloader/services/external_subtitle_service.py` | 278 | Independent multi-language external .SRT subtitle helpers for Faqih Downloader (FD). | `get_valid_ext_tracks()`, `get_protected_ext_langs()`, `is_protected_external_srt()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_clipper_engine.py` | 84 | Media clipper engine, subtitle shift/merge, custom cue edits, and FFmpeg trimming. | `trim_media_file()`, `process_post_download_clip_and_subtitles()`, `download_clipped_stream_direct()` | Edit when modifying video/audio clipping, cue editing, dual subtitles, or post-download trimming. |
| `src/faqih_downloader/services/media_env_helpers.py` | 32 | media_env_helpers.py: Thin backward-compatibility shim re-exporting symbols from services.media_env. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_extractor.py` | 93 | Media extractor service providing lazy loading and background warmup for yt_dlp. | `warmup_yt_dlp_background()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview_stream_bridge.py` | 54 | Built-In In-Memory Preview & Control Bridge HTTP server and web API routing. | — | Edit when modifying in-app preview HTTP bridge or web player controls. |
| `src/faqih_downloader/services/preview_stream_proxy.py` | 21 | Streaming media proxy and VTT subtitle compiler for real-time video previewing. | — | Edit when changing upstream byte-range streaming proxy or VTT subtitle generation. |
| `src/faqih_downloader/services/single_instance.py` | 176 | Single application instance enforcement using Windows named mutex or loopback socket. | `acquire_single_instance_mutex()`, `is_single_instance_mutex_held()`, `release_single_instance_mutex()` | Edit when altering inter-instance signaling or command line forwarding. |
| `src/faqih_downloader/services/startup_service.py` | 106 | Zero-elevation Windows auto-start via Run key, Task Scheduler, and Startup folder. | — | Edit when altering Windows background startup mechanisms or startup entry checks. |
| `src/faqih_downloader/services/subtitle_downloader.py` | 93 | Subtitle downloading, VTT/XML/JSON parsing, GTX translation, and SRT persistence. | `download_subtitle_as_srt()` | Edit when modifying subtitle fetching, timedtext parsing, or auto-translation fallbacks. |
| `src/faqih_downloader/services/subtitle_processor.py` | 181 | Subtitle processing, VTT-to-SRT conversion, FFmpeg soft-muxing, and frame burn-in delivery modes. | `run_cancellable_ffmpeg()`, `embed_subtitle_into_mp4()`, `burn_subtitle_into_video()` | Edit when modifying subtitle delivery modes (srt_only, soft_embed, hard_burn) or FFmpeg subtitle embedding. |
| `src/faqih_downloader/services/subtitle_style_engine.py` | 354 | Subtitle formatting, cue deduplication, libass Arabic text sanitization, and ASS style generator. | `format_ass_timestamp()`, `parse_srt_timestamp_to_seconds()`, `normalize_and_dedupe_cues()` | Edit when modifying subtitle styles, cue rollup deduplication, or libass Arabic text formatting. |
| `src/faqih_downloader/services/updater_service.py` | 66 | Application auto-update manager querying GitHub Releases and launching upgrade installers. | — | Edit when modifying GitHub release querying or update downloading mechanisms. |
| `src/faqih_downloader/services/youtube_format_builder.py` | 33 | Formats video resolution options, audio bitrates, and file size estimates from metadata. | — | Edit when modifying YouTube/social media format extraction or presentation. |
| `src/faqih_downloader/services/youtube_models.py` | 73 | Data classes and URL regex patterns for YouTube and social media platforms. | — | Edit when updating social media domain patterns or stream metadata models. |
| `src/faqih_downloader/services/youtube_resolver.py` | 30 | Backward-compatibility alias re-exporting YouTube and media resolver interfaces. | — | Edit if re-exporting new streaming resolver functions. |
| `src/faqih_downloader/services/youtube_service.py` | 72 | High-level YouTubeResolver and MediaResolver coordinating yt-dlp and FFmpeg. | — | Edit when changing media stream extraction, cookie passing, or FFmpeg merging. |
| `src/faqih_downloader/services/youtube_tracks.py` | 403 | YouTube audio dubbing and subtitle tracks extraction, language mapping, and UI track selectors. | `extract_audio_tracks()`, `extract_subtitle_tracks()`, `build_audio_subtitle_row()` | Edit when modifying audio dubbing languages, subtitle tracks parsing, or quality modal track selectors. |
| `src/faqih_downloader/services/ytdlp_updater.py` | 38 | YtDlpAutoUpdater managing dynamic in-process yt-dlp package updates in %APPDATA%. | — | Edit when changing yt-dlp PyPI/GitHub download logic or sys.meta_path finder hooks. |
| `src/faqih_downloader/services/browser/__init__.py` | 62 | Browser integration package exports. | — | Edit when modifying browser service exports. |
| `src/faqih_downloader/services/browser/bridge_server.py` | 380 | Local HTTP bridge server receiving intercepted links from browser extensions. | `ThreadedHTTPServer`, `BrowserBridgeHandler`, `BrowserBridgeServer` | Edit when altering HTTP endpoints or ports for extension communication. |
| `src/faqih_downloader/services/browser/browser_detector.py` | 236 | Idempotent, self-healing browser integration detector and registration CLI for Faqih Downloader. | `check_and_register_browser()`, `main()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/browser/extension_registry.py` | 196 | Browser WebExtension registration and unregistration in Windows Registry for Chrome and Edge. | `register_browser_extensions()`, `unregister_browser_extensions()`, `is_extension_registered()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/browser/host_manifest.py` | 260 | Generates native messaging host manifest JSON files for Chrome and Edge. | `compute_unpacked_extension_id()`, `get_project_root()`, `get_default_extension_origins()` | Edit when updating extension IDs or native messaging manifest schemas. |
| `src/faqih_downloader/services/browser/host_registry.py` | 269 | Native messaging host registration and status verification in Windows Registry for Chrome and Edge. | `register_native_host()`, `unregister_native_host()`, `is_registered()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/browser/native_host.py` | 211 | Native messaging host stdio protocol handler reading 32-bit length-prefixed messages. | `get_binary_stdin()`, `get_binary_stdout()`, `read_message()` | Edit when modifying browser extension stdio communication. |
| `src/faqih_downloader/services/browser/registry.py` | 118 | Windows Registry manager configuring native messaging host entries for Chrome/Edge. | — | Edit when changing registry paths or browser integration verification logic. |
| `src/faqih_downloader/services/clipper/__init__.py` | 42 | clipper package: Subtitle cue ops, clip state sync, media trimming, post-download pipeline, process control, and direct clip downloading. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/cue_ops.py` | 117 | cue_ops.py: Subtitle cue editing, clip time-filtering/shifting, bilingual cue merging, clean track cloning, and SRT export. | `apply_custom_cue_edits()`, `clone_clean_subtitle_track()`, `filter_and_shift_cues_for_clip()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/direct_downloader.py` | 218 | direct_downloader.py: Direct FFmpeg HTTP-range clipped stream downloading and progress tracking. | `download_clipped_stream_direct()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/post_pipeline.py` | 127 | post_pipeline.py: Post-download subtitle preparation and clip/subtitle/audio-boost orchestration. | `prepare_post_download_subtitles()`, `process_post_download_clip_and_subtitles()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/process_control.py` | 31 | process_control.py: OS-level subprocess suspend and resume control. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/state_sync.py` | 86 | state_sync.py: Preview/clipper state synchronization onto stream_info and clipped byte estimation. | `sync_clipper_state_from_body()`, `enrich_stream_info_with_clip()`, `estimate_clip_total_bytes()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/clipper/trimmer.py` | 79 | trimmer.py: Local FFmpeg media file trimming in-place with duration verification. | `trim_media_file()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/__init__.py` | 38 | media_env package: System media environment, browser cookies, yt-dlp, FFmpeg, and audio recovery helpers. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/audio_recovery.py` | 122 | audio_recovery.py: Audio stream completeness validation and yt-dlp fallback recovery. | `ensure_complete_audio_file()`, `recover_audio_stream_fallback()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/browser_cookies.py` | 86 | browser_cookies.py: Browser cookie installation detection and yt-dlp cookie source resolution. | `detect_installed_cookie_browsers()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/ffmpeg_probe.py` | 169 | ffmpeg_probe.py: FFmpeg binary discovery and media duration probing. | `find_ffmpeg_bin()`, `has_ffmpeg()`, `probe_media_file_duration()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/ffmpeg_runner.py` | 203 | ffmpeg_runner.py: Executes FFmpeg with live progress reporting, ETA calculation, and cancellation. | `run_ffmpeg_with_progress()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/media_env/ytdlp_env.py` | 45 | ytdlp_env.py: yt-dlp runtime availability checking, version inspection, and plugin update trigger. | `is_ytdlp_available()`, `get_ytdlp_version()`, `update_ytdlp_engine()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/__init__.py` | 59 | preview package: In-memory preview bridge, HTTP stream proxy, session store, VTT compiler, and API handlers. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/api_actions.py` | 101 | api_actions.py: Preview HTTP API mixin handling download, open-in-main, and cancel actions. | `PreviewActionApiMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/api_files.py` | 103 | api_files.py: Preview HTTP API mixin for live filename tagging and native save-file browsing. | `PreviewFileApiMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/api_state.py` | 106 | api_state.py: Preview HTTP API mixin synchronizing live web player selections back to Tkinter modal. | `PreviewStateApiMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/bridge_server.py` | 47 | bridge_server.py: Singleton ephemeral loopback HTTP server lifecycle for the preview bridge. | `start_preview_bridge()`, `get_preview_bridge_port()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/http_handler.py` | 177 | http_handler.py: HTTP request handler routing player HTML, media streams, subtitles, and JSON APIs. | `PreviewBridgeRequestHandler` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/local_proxy.py` | 96 | local_proxy.py: Local loopback HTTP proxy bridge for windowed high-speed media streaming. | `PreviewStreamBridge` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/origin_guard.py` | 35 | origin_guard.py: Safe integer parsing and localhost origin CSRF validation for preview bridge. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/session_store.py` | 138 | session_store.py: PreviewSession dataclass, thread-safe session registry, pruning, and style assignment. | `PreviewSession`, `register_preview_session()`, `get_preview_session()`, `unregister_preview_session()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/target_resolver.py` | 71 | target_resolver.py: Resolves upstream video and audio stream targets and headers for preview playback. | `resolve_preview_video_target()`, `resolve_preview_audio_target()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/tk_dispatch.py` | 24 | tk_dispatch.py: Thread-safe Tkinter main-thread callback dispatcher for preview sessions. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/upstream_streamer.py` | 274 | upstream_streamer.py: Upstream HTTP byte-range streaming and 2MB windowed YouTube proxy streaming. | `stream_upstream_media()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/preview/vtt_compiler.py` | 56 | vtt_compiler.py: Compiles SRT subtitles to WebVTT and serves them over HTTP for preview playback. | `compile_and_serve_vtt()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/startup/__init__.py` | 58 | Windows startup registry, Task Scheduler, and Startup shortcut management subpackage for Faqih Downloader: | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/startup/command_resolver.py` | 160 | Executable resolution, startup command formatting, and command line parsing for Faqih Downloader. | `get_installed_exe_path()`, `get_startup_folder()`, `get_startup_command()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/startup/constants.py` | 12 | Windows startup registry keys and Task Scheduler constants for Faqih Downloader. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/startup/shortcut_helper.py` | 83 | Windows startup shortcut (.lnk) creation utilities using WScript.Shell and PowerShell fallbacks. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/startup/startup_manager.py` | 329 | Windows startup registration, query, and unregistration manager for Faqih Downloader. | `is_startup_enabled()`, `enable_startup()`, `disable_startup()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/__init__.py` | 84 | subtitles package: Subtitle parsing, translation, fetching, caching, downloading, FFmpeg muxing, and prefetching. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/cache.py` | 76 | cache.py: Thread-safe timedtext base cue cache. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/downloader.py` | 124 | downloader.py: Orchestrates single .srt subtitle download, conversion, GTX fallback, and UTF-8 disk persistence. | `download_subtitle_as_srt()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/fetcher.py` | 150 | fetcher.py: Multi-phase subtitle network fetching (direct HTTP, browser cookies, and yt-dlp). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/ffmpeg_exec.py` | 91 | ffmpeg_exec.py: Cancellable FFmpeg execution wrapper and ASCII-safe temporary directory resolution. | `run_cancellable_ffmpeg()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/muxer.py` | 272 | muxer.py: Soft subtitle MP4 muxing and hard subtitle frame burning via FFmpeg. | `embed_subtitle_into_mp4()`, `burn_subtitle_into_video()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/parser.py` | 206 | parser.py: Subtitle format parsing (XML, JSON3, WebVTT, SRT), timestamp conversion, and cue formatting. | `convert_vtt_to_srt()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/post_processor.py` | 209 | post_processor.py: Post-download subtitle coordination, burn-tag stripping, and sidecar .srt sync. | `strip_burn_tag_from_filename()`, `handle_subtitles_post_download()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/prefetch.py` | 67 | prefetch.py: Background parallel prefetching of primary, dual, and external .srt subtitle tracks. | `start_subtitle_prefetch()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/subtitles/translator.py` | 128 | translator.py: Google Translate GTX endpoint batch subtitle cue translation. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/__init__.py` | 68 | Updates package: Application auto-updater, yt-dlp dynamic plugin updater, and core hot-patch engine. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/app_updater.py` | 251 | AppAutoUpdater: GitHub Releases update checker, installer downloader, and upgrader. | `AppAutoUpdater` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/constants.py` | 15 | Application identity, version, and remote update API endpoint constants. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/core_hotpatch.py` | 306 | CoreHotPatchUpdater: OTA Core Patch checker, downloader, atomic applier, and activator. | `CoreHotPatchUpdater` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/core_loader.py` | 149 | Dynamic Core Loader & Import Hook (_ExternalCoreFinder, _purge_and_reimport_core, init_core_loader). | `_ExternalCoreFinder`, `init_core_loader()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/core_packager.py` | 80 | Core Hot-Patch Packager: builds lightweight CorePatch.zip bundles in <0.5s. | `build_core_patch_zip()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/paths_and_ssl.py` | 103 | Application data/plugin directory resolvers, trusted update URL validation, | `get_app_data_dir()`, `get_ytdlp_plugin_dir()`, `get_core_plugin_dir()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/versioning.py` | 143 | Semantic and date-based version parsing and comparison helpers. | `parse_version()`, `is_newer_version()`, `is_version_ge()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/ytdlp_activation.py` | 163 | YtDlpPluginActivationMixin: validation, version inspection, activation, and rollback | `YtDlpPluginActivationMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/ytdlp_downloader.py` | 320 | YtDlpArchiveUpdaterMixin: checking PyPI/GitHub Releases, downloading, validating, | `YtDlpArchiveUpdaterMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/ytdlp_finder.py` | 34 | _ExternalYtDlpFinder: sys.meta_path import hook giving precedence to an updated external yt_dlp plugin. | `_ExternalYtDlpFinder` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/updates/ytdlp_manager.py` | 51 | YtDlpAutoUpdater: orchestrator class composing plugin activation and archive updates. | `YtDlpAutoUpdater` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/__init__.py` | 83 | YouTube package: constants, URL matchers, stream models, extractors, format builders, and resolver. | `__getattr__()`, `__dir__()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/client_tier.py` | 27 | YouTube format client throttling tier ranking for Faqih Downloader. | `get_format_client_tier()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/constants.py` | 87 | Regular expressions, platform identifiers, and static configuration constants | — | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/format_builder.py` | 10 | YouTubeFormatBuilderMixin composition mixin combining format options and stream info builders. | `YouTubeFormatBuilderMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/format_extractor.py` | 243 | YouTubeFormatExtractorMixin: yt-dlp options construction, metadata/cookie extraction, | `YouTubeFormatExtractorMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/format_options_builder.py` | 378 | YouTube and social media format options builder mixin for Faqih Downloader. | `YouTubeFormatOptionsBuilderMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/merger.py` | 118 | YouTubeStreamMergerMixin: lossless FFmpeg stream multiplexing and transcode fallback. | `YouTubeStreamMergerMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/models.py` | 163 | Structured data models and filename/filesize formatting helpers for YouTube & social media streams. | `VideoFormatOption`, `YouTubeStreamInfo`, `sanitize_filename()`, `format_filesize()`, `resolve_preferred_option_index()` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/resolver.py` | 50 | YouTubeResolver (alias MediaResolver): orchestrator class composing extraction, | `YouTubeResolver` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/stream_info_builder.py` | 166 | YouTube and social media stream info builder mixin for Faqih Downloader. | `YouTubeStreamInfoBuilderMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/tiktok_fallback.py` | 244 | TikTokFallbackMixin: direct HTML rehydration and TikWM API fallback extractors. | `TikTokFallbackMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/services/youtube/url_matcher.py` | 151 | URL matching, platform identification, media ID extraction, and yt-dlp extractor probing. | `is_youtube_url()`, `is_social_media_url()`, `is_ytdlp_extractor_supported()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/__init__.py` | 45 | UI package exports. | — | Edit when exposing new UI components or windows. |
| `src/faqih_downloader/ui/main_window.py` | 243 | ModernFramelessGUI main application window aggregating all panel and controller mixins. | — | Edit when adding or removing window-level mixins or altering root layout. |
| `src/faqih_downloader/ui/system_tray.py` | 254 | Windows system tray integration (pystray) with minimize/restore and context menus. | `SystemTrayManager` | Edit when modifying system tray icon behavior or menu options. |
| `src/faqih_downloader/ui/app/__init__.py` | 23 | app package: Main application window GUI, bootstrap launcher, and legacy export bindings. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/app/bootstrap.py` | 159 | Application launch entry point, single-instance mutex enforcement, and CLI dispatch. | `main()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/app/gui.py` | 286 | ModernFramelessGUI: Complete Dark-themed, frameless, dynamic chunking download manager GUI. | `ModernFramelessGUI` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/app/legacy_exports.py` | 12 | Consolidated compatibility and legacy re-export surface for Faqih Downloader GUI. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/__init__.py` | 4 | Reusable UI components package exports. | — | Edit when exposing new UI components. |
| `src/faqih_downloader/ui/components/arc_spinner.py` | 136 | ArcSpinnerCanvas: Circular glowing arc spinner widget for parsing / pending cards in Smart Download (SD). | `ArcSpinnerCanvas` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/base_modal.py` | 333 | SafeModalDialog: non-blocking frameless themed modal dialog base class. | `SafeModalDialog` | Edit when modifying modal dialog styling, backdrop, or grab behavior. |
| `src/faqih_downloader/ui/components/led_matrix.py` | 298 | LedEqualizerMatrix: Dynamic Turbo Stream Lanes visualizer widget for Smart Download (SD). | `LedEqualizerMatrix` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/tooltip.py` | 104 | Hover tooltip widget providing contextual explanations for buttons and controls. | `ToolTip` | Edit when changing tooltip styling, delay timings, or positioning. |
| `src/faqih_downloader/ui/components/top_bar.py` | 432 | TopHeaderBarMixin: Unified Top Header Bar implementation for Smart Download (SD) v2.0.2. | `TopHeaderBarMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/components/waveform_visualizer.py` | 125 | WaveformVisualizerCanvas: Symmetrical audio waveform visualizer for completed audio cards in Smart Download (SD). | `WaveformVisualizerCanvas` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/__init__.py` | 41 | Controllers package exports. | — | Edit when adding new controller mixins. |
| `src/faqih_downloader/ui/controllers/batch_download_controller.py` | 102 | BatchDownloadControllerMixin managing multiple download candidates selection and queueing. | `BatchDownloadControllerMixin` | Edit when modifying batch link selection or sequential download triggers. |
| `src/faqih_downloader/ui/controllers/browser_controller.py` | 143 | BrowserControllerMixin handling background extension registration and intercepted downloads. | `BrowserControllerMixin` | Edit when modifying intercepted browser link handling in the GUI. |
| `src/faqih_downloader/ui/controllers/clipboard_controller.py` | 414 | ClipboardControllerMixin sniffing clipboard for valid download and media URLs. | `ClipboardControllerMixin`, `get_url_sniffer_platform_key()` | Edit when modifying clipboard polling intervals, URL regexes, or sniffing logic. |
| `src/faqih_downloader/ui/controllers/clipboard_dialog_mixin.py` | 344 | clipboard_dialog_mixin.py: Clipboard download confirmation dialog, URL dispatching, | `ClipboardDialogMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/dialog_controller.py` | 199 | DialogControllerMixin providing thread-safe non-blocking modal dialogs. | `DialogControllerMixin` | Edit when modifying safe error, warning, or confirmation dialog dispatching. |
| `src/faqih_downloader/ui/controllers/dispatch_controller.py` | 71 | DispatchControllerMixin dispatching background thread tasks safely to Tkinter event loop. | `DispatchControllerMixin` | Edit when changing thread synchronization or GUI queue processing. |
| `src/faqih_downloader/ui/controllers/download_callbacks_mixin.py` | 345 | download_callbacks_mixin.py: Engine progress, chunk visualization, GUI periodic tick, | `DownloadCallbacksMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/download_controller.py` | 425 | DownloadControllerMixin coordinating download start, engine creation, and queue execution. | `DownloadControllerMixin` | Edit when modifying download trigger flow or engine callback wiring. |
| `src/faqih_downloader/ui/controllers/lifecycle_controller.py` | 316 | WindowLifecycleMixin managing resource cleanup, tray minimization, and clean exit. | `WindowLifecycleMixin` | Edit when modifying window close actions, thread cleanup, or tray exit. |
| `src/faqih_downloader/ui/controllers/link_refresh_controller.py` | 97 | LinkRefreshControllerMixin handling expired download link resumption and URL substitution. | `LinkRefreshControllerMixin` | Edit when altering expired link substitution or refresh dialog triggers. |
| `src/faqih_downloader/ui/controllers/locale_controller.py` | 254 | LocaleControllerMixin coordinating dynamic UI text re-translation upon language switch. | `LocaleControllerMixin` | Edit when adding dynamic language switch observers or RTL layout adjustments. |
| `src/faqih_downloader/ui/controllers/media_download_controller.py` | 23 | MediaDownloadControllerMixin composite mixin aggregating YouTube, batch, and refresh. | `MediaDownloadControllerMixin` | Edit when altering composite media controller inheritance. |
| `src/faqih_downloader/ui/controllers/settings_controller.py` | 335 | SettingsControllerMixin managing user preferences, cookies, and auto-categorization. | `SettingsControllerMixin` | Edit when adding new user preference toggles or cookies browser selection. |
| `src/faqih_downloader/ui/controllers/speed_limiter_controller.py` | 179 | SpeedLimiterControllerMixin managing speed presets, slider events, and rate limits. | `SpeedLimiterControllerMixin` | Edit when modifying speed limiter presets or live slider adjustment handlers. |
| `src/faqih_downloader/ui/controllers/theme_controller.py` | 218 | ThemeControllerMixin configuring dark theme color tokens and UI styling. | `ThemeControllerMixin` | Edit when changing application colors, fonts, or styling variables. |
| `src/faqih_downloader/ui/controllers/toast_controller.py` | 200 | ToastControllerMixin presenting non-blocking corner toast notifications. | `ToastControllerMixin` | Edit when modifying startup welcome toast or notification toast animations. |
| `src/faqih_downloader/ui/controllers/update_controller.py` | 170 | UpdateControllerMixin running background checks for app and yt-dlp updates. | `UpdateControllerMixin` | Edit when changing background update check frequency or update notification dialogs. |
| `src/faqih_downloader/ui/controllers/window_controller.py` | 424 | WindowChromeMixin managing custom frameless title bar dragging and window controls. | `WindowChromeMixin` | Edit when modifying custom title bar widgets, drag handling, or window geometry. |
| `src/faqih_downloader/ui/controllers/window_resize_mixin.py` | 415 | WindowResizeMixin: 8-edge & corner resizing grips and border drag handlers for frameless window. | `WindowResizeMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/youtube_download_controller.py` | 32 | YouTubeDownloadControllerMixin analyzing streaming media formats and quality selection. | — | Edit when modifying YouTube/social media format inspection and dialog invocation. |
| `src/faqih_downloader/ui/controllers/youtube_dl/__init__.py` | 12 | youtube_dl package: YouTube download extraction flow, stream launcher, and controller mixin. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/youtube_dl/controller.py` | 13 | YouTubeDownloadControllerMixin: Composite mixin combining format extraction flow and stream launcher. | `YouTubeDownloadControllerMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/youtube_dl/extraction_flow.py` | 406 | YouTubeExtractionFlowMixin: Format probing, quality analysis, and quality selection dialog flow. | `YouTubeExtractionFlowMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/controllers/youtube_dl/stream_launcher.py` | 146 | YouTubeStreamLauncherMixin: Stream coordinator instantiation, queue coordination, and event hook attachment. | `YouTubeStreamLauncherMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/__init__.py` | 34 | Modals package exports. | — | Edit when adding new modal dialog exports. |
| `src/faqih_downloader/ui/modals/browser_settings_modal.py` | 41 | BrowserSettingsModalMixin displaying browser extension setup and diagnostic dialog. | — | Edit when modifying browser extension configuration instructions or diagnostic steps. |
| `src/faqih_downloader/ui/modals/candidates_modal.py` | 484 | MultipleCandidatesModal displaying detected web download candidates with filter badges. | `MultipleCandidatesModal` | Edit when modifying candidate dialog multi-selection, search, or filtering controls. |
| `src/faqih_downloader/ui/modals/confirm_modal.py` | 184 | DownloadConfirmationModal showing probed file details before starting download. | `DownloadConfirmationModal` | Edit when changing pre-download confirmation dialog layout or field editing. |
| `src/faqih_downloader/ui/modals/confirm_modal_logic.py` | 345 | Logic helper probing download candidate metadata for the confirmation modal. | `ConfirmModalLogicMixin` | Edit when modifying candidate probing threads or URL validation. |
| `src/faqih_downloader/ui/modals/confirm_modal_progress.py` | 223 | ConfirmModalProgressMixin: Live progress tracking, canvas drawing, metrics updating, and completion handling. | `ConfirmModalProgressMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/confirm_modal_widgets.py` | 316 | ConfirmModalWidgetsMixin: UI component builders for DownloadConfirmationModal. | `ConfirmModalWidgetsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/fetching_toast.py` | 387 | FetchingLinkToast displaying a loading spinner toast during link inspection. | `FetchingLinkToast` | Edit when modifying link resolving loading animation or cancel triggers. |
| `src/faqih_downloader/ui/modals/file_info_modal.py` | 350 | FileInfoModal: Detailed File & Link Information modal dialog for Faqih Downloader (FD) v2.0.2. | `FileInfoModal`, `open_file_info_modal()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview_clipper_studio.py` | 12 | Smart live video clipper bar, double-click subtitle text editor, and dual bilingual subtitle controls. | — | Edit when modifying live video clipping bar, subtitle text fixer popup, or dual subtitles UI. |
| `src/faqih_downloader/ui/modals/preview_html_builder.py` | 13 | Backward-compatibility shim for preview_html_builder. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview_subtitle_studio.py` | 12 | Interactive in-video subtitle studio providing real-time styling, positioning toolbar, and drag-and-drop. | — | Edit when modifying the live subtitle studio toolbar, CSS presets, or video overlay controls. |
| `src/faqih_downloader/ui/modals/quality_modal.py` | 19 | QualitySelectionModal presenting video resolutions and audio bitrates for media. | — | Edit when modifying media format selection dialog, badges, or treeview. |
| `src/faqih_downloader/ui/modals/quality_modal_helpers.py` | 409 | Helper functions and banner builder for QualitySelectionModal (quality_modal_helpers.py). | `attach_selected_tracks_to_option()`, `sync_modal_selection_to_staged()`, `resolve_final_dest()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality_tracks_ui.py` | 332 | quality_tracks_ui.py: UI widgets for audio tracks and subtitle options in QualitySelectionModal. | `format_ext_srt_button_text()`, `open_ext_srt_popup_menu()`, `build_audio_subtitle_row()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/refresh_modal.py` | 494 | RefreshLinkModal prompting for updated download link when a session expires. | `RefreshLinkModal` | Edit when changing expired link substitution dialog styling or URL validation. |
| `src/faqih_downloader/ui/modals/settings_modal.py` | 21 | Backward-compatibility shim for settings_modal. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings_modal_extra.py` | 325 | SettingsModalExtraMixin: Speed Limiter and Engine Log tab builders for SettingsModal in Smart Download (SD). | `SettingsModalExtraMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings_modal_tabs.py` | 426 | SettingsModalTabsMixin: Tab building logic for SettingsModal in Smart Download (SD). | `SettingsModalTabsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/toasts.py` | 10 | Re-exports toast notification classes for convenient imports. | — | Edit when exposing additional toast classes. |
| `src/faqih_downloader/ui/modals/update_modal.py` | 367 | AppUpdateModal displaying new release notes and one-click update actions. | `AppUpdateModal` | Edit when modifying application update presentation or release notes formatting. |
| `src/faqih_downloader/ui/modals/vault_restore_modal.py` | 23 | Backward-compatibility shim for vault_restore_modal. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/video_preview_modal.py` | 30 | VidMate-style in-app video preview modal with live WebVTT subtitles and chromeless player. | — | Edit when modifying video preview playback, WebVTT subtitle overlay, or player window launcher. |
| `src/faqih_downloader/ui/modals/welcome_toast.py` | 312 | StartupWelcomeToast displaying Windows startup greeting when running minimized. | `StartupWelcomeToast` | Edit when modifying startup toast layout or click-to-restore action. |
| `src/faqih_downloader/ui/modals/browser_settings/__init__.py` | 14 | browser_settings package: Browser integration dialog, status indicators, and extension installation sections. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/browser_settings/capture_settings_section.py` | 203 | Capture settings section builder for browser settings dialog (clipboard monitor, startup auto-boot, tray minimization, auto-unpack). | `build_capture_settings_section()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/browser_settings/extension_section.py` | 95 | Extension installation guide and directory section builder for browser settings dialog. | `build_extension_section()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/browser_settings/modal.py` | 136 | BrowserSettingsModalMixin: Browser WebExtension setup dialog and host registration. | `BrowserSettingsModalMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/browser_settings/status_section.py` | 164 | Status section builder for browser settings dialog (IPC loopback listener & Windows Registry Native Messaging). | `build_status_section()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/__init__.py` | 46 | preview package: Video preview launcher, process management, stream selector, clipper studio, and subtitle studio assets. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/clipper_css.py` | 45 | clipper_css.py: CSS styles for the live clipper bar, subtitle editor modal, and dual subtitles. | `get_clipper_css()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/clipper_html.py` | 74 | clipper_html.py: HTML toolbar markup for live clipper controls, chapters selector, audio boost, and subtitle editor modal. | `get_clipper_toolbar_html()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/clipper_js.py` | 440 | clipper_js.py: Client-side JavaScript for smart live clipping, subtitle fixer, Web Audio boost, and dual subs. | `get_clipper_js()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/launcher.py` | 312 | launcher.py: Orchestrates VidMate-style video preview window launch via bridge and chromeless/webview UI. | `open_video_preview()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/player_css.py` | 48 | CSS styles for HTML5 preview player. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/player_html.py` | 166 | HTML document assembly for HTML5 preview player. | `generate_preview_html()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/player_js.py` | 329 | JavaScript template for HTML5 preview player. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/process_launcher.py` | 108 | process_launcher.py: Subprocess lifecycle, pywebview launcher, and chromeless browser discovery. | `_PreviewJsApi`, `terminate_active_preview_proc()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/stream_selector.py` | 58 | stream_selector.py: Progressive MP4 preview stream selection and SRT-to-VTT data URI conversion. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/subtitle_studio_css.py` | 75 | subtitle_studio_css.py: CSS rules for the live draggable subtitle overlay and styling studio bar. | `get_studio_css()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/subtitle_studio_html.py` | 44 | subtitle_studio_html.py: HTML markup for the interactive subtitle styling toolbar. | `get_studio_toolbar_html()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/preview/subtitle_studio_js.py` | 304 | subtitle_studio_js.py: Client-side JavaScript for subtitle parsing, live overlay syncing, and drag-and-drop. | `get_studio_js()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality/__init__.py` | 16 | quality package for Faqih Downloader (FD). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality/action_handlers.py` | 143 | QualityModalActionsMixin: Action dispatchers for downloading video/MP3, launching preview, and opening in main window. | `QualityModalActionsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality/layout_builder.py` | 197 | QualityModalLayoutMixin: Builds the visual layout and widget hierarchy for QualitySelectionModal. | `QualityModalLayoutMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality/modal.py` | 158 | QualitySelectionModal: Interactive video/audio resolution and stream format picker. | `QualitySelectionModal` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/quality/selection_handlers.py` | 129 | QualityModalSelectionMixin: Handlers for Treeview selection, destination browsing, track attaching, and initial options. | `QualityModalSelectionMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/__init__.py` | 18 | settings package for Faqih Downloader (FD). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/layout_builder.py` | 98 | SettingsModalLayoutMixin: Builds the visual layout and tab notebook for SettingsModal. | `SettingsModalLayoutMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/modal.py` | 208 | SettingsModal: Frameless dark application settings dialog with per-platform sniffer filtering, | `SettingsModal` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/network_system_handlers.py` | 140 | SettingsNetworkSystemMixin: Network thread warnings, cookie management, and OS system integrations. | `SettingsNetworkSystemMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/sniffer_handlers.py` | 61 | SettingsSnifferHandlersMixin: Platform sniffer toggling, button updates, and master sniffer switches. | `SettingsSnifferHandlersMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/settings/storage_handlers.py` | 90 | SettingsStorageHandlersMixin: Directory selection, path synchronization, and archive/categorization settings. | `SettingsStorageHandlersMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/__init__.py` | 18 | vault_restore package for Faqih Downloader (FD). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/actions_mixin.py` | 108 | VaultRestoreActionsMixin: Disk browsing, folder loading, history batch additions, and modal finalization. | `VaultRestoreActionsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/modal.py` | 207 | VaultRestoreModal: Selective file restoration modal dialog for Completed Vault in Smart Download (SD). | `VaultRestoreModal` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/rows_builder.py` | 144 | VaultRestoreRowsMixin: File row generation, formatting, and pagination loading. | `VaultRestoreRowsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/scroll_mixin.py` | 91 | VaultRestoreScrollMixin: Smooth scrolling and debounced canvas scrollregion updates. | `VaultRestoreScrollMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/modals/vault_restore/selection_mixin.py` | 66 | VaultRestoreSelectionMixin: Search filtering and interactive row selection handling. | `VaultRestoreSelectionMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/__init__.py` | 18 | Panels package exports. | — | Edit when adding new panel mixin exports. |
| `src/faqih_downloader/ui/panels/chunks_panel.py` | 19 | ChunksPanelMixin rendering segmented dynamic chunk visualizer and status table. | — | Edit when modifying segmented chunk canvas graphics or chunk details treeview. |
| `src/faqih_downloader/ui/panels/controls_panel.py` | 430 | ControlsPanelMixin rendering thread selector, speed limiter controls, and action buttons. | `_StateButton`, `ControlsPanelMixin` | Edit when changing start/pause/cancel action buttons or limiter controls. |
| `src/faqih_downloader/ui/panels/hidden_compat_panel.py` | 295 | HiddenCompatPanelMixin: Preserves 100% of internal widgets and variables expected by tests and controllers. | `_CompatButton`, `HiddenCompatPanelMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/history_panel.py` | 287 | HistoryPanelMixin managing download history table and right-click context menu. | `HistoryPanelMixin` | Edit when modifying history treeview columns or context menu actions. |
| `src/faqih_downloader/ui/panels/inputs_panel.py` | 198 | InputsPanelMixin rendering URL and destination inputs with auto-categorization button. | `InputsPanelMixin` | Edit when modifying URL entry, destination browse button, or auto-cat toggle. |
| `src/faqih_downloader/ui/panels/kanban_active_mixin.py` | 353 | KanbanActiveColumnMixin: Column 2 (Active Turbo Streams) management for Smart Download (SD). | `KanbanActiveColumnMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_card_graphics.py` | 231 | kanban_card_graphics.py: Thumbnail extraction, icon drawing, and progress bar graphics | `draw_neon_progress_bar()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_cards.py` | 445 | Kanban Card Widgets and Rounded Glass Builders for Smart Download (SD) v2.0.2. | `create_empty_state()`, `build_queued_card()`, `build_vault_card()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_panel.py` | 21 | Backward-compatibility shim for kanban_panel. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_staged_helpers.py` | 402 | kanban_staged_helpers.py: Staged Link Card builder, context menu, and URL probing | `show_staged_context_menu()`, `build_staged_link_card()`, `render_col1_staged_cards()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_staged_prober.py` | 453 | kanban_staged_prober.py: Staged URL probers and download launch workers | `stage_media_option_in_col1()`, `probe_and_stage_pasted_url()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_vault_helpers.py` | 439 | Completed Vault helpers: filtering pills, context menus, and pagination controls for Smart Download (SD). | `get_entry_category()`, `filter_vault_entries()`, `build_vault_filter_pills()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban_vault_ops.py` | 275 | kanban_vault_ops.py: Completed Vault filesystem operations, disk scanning, | `clear_completed_vault_entries()`, `scan_unregistered_disk_files()`, `restore_vault_entries_from_disk()` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_options_actions.py` | 469 | MediaOptionsActionsMixin: Actions, modal triggers, preview handlers, and download starters | `MediaOptionsActionsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_options_bar.py` | 35 | Backward-compatibility shim for media_options_bar. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/metrics_panel.py` | 99 | MetricsPanelMixin rendering overall progress bar and real-time metric cards. | `MetricsPanelMixin` | Edit when modifying speed, size, ETA, or thread count metric cards. |
| `src/faqih_downloader/ui/panels/chunks/__init__.py` | 17 | chunks package for Faqih Downloader (FD). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/chunks/context_menu.py` | 116 | ChunksContextMenuMixin: Right-click context menus for chunk treeview and download action routing. | `ChunksContextMenuMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/chunks/panel.py` | 21 | ChunksPanelMixin: Dynamic chunk visualization, tabbed consoles, and chunk-tree context actions. | `ChunksPanelMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/chunks/tabs_builder.py` | 268 | ChunksTabsBuilderMixin: Tabbed consoles (Chunks table, Activity Log, Download History) and resize management. | `ChunksTabsBuilderMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/chunks/visualizer.py` | 158 | ChunksVisualizerMixin: Dynamic chunk visualization canvas and segment byte map. | `ChunksVisualizerMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/__init__.py` | 19 | kanban package for Faqih Downloader (FD). | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/col1_queued.py` | 122 | KanbanQueuedColumnMixin: Column 1 queued and parsing links manager for Kanban pipeline. | `KanbanQueuedColumnMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/col3_vault.py` | 130 | KanbanVaultColumnMixin: Column 3 Completed Vault workspace for Kanban pipeline. | `KanbanVaultColumnMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/panel.py` | 58 | KanbanPanelMixin: 3-Column dynamic pipeline workspace for Faqih Downloader (FD). | `KanbanPanelMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/vault_actions.py` | 68 | KanbanVaultActionsMixin: Action handlers, context menus, and file openers for Completed Vault. | `KanbanVaultActionsMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/kanban/vault_scroll.py` | 86 | KanbanVaultScrollMixin: Smooth mousewheel scrolling and wheel routing for Completed Vault. | `KanbanVaultScrollMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_bar/__init__.py` | 16 | media_bar package: Media options bar components, layout builders, state synchronizers, and event handlers. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_bar/bar.py` | 20 | MediaOptionsBarMixin composite mixin combining layout, state sync, event handlers, and media actions. | `MediaOptionsBarMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_bar/event_handlers.py` | 102 | MediaBarEventHandlersMixin: Event callbacks for user dropdown selections and clicks in the media bar. | `MediaBarEventHandlersMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_bar/layout_builder.py` | 161 | MediaBarLayoutMixin: UI construction and localization for the Main Window Media Settings Bar. | `MediaBarLayoutMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/ui/panels/media_bar/state_sync.py` | 323 | MediaBarStateSyncMixin: Synchronization of media selections, staged card contexts, and Kanban models. | `MediaBarStateSyncMixin` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/__init__.py` | 85 | Utils package exports. | `__getattr__()`, `__dir__()` | Edit when exporting new utility helpers. |
| `src/faqih_downloader/utils/archive_utils.py` | 172 | Archive auto-extraction and SHA-256 file integrity verification. | `calculate_file_integrity()`, `auto_unpack_archive()` | Edit when supporting new archive formats or hash algorithms. |
| `src/faqih_downloader/utils/clipboard.py` | 75 | Cross-platform and Win32 direct clipboard text retrieval. | `get_clipboard_text()` | Edit when improving clipboard access reliability on Windows. |
| `src/faqih_downloader/utils/dpi.py` | 83 | Windows High-DPI awareness initialization and screen work area geometry. | `enable_high_dpi_awareness()`, `get_windows_work_area()` | Edit when tuning DPI scaling factors or multi-monitor geometry detection. |
| `src/faqih_downloader/utils/file_ops.py` | 38 | File categorization into subfolders (Videos, Music, etc.) and file/folder launching. | — | Edit when modifying category subfolder mappings or OS shell execute actions. |
| `src/faqih_downloader/utils/magic_detector.py` | 88 | Binary magic bytes detector determining actual file types independent of URL extensions. | `MagicBytesDetector` | Edit when adding new file signature definitions. |
| `src/faqih_downloader/utils/speed_utils.py` | 91 | Speed string parsing (e.g. '1.5 MB/s') and human-readable formatting. | `parse_speed_limit()`, `format_speed()` | Edit when updating speed parsing regexes or unit formats. |
| `src/faqih_downloader/utils/tk_helpers.py` | 397 | Tkinter resource cleanup preventing photo reference and callback memory leaks. | `animate_window_open()`, `animate_window_close()` | Edit when adding memory leak mitigations for Tkinter widgets. |
| `src/faqih_downloader/utils/url_utils.py` | 393 | URL parsing, filename derivation, and Content-Disposition header extraction. | `is_downloadable_url()`, `clean_download_filename()`, `derive_download_filename()` | Edit when improving filename derivation from complex redirect URLs. |
| `src/faqih_downloader/utils/window_effects.py` | 23 | Backward-compatibility shim for window effects. | — | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/effects/__init__.py` | 29 | Window effects and rounded canvas styling subpackage for Faqih Downloader: | — | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/effects/canvas_shapes.py` | 120 | Smooth rounded rectangle and glowing border Canvas drawing helpers for Faqih Downloader. | `draw_rounded_rect()`, `draw_glow_border()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/effects/dwm_effects.py` | 140 | Windows DWM dark titlebar, Acrylic, and Mica backdrop effects via Win32 APIs for Faqih Downloader. | `enable_dark_titlebar()`, `apply_acrylic_or_mica_effect()`, `apply_window_opacity()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/effects/glass_card.py` | 205 | Rounded Frosted Glass Canvas Container for Faqih Downloader. | `RoundedGlassCard` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/__init__.py` | 43 | File operations subpackage for Faqih Downloader: | — | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/atomic_io.py` | 32 | Atomic file replacement and retry utilities for Faqih Downloader. | `atomic_replace_with_retry()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/categories.py` | 73 | File category classifications, extension icons, and path categorization for Faqih Downloader. | `get_file_category_and_icon()`, `resolve_categorized_path()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/naming.py` | 115 | File destination naming, anti-collision numbering, and media tag formatting for Faqih Downloader. | `generate_unique_destination_path()`, `apply_media_filename_tags()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/path_matcher.py` | 146 | On-disk file searching and fuzzy download path resolution for Faqih Downloader. | `resolve_existing_download_path()` | Edit when modifying this module's features. |
| `src/faqih_downloader/utils/files/shell_open.py` | 91 | OS shell launch utilities (open file, reveal in explorer/finder) for Faqih Downloader. | `open_downloaded_file()`, `open_containing_folder()` | Edit when modifying this module's features. |
| `faqih_downloader.py` | 459 | Main official application entry point, CLI dispatcher, and unified symbol re-exporter. | `_SmartDownloadAliasLoader`, `_SmartDownloadAliasFinder`, `_FaqihDownloaderShim` | Edit when updating top-level launch hooks, CLI flags, or application initialization. |
| `turbo_downloader.py` | 58 | Backward-compatibility root shim re-exporting all symbols from faqih_downloader. | `_TurboDownloaderCompatShim` | Edit when maintaining legacy backward-compatible import compatibility. |
| `browser_bridge.py` | 24 | Backward-compatibility root shim re-exporting BrowserBridgeServer. | — | Edit when changing browser bridge root exports. |
| `native_messaging_host.py` | 29 | Backward-compatibility root shim re-exporting native messaging host functions. | — | Edit when updating native messaging entry point. |
| `register_browser.py` | 37 | Backward-compatibility root shim for browser extension registration commands. | — | Edit when updating browser registration CLI entry point. |
| `updater.py` | 48 | Backward-compatibility root shim re-exporting AppAutoUpdater and CoreHotPatchUpdater. | — | Edit when adding top-level updater exports. |
| `youtube_resolver.py` | 65 | Backward-compatibility root shim re-exporting YouTube and media resolver interfaces. | `_YouTubeResolverShim` | Edit when updating YouTube resolver root exports. |
| `release_publisher.py` | 354 | Automated GitHub Releases publisher supporting fast zero-rebuild core patch publishing. | `log()`, `get_git_credentials()`, `api_request()` | Edit when modifying release publishing workflow or asset upload logic. |
| `build_installer.py` | 458 | Automated build script compiling PyInstaller bundles and Windows setup installer. | `clean_stale_shadow_modules()`, `verify_exe_startup()`, `clean_stale_dist_artifacts()` | Edit ONLY when user explicitly commands 'build installer' or 'ابنِ المثبت'. |
| `installer.py` | 119 | Standalone installer runner executing SmartDownload setup wizard. | `_InstallerShim`, `main()` | Edit when modifying standalone installer CLI options. |
| `tests/__init__.py` | 11 | Tests package initialization. | — | Edit when configuring test discovery fixtures. |
| `tests/conftest.py` | 81 | Module implementation for Smart Download. | `_SmartDownloadAliasLoader`, `_SmartDownloadAliasFinder` | Edit when modifying this module's features. |
| `tests/test_browser.py` | 631 | Unit tests for browser extension bridge, native host stdio, and Windows registry. | `TestBrowserBridgeServer`, `TestBrowserBridgeConcurrency`, `TestExtensionManifestAndAssets`, `TestNativeMessagingHostProtocol`, `TestBrowserRegistryIntegration`, `setUpModule()`, `tearDownModule()` | Edit when adding tests for browser integration features. |
| `tests/test_bugfixes.py` | 3735 | Automated unit and integration tests for Part 1 (Subtitle Hard-Burn fixes & GTX translation fallback) | `TestSubtitleProcessorAndGTXFallback`, `TestVideoPreviewModal`, `TestHardenedFFmpeg`, `TestPreviewStreamBridgeAndUnifiedVidMatePlayer`, `TestPart1To4CriticalBugfixes`, `TestWindowMaximizeAndTikTokDirectFixes`, `TestGeometryAndSanitizationAndTikTokDeduplication`, `TestClipboardPlatformFilteringAndSettings`, `TestMainToolbarCleanup`, `TestStartupAndWelcomeToastBugfixes` | Edit when modifying this module's features. |
| `tests/test_clipper_and_dual_subs.py` | 1745 | Unit and Integration Tests for Smart Live Clipper & Dual Bilingual Subtitles. | `TestClipperAndDualSubs` | Edit when modifying this module's features. |
| `tests/test_concurrent_redownload_and_tags.py` | 501 | Unit tests verifying concurrent re-download path uniqueness, | `TestConcurrentRedownloadAndTags` | Edit when modifying this module's features. |
| `tests/test_core_patch_updater.py` | 424 | Unit tests for CoreHotPatchUpdater, packaging, rollback, and dynamic loading. | `_MockStreamResp`, `TestCoreHotPatchAndZeroRebuildWorkflow` | Edit when testing OTA core hot-patching or zero-rebuild workflow. |
| `tests/test_dpi_and_assets.py` | 398 | Unit tests for Windows High-DPI scaling, icons, and asset resolution. | `TestDPIAndAssets`, `setUpModule()`, `tearDownModule()` | Edit when adding tests for display scaling or asset bundling. |
| `tests/test_engine_core.py` | 794 | Unit tests for TurboDownloadEngine, chunking, rate limiting, and worker pooling. | `MockServerHandler`, `TestTurboDownloader`, `TestSmartDownloadBrandingAndParts`, `setUpModule()`, `tearDownModule()` | Edit when testing download core algorithms and throttling. |
| `tests/test_engine_resume.py` | 485 | Unit tests for download pause, resume, and .sd_parts persistence. | `MockHeaderInspectHandler`, `TestEngineCustomHeaders`, `TestStreamCoordinatorIntegration`, `TestSmartDownloadPartsDirectory`, `TestHeadlessDecoupling`, `setUpModule()`, `tearDownModule()` | Edit when testing download resumption and manifest serialization. |
| `tests/test_external_subtitles.py` | 1045 | Regression and feature tests for Independent Multi-Language External .SRT Subtitles. | `TestExternalSubtitlesBackend`, `TestExternalSubtitlesUI`, `TestPreviewExtSrtAndSubtitleDedup` | Edit when modifying this module's features. |
| `tests/test_html_candidates.py` | 825 | Unit tests for web page candidate link extraction and filtering. | `MockHtmlResolverHandler`, `TestHtmlLinkResolverAndStartupToast`, `MockMultiCandidateServer`, `TestMultipleDownloadCandidates`, `setUpModule()`, `tearDownModule()` | Edit when testing HTML candidate link discovery. |
| `tests/test_i18n.py` | 467 | Unit tests for Arabic and English translations and runtime language toggling. | `TestBilingualLocalization`, `setUpModule()`, `tearDownModule()` | Edit when adding i18n and localization test cases. |
| `tests/test_installer.py` | 1190 | Unit tests for installer file extraction, registry keys, and shortcuts. | `TestWindowsInstallerLogic`, `TestStandaloneExeBuild`, `setUpModule()`, `tearDownModule()` | Edit when testing Windows installer operations. |
| `tests/test_kanban_pipeline.py` | 285 | Comprehensive unit tests for 100% Dynamic 3-Column Kanban Pipeline in Smart Download (SD) v2.0.2: | `TestKanbanPipeline` | Edit when modifying this module's features. |
| `tests/test_main_window_actions.py` | 787 | Unit tests for main window user actions, queueing, and callbacks. | `TestClipboardNonBlockingInterception`, `TestClipboardSnifferAndUrlValidation`, `setUpModule()`, `tearDownModule()` | Edit when testing GUI button actions and download queueing. |
| `tests/test_main_window_ui.py` | 866 | Unit tests for main window UI structure, widget creation, and layout. | `TestBackgroundAndMinimizedLaunch`, `TestSystemTrayAndBackgroundMinimization`, `TestClipboardSequenceRecopying`, `TestBackgroundStartupNotificationAndTray`, `setUpModule()`, `tearDownModule()` | Edit when testing window geometry, cards, and widget hierarchies. |
| `tests/test_media_options_and_continuity.py` | 256 | Unit tests verifying Media Options Bar UI wiring and Dubbing & Subtitle continuity fixes. | `TestMediaOptionsAndContinuity` | Edit when modifying this module's features. |
| `tests/test_modals_confirm.py` | 783 | Unit tests for DownloadConfirmationModal and candidate size probing. | `TestTDMDownloadConfirmationDialog`, `TestTDMConfirmationAndStandaloneProgress`, `setUpModule()`, `tearDownModule()` | Edit when testing confirmation modal logic. |
| `tests/test_modals_other.py` | 744 | Unit tests for quality, refresh, browser settings, and toast modals. | `TestQualitySelectionModalGUI`, `TestInstantFetchingLinkToast`, `setUpModule()`, `tearDownModule()` | Edit when testing secondary modal dialogs and toasts. |
| `tests/test_pause_resume_and_perf.py` | 1334 | Live E2E tests for Pause/Resume unblocking, Speed EMA smoothing, StreamCoordinator pause/resume, | `_ThrottledRangeHandler`, `_ThreadingHTTPServer`, `TestLivePauseResumeAndPerf` | Edit when modifying this module's features. |
| `tests/test_preview_reopen_and_network_stability.py` | 494 | Unit tests for Preview Window Reopen & Safe Wi-Fi Network Stability (tests/test_preview_reopen_and_network_stability.py). | `TestPreviewReopenAndNetworkStability` | Edit when modifying this module's features. |
| `tests/test_rebranding_and_improvements.py` | 1882 | Unit tests verifying the 5 radical improvements and rebranding in Faqih Downloader (FD): | `TestRebrandingAndImprovements`, `TestPhase2SecurityAndHardening` | Edit when modifying this module's features. |
| `tests/test_settings_history.py` | 825 | Unit tests for settings persistence, auto-categorization, and history manager. | `TestWindowsStartupRegistryIntegration`, `TestDownloadHistoryAndCategorization`, `setUpModule()`, `tearDownModule()` | Edit when testing preferences and download history operations. |
| `tests/test_stage4_srp_decomposition.py` | 345 | Unit tests verifying strict SRP decomposition (<550 lines per file). | `TestUIControllersSRP`, `TestUIPanelsSRP`, `TestCoreAndUtilsSRP` | Edit when adding new decomposed modules to verify strict line limits. |
| `tests/test_stage6_performance.py` | 263 | Unit test suite verifying Stage 6: Ultra-Performance, Low-Latency & High-Throughput Optimization. | `TestStage6PerformanceOptimizations` | Edit when modifying this module's features. |
| `tests/test_stage7_security_stress.py` | 470 | Unit and stress test suite verifying Stage 7: Enterprise Security Hardening & Heavy Stress Resilience. | `TestZipTarSlipSecurity`, `TestBridgeServerOriginCSRFSecurity`, `TestFilenameSanitizationAndWindowsReserved`, `TestFileRedirectSchemeSecurity`, `TestStressAndHeavyLoadResilience` | Edit when modifying this module's features. |
| `tests/test_stage8_2_live_ux.py` | 415 | Live Tkinter GUI Verification for Stage 8.2 UX & Window Lifecycle Overhaul. | `TestStage82LiveUX` | Edit when modifying this module's features. |
| `tests/test_stage8_dubbing_subtitles.py` | 735 | Unit tests for Stage 8: YouTube Multi-Language Audio Dubbing & Subtitle Selection/Embedding. | `DummyBuilder`, `TestYouTubeTracks` | Edit when modifying this module's features. |
| `tests/test_stage9_1_and_10_e2e.py` | 260 | Comprehensive Unit & E2E Verification for Smart Download Stages 9.1 & 10. | `TestStage9_1_And_10_Verification` | Edit when modifying this module's features. |
| `tests/test_stage9_2_stabilization.py` | 326 | Comprehensive verification test suite for Stage 9.2: | `TestStage9_2Stabilization` | Edit when modifying this module's features. |
| `tests/test_stage9_runtime_fixes.py` | 598 | Unit and integration tests for Stage 9: Comprehensive Runtime & UX Overhaul. | `TestSubtitleConversionStage9`, `TestBurnSubtitleEncodingAndPaths`, `TestStreamCoordinatorMultiThreading`, `DummyMockApp`, `TestOpenInMainAppAndMediaOptionsBar`, `TestFetchingToastSafety`, `TestSubtitleAutoSelection`, `TestHistoryRedownloadQuality` | Edit when modifying this module's features. |
| `tests/test_stream_and_staged_fixes.py` | 456 | Unit tests for StreamCoordinator dubbing fault tolerance, | `TestStreamCoordinatorDubbingFixes`, `TestSubtitleFilenameTagAccuracy`, `TestMediaOptionsBarAndStagedCard` | Edit when modifying this module's features. |
| `tests/test_subtitle_style_engine_all.py` | 140 | Module implementation for Smart Download. | `TestSubtitleStyleEngineComprehensive` | Edit when modifying this module's features. |
| `tests/test_updater.py` | 562 | Unit tests for AppAutoUpdater, YtDlpAutoUpdater, and version unification. | `_MockHttpResp`, `TestVersionComparisonAndUnification`, `TestYtDlpAutoUpdater`, `TestAppAutoUpdaterAndModal` | Edit when testing app/yt-dlp auto-updates or version comparison. |
| `tests/test_url_resolver.py` | 725 | Unit tests for URL utilities, filename sanitization, and speed formatting. | `MockRefreshLinkServerHandler`, `TestRefreshExpiredLinks`, `TestSpeedFormatting`, `setUpModule()`, `tearDownModule()` | Edit when testing URL manipulation and parsing utilities. |
| `tests/test_visual_defects_fix.py` | 297 | Unit tests for visual defects fix: | `TestVisualDefectsFix` | Edit when modifying this module's features. |
| `tests/test_windowed_range_and_warnings.py` | 1241 | Tests for Windowed Range Proxy, Clipboard URL Sniffing Fixes, and 32 Connections Warning. | `TestWindowedRangeAndWarnings` | Edit when modifying this module's features. |
| `tests/test_youtube_extract.py` | 798 | Unit tests for YouTube and social media link extraction with yt-dlp. | `TestYouTubeDetectionAndSanitization`, `TestYouTubeResolver`, `TestSocialMediaDetectionAndSanitization`, `TestSocialMediaResolverAndExtraction`, `TestVideoQualityFormatExtraction`, `setUpModule()`, `tearDownModule()` | Edit when testing social media stream resolution. |
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
