# -*- coding: utf-8 -*-
"""
PyInstaller entry-point for Faqih Downloader (FD) | فقيه التنزيلات.
Maintained in scripts/ to avoid module/package name collisions with src/faqih_downloader.
"""
import sys
import os
import time

# Ensure src/ directory is available in sys.path when running unbundled
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_base_dir, "src")
if os.path.isdir(_src_dir) and _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# 1. Fast-path for --test-startup verification
if "--test-startup" in sys.argv:
    t0 = time.time()
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
            f.write(
                f"ytdlp_res={t1-t0:.2f}s, bridge={t2-t1:.2f}s, nat={t3-t2:.2f}s, "
                f"reg={t4-t3:.2f}s, ytdlp={t5-t4:.2f}s, avail={t6-t5:.2f}s, total={t6-t0:.2f}s\n"
            )
    except Exception:
        pass
    if not avail:
        sys.stderr.write("[STARTUP TEST FAILED] yt-dlp is not available\n")
        sys.stderr.flush()
        os._exit(1)

    try:
        from faqih_downloader.config import get_resource_path
        png_path = get_resource_path("app_icon.png")
        ico_path = get_resource_path("app_icon.ico")
        if not (os.path.isfile(png_path) and os.path.isfile(ico_path)):
            sys.stderr.write(
                f"[STARTUP TEST FAILED] Icons missing: png='{png_path}' (exists={os.path.isfile(png_path)}), "
                f"ico='{ico_path}' (exists={os.path.isfile(ico_path)})\n"
            )
            sys.stderr.flush()
            os._exit(1)

        from PIL import Image, ImageTk
        with Image.open(png_path) as _img:
            _img.load()

        from faqih_downloader.services.media_env_helpers import find_ffmpeg_bin
        find_ffmpeg_bin()

        from faqih_downloader.ui.main_window import ModernFramelessGUI
        from faqih_downloader.ui.panels.kanban_staged_helpers import build_staged_link_card
        from faqih_downloader.ui.panels.kanban_card_graphics import _extract_and_load_video_thumbnail
    except Exception as e:
        sys.stderr.write(f"[STARTUP TEST FAILED] Integrity check error: {e}\n")
        sys.stderr.flush()
        os._exit(1)

    os._exit(0)

# 2. Subprocess handler for standalone --preview-html window
if "--preview-html" in sys.argv:
    try:
        idx = sys.argv.index("--preview-html")
        if idx + 1 < len(sys.argv):
            from faqih_downloader.ui.modals.video_preview_modal import _launch_webview_subprocess
            _launch_webview_subprocess(sys.argv[idx + 1])
    except Exception:
        pass
    os._exit(0)

# 3. Fast-path for uninstaller execution
if any(arg.lower() in ("--uninstall", "-uninstall", "/uninstall", "/u", "-u", "--uninstall-gui", "--uninstall-worker") for arg in sys.argv[1:]):
    from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli
    handle_uninstall_cli()
    os._exit(0)

# 4. Initialize Dynamic Core Loader (Zero-Rebuild Dev Mode & OTA Hot-Patch Plugin)
try:
    from faqih_downloader.services.core_patch_updater import init_core_loader
    init_core_loader()
except Exception:
    pass

# 5. Early Single-Instance Mutex Check: import before heavy modules (Tkinter, PIL, pystray, yt-dlp)
from faqih_downloader.services.single_instance import early_single_instance_guard
if __name__ == "__main__":
    early_single_instance_guard()

# 6. Initialize DPI awareness
from faqih_downloader.utils.dpi import enable_high_dpi_awareness
enable_high_dpi_awareness()

# 7. Start Main GUI
from faqih_downloader.ui.main_window import main

if __name__ == "__main__":
    main()
