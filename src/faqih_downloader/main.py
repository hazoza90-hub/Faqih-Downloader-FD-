"""
Smart Download entry point script.
"""
import sys
import os

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

def main():
    if "--preview-html" in sys.argv:
        try:
            idx = sys.argv.index("--preview-html")
            if idx + 1 < len(sys.argv):
                html_target = sys.argv[idx + 1]
                from faqih_downloader.ui.modals.video_preview_modal import _launch_webview_subprocess
                _launch_webview_subprocess(html_target)
        except Exception:
            pass
        os._exit(0)
        return
    from faqih_downloader.services.single_instance import early_single_instance_guard
    early_single_instance_guard()
    from faqih_downloader.ui.main_window import main as gui_main
    gui_main()

if __name__ == "__main__":
    main()
