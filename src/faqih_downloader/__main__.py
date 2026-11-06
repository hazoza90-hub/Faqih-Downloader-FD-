"""
Package CLI entry point for Faqih Downloader: python -m faqih_downloader.
"""
import sys
import os
import time

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
        os._exit(1)
    os._exit(0)

# 2. Subprocess handler for standalone --preview-html window
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

# 3. Fast-path for uninstaller execution
if any(arg.lower() in ("--uninstall", "-uninstall", "/uninstall", "/u", "-u", "--uninstall-gui") for arg in sys.argv[1:]):
    from faqih_downloader.installer.uninstaller_runner import handle_uninstall_cli
    handle_uninstall_cli()
    os._exit(0)

# 4. Initialize Dynamic Core Loader (Zero-Rebuild Dev Mode & OTA Hot-Patch Plugin)
try:
    from faqih_downloader.services.core_patch_updater import init_core_loader
    init_core_loader()
except Exception:
    pass

# 5. Early Single-Instance Mutex Check
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
