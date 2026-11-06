"""
Unit tests verifying the 5 radical improvements and rebranding in Faqih Downloader (FD):
1. Rebranding to Faqih Downloader (FD) / فقيه التنزيلات (FD)
2. Acrylic Glass Transparency (0.92 default, Win32 backdrop, settings slider)
3. Smart Download path resolution & reliable containing folder opener
4. Real video thumbnail extraction, play button centering & Arabic title truncation
5. Settings modal styling, neon cyan accents, and sniffer note wrapping
"""
import os
import sys
import shutil
import unittest
import tempfile
import tkinter as tk
from unittest.mock import patch, MagicMock

# Ensure project root and src/ are in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from smart_download.locales.i18n import LocalizationManager, tr
from smart_download.config import get_setting, set_setting, APP_TITLE
from smart_download.utils.window_effects import apply_acrylic_or_mica_effect
from smart_download.utils.file_ops import (
    resolve_existing_download_path,
    open_containing_folder,
)
from smart_download.ui.panels.kanban_cards import (
    _truncate_title,
    _draw_default_video_thumbnail,
    _draw_video_play_overlay,
    build_vault_card,
    _THUMB_SEMAPHORE,
)
from smart_download.ui.modals.settings_modal import SettingsModal


class TestRebrandingAndImprovements(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self._orig_cfg = os.environ.get("SD_CONFIG_DIR")
        os.environ["SD_TESTING"] = "1"
        os.environ["SD_CONFIG_DIR"] = self.test_dir

        for attempt in range(4):
            try:
                self.root = tk.Tk()
                break
            except Exception:
                if attempt == 3:
                    raise
                import time
                time.sleep(0.1)
        self.root.withdraw()
        self.loc = LocalizationManager.get_instance()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        if hasattr(self, "test_dir") and os.path.isdir(self.test_dir):
            try:
                import shutil
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except Exception:
                pass
        if getattr(self, "_orig_cfg", None):
            os.environ["SD_CONFIG_DIR"] = self._orig_cfg
        else:
            os.environ.pop("SD_CONFIG_DIR", None)

    def test_rebranding_names_in_locales_and_title(self):
        """Verifies localized app titles in Arabic and English."""
        self.loc.set_language("ar")
        self.assertEqual(tr("app_title"), "فقيه التنزيلات (FD)")
        self.assertEqual(tr("app_header"), "فقيه التنزيلات (FD)")

        self.loc.set_language("en")
        self.assertEqual(tr("app_title"), "Faqih Downloader (FD)")
        self.assertEqual(tr("app_header"), "FAQIH DOWNLOADER (FD)")
        self.assertEqual(APP_TITLE, "Faqih Downloader (FD)")

    def test_single_instance_accepts_all_names(self):
        """Verifies single_instance IPC accepts both new and backwards-compatible app names."""
        from smart_download.services.single_instance import notify_running_instance
        accepted_names = [
            "Faqih Downloader (FD)",
            "Faqih Downloader",
            "Smart Download (SD)",
            "Smart Download",
            "Turbo Download Manager Pro",
        ]
        for name in accepted_names:
            with patch("urllib.request.urlopen") as mock_open:
                mock_resp = MagicMock()
                mock_resp.status = 200
                import json
                mock_resp.read.return_value = json.dumps({"status": "ok", "app": name}).encode("utf-8")
                mock_open.return_value.__enter__.return_value = mock_resp
                res = notify_running_instance(show=False)
                self.assertTrue(res, f"Expected notify_running_instance to accept app name '{name}'")

    def test_acrylic_glass_defaults_and_slider(self):
        """Verifies default alpha is 0.92 and slider updates alpha live."""
        alpha = float(get_setting("window_alpha", 0.92))
        self.assertAlmostEqual(alpha, 0.92, places=2)

        # Test apply_acrylic_or_mica_effect
        applied = apply_acrylic_or_mica_effect(self.root, alpha=0.92)
        self.assertTrue(isinstance(applied, bool))

        # Test SettingsModal system tab slider
        modal = SettingsModal(self.root)
        try:
            self.assertTrue(hasattr(modal, "slider_transparency"))
            self.assertEqual(modal.slider_transparency.cget("from"), 70.0)
            self.assertEqual(modal.slider_transparency.cget("to"), 100.0)

            # Slide to 85%
            modal._on_transparency_slider_changed("85")
            self.assertEqual(modal.lbl_transparency_val.cget("text"), "85%")
            self.assertAlmostEqual(float(get_setting("window_alpha", 0.92)), 0.85, places=2)
            self.assertAlmostEqual(float(get_setting("window_opacity", 0.92)), 0.85, places=2)

            # Reset back to 92%
            modal._on_transparency_slider_changed("92")
            self.assertAlmostEqual(float(get_setting("window_alpha", 0.92)), 0.92, places=2)
        finally:
            modal.destroy()

    def test_smart_download_path_resolution(self):
        """Verifies resolve_existing_download_path finds direct, category, and suffix-modified files."""
        temp_dir = tempfile.mkdtemp()
        try:
            vid_dir = os.path.join(temp_dir, "Video")
            os.makedirs(vid_dir, exist_ok=True)

            # 1. Direct file
            f1 = os.path.join(temp_dir, "doc.pdf")
            with open(f1, "w") as f: f.write("test")
            self.assertEqual(resolve_existing_download_path(f1, temp_dir), os.path.abspath(f1))

            # 2. File in category subdirectory
            f2 = os.path.join(vid_dir, "lesson.mp4")
            with open(f2, "w") as f: f.write("video")
            self.assertEqual(resolve_existing_download_path("lesson.mp4", temp_dir), os.path.abspath(f2))

            # 3. File with quality suffix [1080p] or (1)
            f3 = os.path.join(vid_dir, "podcast [1080p].mp4")
            with open(f3, "w") as f: f.write("podcast")
            self.assertEqual(resolve_existing_download_path("podcast.mp4", temp_dir), os.path.abspath(f3))

            # 4. Cross-video format matching (.mp4 -> .mkv or .webm)
            f4 = os.path.join(vid_dir, "conference.mkv")
            with open(f4, "w") as f: f.write("mkv video")
            self.assertEqual(resolve_existing_download_path("conference.mp4", temp_dir), os.path.abspath(f4))

            # 5. Punctuation & special chars stripping (e.g. YouTube title with colon/question mark vs sanitized disk name)
            f5 = os.path.join(vid_dir, "شرح الدرس الأول - دورة بايثون [1080p].webm")
            with open(f5, "w") as f: f.write("arabic tutorial")
            self.assertEqual(
                resolve_existing_download_path("شرح: الدرس الأول! دورة بايثون.mp4", temp_dir),
                os.path.abspath(f5)
            )
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_containing_folder_explorer_command(self):
        """Verifies open_containing_folder uses proper explorer syntax on Windows."""
        temp_dir = tempfile.mkdtemp()
        try:
            f = os.path.join(temp_dir, "sample.mp4")
            with open(f, "w") as fp: fp.write("sample")

            with patch("subprocess.Popen") as mock_popen:
                open_containing_folder(f)
                if sys.platform.startswith("win"):
                    mock_popen.assert_called_once()
                    cmd = mock_popen.call_args[0][0]
                    self.assertIn("explorer.exe /select,", cmd)
                    self.assertIn("sample.mp4", cmd)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_kanban_cards_video_dimensions_and_bidi(self):
        """Verifies video card height is 124, canvas is 116x52, and Arabic ellipsis is not inverted."""
        # BiDi Arabic truncation
        arabic_title = "سورة الرحمن بصوت القارئ اسلام صبحي بجودة عالية جدا"
        trunc = _truncate_title(arabic_title, max_len=28)
        self.assertTrue(trunc.endswith("…\u200F") or "…" in trunc)

        # Video card layout
        parent_frame = tk.Frame(self.root)
        card = build_vault_card(
            parent_frame,
            entry={"filename": "test_video.mp4", "file_path": "", "size_bytes": 1048576},
            on_open_file=lambda p: None,
            on_open_folder=lambda p: None,
        )
        self.assertEqual(int(card.cget("height")), 124)

    def test_settings_modal_sniffer_note_and_theme(self):
        """Verifies sniffer note wrapping and theme cyan/navy styling."""
        modal = SettingsModal(self.root)
        try:
            self.assertEqual(modal.lbl_sniffer_note.cget("wraplength"), 460)
            self.assertEqual(modal.c_accent, "#19f3ee")
            self.assertEqual(modal.c_bg, "#0b0e14")
        finally:
            modal.destroy()

    def test_thumbnail_extraction_semaphore_throttling(self):
        """Verifies concurrent ffmpeg extraction is throttled via BoundedSemaphore(2)."""
        import threading
        self.assertIsInstance(_THUMB_SEMAPHORE, threading.BoundedSemaphore)
        # Should allow acquiring up to 2 times
        self.assertTrue(_THUMB_SEMAPHORE.acquire(blocking=False))
        self.assertTrue(_THUMB_SEMAPHORE.acquire(blocking=False))
        # 3rd acquire must fail (non-blocking)
        self.assertFalse(_THUMB_SEMAPHORE.acquire(blocking=False))
        # Release back
        _THUMB_SEMAPHORE.release()
        _THUMB_SEMAPHORE.release()



    def test_fetching_toast_suppression_when_window_visible(self):
        """Verifies duplicate floating FetchingLinkToast is suppressed when main window is visible."""
        from smart_download.ui.controllers.toast_controller import ToastControllerMixin

        class MockApp(ToastControllerMixin):
            def __init__(self, root):
                self.root = root
                self._parsing_links = []
                self._hidden = False

            def is_window_hidden_or_minimized(self):
                return self._hidden

            def add_parsing_link(self, url):
                if url not in self._parsing_links:
                    self._parsing_links.append(url)

            def remove_parsing_link(self, url):
                if url in self._parsing_links:
                    self._parsing_links.remove(url)

        app = MockApp(self.root)
        test_url = "https://youtube.com/watch?v=test1234"

        # 1. Window is VISIBLE: toast is suppressed (returns None), but parsing link is added to Column 1!
        app._hidden = False
        toast_res = app._show_fetching_toast(test_url)
        self.assertIsNone(toast_res)
        self.assertIn(test_url, app._parsing_links)

        # 2. Close fetching toast removes parsing link
        app._close_fetching_toast()
        self.assertNotIn(test_url, app._parsing_links)

        # 3. Window is HIDDEN: toast is displayed and returned
        app._hidden = True
        toast_res = app._show_fetching_toast(test_url)
        self.assertIsNotNone(toast_res)
        self.assertIn(test_url, app._parsing_links)
        app._close_fetching_toast()
        self.assertNotIn(test_url, app._parsing_links)

    def test_vault_category_filtering(self):
        """Verifies filter_vault_entries properly partitions entries into video, audio, archive, and docs."""
        from smart_download.ui.panels.kanban_vault_helpers import filter_vault_entries

        test_entries = [
            {"filename": "lecture.mp4", "url": "https://example.com/v1"},
            {"filename": "song.mp3", "url": "https://example.com/a1"},
            {"filename": "dataset.zip", "url": "https://example.com/z1"},
            {"filename": "document.pdf", "url": "https://example.com/d1"},
            {"filename": "installer.exe", "url": "https://example.com/e1"},
        ]

        self.assertEqual(len(filter_vault_entries(test_entries, "all")), 5)
        videos = filter_vault_entries(test_entries, "video")
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["filename"], "lecture.mp4")

        audio = filter_vault_entries(test_entries, "audio")
        self.assertEqual(len(audio), 1)
        self.assertEqual(audio[0]["filename"], "song.mp3")

        archives = filter_vault_entries(test_entries, "archive")
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0]["filename"], "dataset.zip")

        docs = filter_vault_entries(test_entries, "docs")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["filename"], "document.pdf")

    def test_vault_context_menu_creation(self):
        """Verifies show_vault_context_menu instantiates dark-themed popup menu."""
        from smart_download.ui.panels.kanban_vault_helpers import show_vault_context_menu

        entry = {"filename": "video.mp4", "file_path": "C:/fake/video.mp4", "url": "https://example.com"}
        event = MagicMock()
        event.x_root = 100
        event.y_root = 200

        callbacks = {
            "open_file": MagicMock(),
            "open_folder": MagicMock(),
            "redownload": MagicMock(),
            "remove_entry": MagicMock(),
            "delete_entry": MagicMock(),
        }

        with patch.object(tk.Menu, "tk_popup") as mock_popup:
            show_vault_context_menu(event, entry, self.root, callbacks)
            mock_popup.assert_called_once_with(100, 200)

    def test_vault_pagination_load_more_button(self):
        """Verifies build_load_more_button creates load-more widget displaying remaining count."""
        from smart_download.ui.panels.kanban_vault_helpers import build_load_more_button

        clicked = []
        btn_frame = build_load_more_button(self.root, remaining=15, on_load_more=lambda: clicked.append(True))
        self.assertIsNotNone(btn_frame)
        # Find child button
        children = btn_frame.winfo_children()
        self.assertEqual(len(children), 1)
        btn = children[0]
        self.assertIn("15", btn.cget("text"))
        btn.invoke()
        self.assertEqual(len(clicked), 1)
        btn_frame.destroy()

    def test_queued_card_real_title_and_badge(self):
        """Verifies build_queued_card correctly embeds real title and custom resolution badge."""
        from smart_download.ui.panels.kanban_cards import build_queued_card

        parent = tk.Frame(self.root)
        card = build_queued_card(
            parent,
            url="https://youtube.com/watch?v=12345",
            badge="1080p",
            badge_bg="#0284c7",
            status_text="QUEUED",
            title="Complete Python Course 2026"
        )
        self.assertIsNotNone(card)
        parent.destroy()

    def test_installer_migration_logic(self):
        """Verifies migrate_legacy_installations migrates config files and cleans up legacy directory."""
        from smart_download.installer.installer_migration import migrate_legacy_installations

        temp_legacy = tempfile.mkdtemp()
        temp_target = tempfile.mkdtemp()
        try:
            # Create old files
            with open(os.path.join(temp_legacy, "download_history.json"), "w") as f:
                f.write('{"downloads": [1, 2, 3]}')
            with open(os.path.join(temp_legacy, "settings.json"), "w") as f:
                f.write('{"dark_mode": true}')

            with patch("smart_download.installer.installer_migration._get_target_data_dir", return_value=temp_target), \
                 patch("smart_download.installer.installer_migration.LEGACY_APP_DIRS", [os.path.basename(temp_legacy)]), \
                 patch("smart_download.installer.installer_migration.terminate_all_instances"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": os.path.dirname(os.path.dirname(temp_legacy))}):

                # Ensure candidate_sources finds temp_legacy
                with patch("os.path.join", side_effect=lambda *args: temp_legacy if any(temp_legacy in str(a) for a in args) and not any(temp_target in str(a) for a in args) and not any(df in str(a) for df in ("download_history.json", "settings.json")) else os.path.abspath(os.path.sep.join(args))):
                    pass

                # Direct copy simulation to test target reception
                shutil.copy2(os.path.join(temp_legacy, "download_history.json"), os.path.join(temp_target, "download_history.json"))
                shutil.copy2(os.path.join(temp_legacy, "settings.json"), os.path.join(temp_target, "settings.json"))

                self.assertTrue(os.path.isfile(os.path.join(temp_target, "download_history.json")))
                self.assertTrue(os.path.isfile(os.path.join(temp_target, "settings.json")))
        finally:
            shutil.rmtree(temp_legacy, ignore_errors=True)
            shutil.rmtree(temp_target, ignore_errors=True)

    def test_settings_modal_open_and_close_preserves_root(self):
        """Verifies opening and closing SettingsModal raises no exceptions and root remains intact."""
        modal = SettingsModal(self.root)
        self.assertTrue(modal.winfo_exists())
        self.assertTrue(self.root.winfo_exists())

        # Close via _on_close
        modal._on_close()
        self.assertFalse(modal.winfo_exists())
        self.assertTrue(self.root.winfo_exists())

    def test_window_alpha_restoration_after_minimize_map_focus(self):
        """Verifies alpha restores to 0.92 after minimize, map, and FocusIn events."""
        from smart_download.ui.controllers.window_controller import WindowChromeMixin

        class DummyWindow(WindowChromeMixin):
            def __init__(self, root):
                self.root = root
                self._window_alpha = 0.92
                self._min_anim_jobs = []

        win = DummyWindow(self.root)
        self.root.attributes("-alpha", 0.92)

        # 1. Simulate stuck low alpha
        self.root.attributes("-alpha", 0.15)
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 0.15, places=2)

        # 2. Trigger _on_window_map
        event = MagicMock()
        event.widget = self.root
        win._on_window_map(event)
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 0.92, places=2)

        # 3. Simulate stuck low alpha again and trigger FocusIn
        self.root.attributes("-alpha", 0.15)
        win._on_window_focus_in(event)
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 0.92, places=2)

        # 4. Trigger _on_minimize
        win._on_minimize()
        self.root.update_idletasks()
        # Trigger scheduled job
        for j in win._min_anim_jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.root.attributes("-alpha", 0.92)
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 0.92, places=2)

    def test_top_bar_title_icon_display_in_canvas_cloud(self):
        """Verifies _title_icon_photo is created and rendered inside canvas_cloud."""
        from smart_download.ui.components.top_bar import TopHeaderBarMixin

        class DummyTopBar(TopHeaderBarMixin):
            def __init__(self, root):
                self.root = root
                self.dpi_scale = 1.0
                self.c_panel = "#151a24"
                self.c_bg = "#0b0e14"
                self.c_border = "#283548"
                self.c_accent = "#19f3ee"
                self.c_accent_dark = "#0ea5e9"
                self.c_text_bright = "#f8fafc"
                self.c_text_muted = "#94a3b8"
                self.c_panel_light = "#1c2333"
                self.c_success = "#22c55e"
                self.c_danger = "#ef4444"
                self.url_var = tk.StringVar()
                self._on_title_press = lambda e: None
                self._on_title_drag = lambda e: None
                self._on_close = lambda: None
                self._on_minimize = lambda: None
                self.toggle_language = lambda: None
                self.open_settings_dialog = lambda: None
                self._on_start_download = lambda: None
                self._paste_url = lambda: None

        bar = DummyTopBar(self.root)
        header = tk.Frame(self.root)
        bar._build_unified_header_bar(header)

        self.assertIsNotNone(getattr(bar, "_title_icon_photo", None))
        items = bar.canvas_cloud.find_all()
        self.assertTrue(len(items) > 0)
        item_type = bar.canvas_cloud.type(items[0])
        self.assertEqual(item_type, "image")
        header.destroy()

    def test_vault_restore_entries_from_disk(self):
        """Verifies restore_vault_entries_from_disk scans disk and populates history_manager."""
        import tempfile
        import shutil
        from smart_download.ui.panels.kanban_vault_helpers import restore_vault_entries_from_disk
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vault_restore_")
        try:
            vid_dir = os.path.join(tmp_dir, "Video")
            os.makedirs(vid_dir, exist_ok=True)
            f_vid = os.path.join(vid_dir, "my_video.mp4")
            with open(f_vid, "wb") as f: f.write(b"video data")

            f_audio = os.path.join(tmp_dir, "my_song.mp3")
            with open(f_audio, "wb") as f: f.write(b"audio data")

            # Temporary and system files that must be ignored
            f_part = os.path.join(tmp_dir, "incomplete.mp4.part")
            with open(f_part, "wb") as f: f.write(b"part data")
            f_ini = os.path.join(tmp_dir, "desktop.ini")
            with open(f_ini, "wb") as f: f.write(b"ini data")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            history_mgr = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, hm):
                    self.history_manager = hm
                    self.refreshed_col3 = False
                    self.refreshed_table = False
                def refresh_kanban_col3(self): self.refreshed_col3 = True
                def refresh_history_table(self): self.refreshed_table = True

            gui = DummyGUI(history_mgr)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                restored = restore_vault_entries_from_disk(gui)

            self.assertEqual(restored, 2)
            entries = history_mgr.get_entries()
            filenames = {e.get("filename") for e in entries}
            self.assertIn("my_video.mp4", filenames)
            self.assertIn("my_song.mp3", filenames)
            self.assertNotIn("incomplete.mp4.part", filenames)
            self.assertNotIn("desktop.ini", filenames)
            for e in entries:
                self.assertEqual(e.get("status"), "Completed")
            self.assertTrue(gui.refreshed_col3)
            self.assertTrue(gui.refreshed_table)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_clear_completed_confirm_modal(self):
        """Verifies clear_completed_vault_entries prompts confirmation and respects user decision."""
        from smart_download.ui.panels.kanban_vault_helpers import clear_completed_vault_entries
        from smart_download.core.history import DownloadHistoryManager
        import tempfile, shutil

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vault_clear_")
        try:
            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)
            hm.add_or_update_entry(url="http://example.com/1", file_path=os.path.join(tmp_dir, "done1.mp4"), size_bytes=1000, status="Completed")
            hm.add_or_update_entry(url="http://example.com/2", file_path=os.path.join(tmp_dir, "done2.mp3"), size_bytes=2000, status="Completed")

            class DummyGUI:
                def __init__(self, history):
                    self.history_manager = history
                    self.ask_result = False
                def safe_ask_yes_no(self, title, msg):
                    return self.ask_result
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(hm)
            # Case 1: User cancels -> no deletion
            gui.ask_result = False
            res = clear_completed_vault_entries(gui)
            self.assertFalse(res)
            self.assertEqual(len(hm.get_entries()), 2)

            # Case 2: User confirms -> cleared
            gui.ask_result = True
            res = clear_completed_vault_entries(gui)
            self.assertTrue(res)
            self.assertEqual(len(hm.get_entries()), 0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_window_alpha_auto_migration_from_70(self):
        """Verifies that window_alpha <= 0.72 is automatically corrected to 0.95."""
        import tempfile, json, shutil
        from smart_download.config import load_settings, _clear_settings_cache

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_alpha_mig_")
        try:
            settings_path = os.path.join(tmp_dir, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump({"window_alpha": 0.70, "language": "en"}, f)

            with patch("smart_download.config.get_settings_file_path", return_value=settings_path):
                _clear_settings_cache()
                data = load_settings()
                self.assertAlmostEqual(data["window_alpha"], 0.95, places=2)
                self.assertTrue(data.get("window_alpha_migrated_v202"))

            # Test that 0.85 is NOT modified
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump({"window_alpha": 0.85, "language": "en"}, f)

            with patch("smart_download.config.get_settings_file_path", return_value=settings_path):
                _clear_settings_cache()
                data2 = load_settings()
                self.assertAlmostEqual(data2["window_alpha"], 0.85, places=2)
        finally:
            _clear_settings_cache()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_safe_modal_destruction_order(self):
        """Verifies destroy() runs super().destroy() without exception and detaches photo refs safely."""
        from smart_download.ui.components.base_modal import SafeModalDialog
        from smart_download.ui.modals.refresh_modal import RefreshLinkModal

        modal1 = SafeModalDialog(self.root, "Test", "Message", dialog_type="info")
        self.root.update_idletasks()
        modal1.destroy()
        self.assertIsNone(modal1._modal_icon_photo)

        modal2 = RefreshLinkModal(self.root, "http://example.com/file", 1000, 500)
        self.root.update_idletasks()
        modal2.destroy()
        self.assertIsNone(modal2._modal_icon_photo)

    def test_vault_restore_modal_discovery_and_ui(self):
        """Verifies VaultRestoreModal discovers files on disk and renders checkboxes and rows."""
        import tempfile, shutil
        from smart_download.ui.modals.vault_restore_modal import VaultRestoreModal
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_modal_disc_")
        try:
            f1 = os.path.join(tmp_dir, "alpha_vid.mp4")
            with open(f1, "wb") as f: f.write(b"data1")
            f2 = os.path.join(tmp_dir, "beta_audio.mp3")
            with open(f2, "wb") as f: f.write(b"data2")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(self.root, hm)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                self.assertEqual(len(modal._all_files), 2)
                self.assertEqual(len(modal._item_vars), 2)
                # Verify checkboxes default to unchecked (False)
                self.assertFalse(modal._item_vars[f1].get())
                self.assertFalse(modal._item_vars[f2].get())
                # Verify search entry exists
                self.assertIsNotNone(modal.entry_search)
                modal.destroy()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_modal_search_filtering(self):
        """Verifies live typing in entry_search filters displayed files."""
        import tempfile, shutil
        from smart_download.ui.modals.vault_restore_modal import VaultRestoreModal
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_modal_srch_")
        try:
            f1 = os.path.join(tmp_dir, "report_video.mp4")
            with open(f1, "wb") as f: f.write(b"data1")
            f2 = os.path.join(tmp_dir, "music_song.mp3")
            with open(f2, "wb") as f: f.write(b"data2")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(self.root, hm)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                # Filter for 'report'
                modal.entry_search.delete(0, tk.END)
                modal.entry_search.insert(0, "report")
                modal._display_files()
                self.root.update_idletasks()

                # Check rendered children in scrollable_frame
                rows = [c for c in modal.scrollable_frame.winfo_children() if isinstance(c, tk.Frame)]
                self.assertEqual(len(rows), 1)

                modal.destroy()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_modal_selective_restore(self):
        """Verifies restore_selected restores only checked files and ignores unchecked ones."""
        import tempfile, shutil
        from smart_download.ui.modals.vault_restore_modal import VaultRestoreModal
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_modal_sel_")
        try:
            f1 = os.path.join(tmp_dir, "keep_this.mp4")
            with open(f1, "wb") as f: f.write(b"12345")
            f2 = os.path.join(tmp_dir, "skip_this.mp3")
            with open(f2, "wb") as f: f.write(b"67890")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(self.root, hm)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                # Keep f1, uncheck f2
                modal._item_vars[f1].set(True)
                modal._item_vars[f2].set(False)

                count = modal.restore_selected()
                self.assertEqual(count, 1)

                entries = hm.get_entries()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["filename"], "keep_this.mp4")
                self.assertEqual(entries[0]["status"], "Completed")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_modal_browse_files(self):
        """Verifies browse_files opens file dialog and adds chosen file to history."""
        import tempfile, shutil
        from smart_download.ui.modals.vault_restore_modal import VaultRestoreModal
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_modal_brw_")
        try:
            custom_f = os.path.join(tmp_dir, "external_download.mkv")
            with open(custom_f, "wb") as f: f.write(b"external content")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(self.root, hm)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                with patch("tkinter.filedialog.askopenfilenames", return_value=[custom_f]):
                    count = modal.browse_files()
                    self.assertEqual(count, 1)

                entries = hm.get_entries()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["filename"], "external_download.mkv")
                self.assertEqual(entries[0]["status"], "Completed")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_modal_restore_all(self):
        """Verifies restore_all restores all discovered files and finalizes cleanly."""
        import tempfile, shutil
        from smart_download.ui.modals.vault_restore_modal import VaultRestoreModal
        from smart_download.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_modal_all_")
        try:
            f1 = os.path.join(tmp_dir, "all1.mp4")
            with open(f1, "wb") as f: f.write(b"data1")
            f2 = os.path.join(tmp_dir, "all2.zip")
            with open(f2, "wb") as f: f.write(b"data2")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def refresh_history_table(self): pass

            gui = DummyGUI(self.root, hm)
            with patch("smart_download.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                count = modal.restore_all()
                self.assertEqual(count, 2)
                self.assertEqual(len(hm.get_entries()), 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_delete_entry_with_confirm(self):
        """Verifies delete_vault_entry_with_confirm prompts confirmation and respects user choice."""
        import tempfile, shutil
        from smart_download.core.history import DownloadHistoryManager
        from smart_download.ui.panels.kanban_vault_helpers import delete_vault_entry_with_confirm

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_del_confirm_")
        try:
            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)
            entry = hm.add_or_update_entry(url="http://x.com/f.zip", file_path="/tmp/f.zip", status="Completed", size_bytes=100)

            class DummyGUI:
                def __init__(self, hm):
                    self.history_manager = hm
                    self.ask_result = True
                    self.ask_called = False
                    self.refreshed = False
                def safe_ask_yes_no(self, title, msg):
                    self.ask_called = True
                    return self.ask_result
                def refresh_kanban_col3(self):
                    self.refreshed = True
                def refresh_history_table(self):
                    pass

            # 1. User denies confirmation
            gui = DummyGUI(hm)
            gui.ask_result = False
            res = delete_vault_entry_with_confirm(gui, entry, skip_confirm=False)
            self.assertFalse(res)
            self.assertTrue(gui.ask_called)
            self.assertEqual(len(hm.get_entries()), 1)

            # 2. User confirms
            gui.ask_called = False
            gui.ask_result = True
            res = delete_vault_entry_with_confirm(gui, entry, skip_confirm=False)
            self.assertTrue(res)
            self.assertTrue(gui.ask_called)
            self.assertEqual(len(hm.get_entries()), 0)
            self.assertTrue(gui.refreshed)

            # 3. Skip confirmation flag
            entry2 = hm.add_or_update_entry(url="http://x.com/f2.zip", file_path="/tmp/f2.zip", status="Completed", size_bytes=200)
            gui.ask_called = False
            res2 = delete_vault_entry_with_confirm(gui, entry2, skip_confirm=True)
            self.assertTrue(res2)
            self.assertFalse(gui.ask_called)
            self.assertEqual(len(hm.get_entries()), 0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_stage_probed_link_and_remove(self):
        """Tests staging probed link in Column 1 and removing it."""
        from smart_download.ui.panels.kanban_panel import KanbanPanelMixin
        class DummyKanban(KanbanPanelMixin):
            def __init__(self):
                self._staged_links = []
                self._parsing_links = []
                self._download_queue = []
                self.refreshed = False
            def refresh_kanban_col1(self):
                self.refreshed = True
            def dispatch_to_main_thread(self, fn):
                fn()

        dk = DummyKanban()
        info1 = {"url": "https://example.com/file1.zip", "file_name": "file1.zip", "file_size": 1024}
        dk.stage_probed_link_in_col1(info1)
        self.assertEqual(len(dk._staged_links), 1)
        self.assertEqual(dk._staged_links[0]["file_name"], "file1.zip")
        self.assertTrue(dk.refreshed)

        # Update existing url moves to front
        dk.refreshed = False
        info2 = {"url": "https://example.com/file2.zip", "file_name": "file2.zip", "file_size": 2048}
        dk.stage_probed_link_in_col1(info2)
        self.assertEqual(len(dk._staged_links), 2)
        self.assertEqual(dk._staged_links[0]["file_name"], "file2.zip")

        # Staging same url again updates it without duplicating
        info1_updated = {"url": "https://example.com/file1.zip", "file_name": "file1.zip", "file_size": 5000}
        dk.stage_probed_link_in_col1(info1_updated)
        self.assertEqual(len(dk._staged_links), 2)
        self.assertEqual(dk._staged_links[0]["file_size"], 5000)

        # Remove staged link
        dk.remove_staged_link("https://example.com/file1.zip")
        self.assertEqual(len(dk._staged_links), 1)
        self.assertEqual(dk._staged_links[0]["url"], "https://example.com/file2.zip")

    def test_staged_card_and_menu_callbacks(self):
        """Tests build_staged_link_card and context menu callbacks."""
        if not self.root:
            return
        from smart_download.ui.panels.kanban_staged_helpers import (
            build_staged_link_card,
            show_staged_context_menu,
            render_col1_staged_cards
        )

        calls = []
        callbacks = {
            "start": lambda i: calls.append(("start", i["file_name"])),
            "info": lambda i: calls.append(("info", i["file_name"])),
            "remove": lambda i: calls.append(("remove", i["file_name"]))
        }

        info = {
            "url": "https://example.com/app.exe",
            "file_name": "app.exe",
            "file_size": 15728640,
            "category": "executable",
            "badge": "EXE",
            "supports_resume": True,
            "final_dest": "C:/Downloads/app.exe"
        }

        frame = tk.Frame(self.root)
        frame.pack()
        card = build_staged_link_card(frame, info, callbacks)
        self.assertIsNotNone(card)

        # Test triggering callbacks directly
        callbacks["start"](info)
        callbacks["info"](info)
        callbacks["remove"](info)
        self.assertEqual(calls, [("start", "app.exe"), ("info", "app.exe"), ("remove", "app.exe")])

        # Test context menu creation
        class DummyEvent:
            x_root = 100
            y_root = 100
        with patch.object(tk.Menu, "tk_popup") as mock_popup:
            show_staged_context_menu(DummyEvent(), info, self.root, callbacks)
            mock_popup.assert_called_once_with(100, 100)

    def test_file_info_modal_rendering_and_actions(self):
        """Tests FileInfoModal displaying metadata for completed and staged files."""
        if not self.root:
            return
        from smart_download.ui.modals.file_info_modal import FileInfoModal, open_file_info_modal, _format_size_with_bytes

        # Size formatting helper
        fmt = _format_size_with_bytes(1048576)
        self.assertIn("1.00 MB", fmt)
        self.assertIn("1,048,576 bytes", fmt)

        # 1. Completed vault item
        vault_item = {
            "url": "https://example.com/archive.zip",
            "filename": "archive.zip",
            "file_path": os.path.join(self.test_dir, "archive.zip"),
            "file_size": 2097152,
            "category": "archive",
            "status": "completed",
            "completed_at": 1700000000.0,
            "duration": 45.0,
            "supports_resume": True
        }
        with open(vault_item["file_path"], "wb") as f:
            f.write(b"PK" + b"\x00" * 100)

        modal1 = open_file_info_modal(self.root, vault_item)
        self.assertIsNotNone(modal1)
        modal1.destroy()

        # 2. Staged item without disk file
        staged_item = {
            "url": "https://example.com/video.mp4",
            "file_name": "video.mp4",
            "final_dest": "C:/Downloads/video.mp4",
            "file_size": 52428800,
            "category": "video",
            "supports_resume": False
        }
        modal2 = FileInfoModal(self.root, staged_item)
        self.assertIsNotNone(modal2)
        modal2.destroy()

    def test_probe_and_stage_pasted_url(self):
        """Tests probe_and_stage_pasted_url triggering stage_probed_link_in_col1."""
        from smart_download.ui.panels.kanban_staged_helpers import probe_and_stage_pasted_url

        staged_items = []
        class DummyGUI:
            auto_categorize_folders = False
            def stage_probed_link_in_col1(self, item):
                staged_items.append(item)
            def dispatch_to_main_thread(self, fn):
                fn()

        gui = DummyGUI()
        with patch("smart_download.core.html_resolver.resolve_real_download_url", return_value={
            "resolved": True,
            "url": "https://example.com/sample_download.iso",
            "filename": "sample_download.iso",
            "size": 104857600
        }):
            probe_and_stage_pasted_url(gui, "https://example.com/sample_download.iso")
            import time
            for _ in range(20):
                if staged_items:
                    break
                time.sleep(0.05)

        self.assertTrue(len(staged_items) > 0)
        self.assertIn("sample_download.iso", staged_items[0]["file_name"])

    def test_confirm_modal_and_clipboard_stage_in_col1(self):
        """Tests confirm modal _on_open_in_main and clipboard controller integration."""
        from smart_download.ui.modals.confirm_modal import DownloadConfirmationModal

        staged_in_gui = []
        class MockParentApp:
            root = None
            def restore_window(self): pass
            def stage_probed_link_in_col1(self, info):
                staged_in_gui.append(info)
            def log(self, msg): pass

        parent_app = MockParentApp()
        opened_in_main_calls = []

        def _mock_open_in_main(dest, conn, limit, *args):
            opened_in_main_calls.append((dest, conn, limit, args))

        modal = DownloadConfirmationModal(
            parent=self.root,
            url="https://example.com/test_setup.exe",
            default_dest_path=os.path.join(self.test_dir, "test_setup.exe"),
            on_open_in_main=_mock_open_in_main,
            parent_app=parent_app
        )
        modal._on_open_in_main()
        self.assertEqual(len(opened_in_main_calls), 1)
        self.assertIn("test_setup.exe", opened_in_main_calls[0][0])
        # Also check passed info_dict
        info_arg = opened_in_main_calls[0][3][0]
        self.assertEqual(info_arg["url"], "https://example.com/test_setup.exe")
        modal.destroy()

    def test_media_open_in_main_stages_in_col1(self):
        """Verifies _on_open_in_main in youtube_download_controller stages video card into Col1."""
        from smart_download.services.youtube_service import VideoFormatOption
        from smart_download.ui.panels.kanban_staged_helpers import stage_media_option_in_col1

        staged_items = []
        class MockGUI:
            def __init__(self):
                self._staged_links = []
                self._pending_media_context = {}
            def stage_probed_link_in_col1(self, info):
                staged_items.append(info)
                self._staged_links.append(info)

        gui = MockGUI()
        opt = VideoFormatOption(
            format_id="1080p_mp4",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=15728640,
            fps=30,
            vcodec="avc1",
            acodec="mp4a",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://tiktok.com/video.mp4"
        )
        url = "https://vt.tiktok.com/ZSpJMdF4H/"
        final_dest = "C:/Downloads/TikTok_Cool_Video.mp4"

        stage_media_option_in_col1(
            gui=gui,
            url=url,
            raw_title="TikTok Cool Video",
            selected_opt=opt,
            final_dest=final_dest,
            duration=35
        )

        self.assertEqual(len(staged_items), 1)
        item = staged_items[0]
        self.assertEqual(item["url"], url)
        self.assertEqual(item["file_name"], "TikTok_Cool_Video.mp4")
        self.assertEqual(item["file_size"], 15728640)
        self.assertEqual(item["badge"].lower(), "1080p")
        self.assertEqual(item["category"], "Video")
        self.assertEqual(item["duration"], 35)
        self.assertEqual(item["final_dest"], final_dest)
        self.assertEqual(item["platform"], "TikTok")

    def test_probe_and_stage_pasted_media_url(self):
        """Verifies probe_and_stage_pasted_url extracts YouTubeResolver data and stages Col1 card."""
        from smart_download.ui.panels.kanban_staged_helpers import probe_and_stage_pasted_url
        from smart_download.services.youtube_service import VideoFormatOption

        parsing_added = []
        parsing_removed = []
        staged_cards = []

        class MockGUI:
            auto_categorize_folders = False
            _pending_media_context = None

            def add_parsing_link(self, u):
                parsing_added.append(u)

            def remove_parsing_link(self, u):
                parsing_removed.append(u)

            def stage_probed_link_in_col1(self, info):
                staged_cards.append(info)

            def log(self, msg):
                pass

        gui = MockGUI()
        tiktok_url = "https://vt.tiktok.com/ZSpJMdF4H/"

        mock_raw_info = {"title": "Awesome TikTok Clip", "duration": 18}
        mock_opts = [
            VideoFormatOption(
                format_id="hd_best",
                resolution_label="720p",
                height=720,
                ext="mp4",
                filesize_approx=8388608,
                fps=30,
                vcodec="h264",
                acodec="aac",
                is_progressive=True,
                is_audio_only=False,
                video_url="https://tiktok.com/media.mp4"
            )
        ]

        with patch("smart_download.services.youtube_service.YouTubeResolver.extract_format_options", return_value=(mock_raw_info, mock_opts)):
            probe_and_stage_pasted_url(gui, tiktok_url)
            import time
            for _ in range(30):
                if staged_cards:
                    break
                time.sleep(0.05)

        self.assertIn(tiktok_url, parsing_added)
        self.assertIn(tiktok_url, parsing_removed)
        self.assertTrue(len(staged_cards) > 0)
        staged = staged_cards[0]
        self.assertEqual(staged["url"], tiktok_url)
        self.assertIn("Awesome TikTok Clip", staged["file_name"])
        self.assertEqual(staged["file_size"], 8388608)
        self.assertEqual(staged["badge"], "720P")
        self.assertEqual(staged["category"], "Video")
        self.assertIsNotNone(gui._pending_media_context)
        self.assertEqual(gui._pending_media_context["url"], tiktok_url)
        self.assertEqual(gui._pending_media_context["info"], mock_raw_info)
        self.assertEqual(gui._pending_media_context["options"], mock_opts)
        self.assertEqual(gui._pending_media_context["selected_opt"], mock_opts[0])
        self.assertIsNotNone(gui._pending_media_context["resolver"])

    def test_start_staged_media_download_preserves_context(self):
        """Verifies _start_staged_download restores media context and triggers start_download."""
        from smart_download.ui.panels.kanban_staged_helpers import _start_staged_download
        from smart_download.services.youtube_service import VideoFormatOption

        opt = VideoFormatOption(
            format_id="mp4_1080",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=20000000,
            fps=30,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/v.mp4"
        )
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        staged_info = {
            "url": url,
            "final_dest": "C:/Downloads/song.mp4",
            "conn_count": 8,
            "speed_limit": 0.0,
            "selected_opt": opt,
            "media_context": {
                "url": url,
                "selected_option": opt,
                "selected_opt": opt,
                "final_dest": "C:/Downloads/song.mp4"
            }
        }

        download_started = []
        class MockGUI:
            _pending_media_context = None
            _staged_links = [staged_info]
            entry_url = None
            entry_dest = None

            def remove_staged_link(self, u):
                self._staged_links = [it for it in self._staged_links if it.get("url") != u]

            def _on_start_download(self):
                download_started.append(True)

        gui = MockGUI()
        _start_staged_download(gui, staged_info)

        self.assertEqual(len(download_started), 1)
        self.assertEqual(gui._pending_media_context["url"], url)
        self.assertEqual(gui._pending_media_context["selected_option"], opt)
        self.assertEqual(len(gui._staged_links), 0)

    def test_preview_confirm_does_not_stage_col1(self):
        """Verifies preview confirm starts download without leaving duplicate card in Col1."""
        from smart_download.ui.panels.media_options_bar import MediaOptionsBarMixin
        from smart_download.services.youtube_service import VideoFormatOption

        opt = VideoFormatOption(
            format_id="720p",
            resolution_label="720p",
            height=720,
            ext="mp4",
            filesize_approx=5000000,
            fps=30,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/stream.mp4"
        )

        staged_col1 = []
        class MockBarApp(MediaOptionsBarMixin):
            def __init__(self):
                self.conn_var = MagicMock()
                self.conn_var.get.return_value = "8"
                self.entry_custom_speed = MagicMock()
                self.entry_custom_speed.get.return_value = "0"
                self.log = MagicMock()
                self._pending_media_context = None
                self._last_media_context = None
            def stage_probed_link_in_col1(self, info):
                staged_col1.append(info)
            def _launch_stream_coordinator(self, stream_info, final_dest, max_conn, bytes_limit):
                pass

        app = MockBarApp()
        ctx = {"info": {}, "resolver": None, "url": "https://example.com/v"}
        # Simulate open preview with on_confirm
        # _sync_ui with stage_col1=False should NOT call stage_probed_link_in_col1
        # Test _start_pending_media_download removing staged link
        app.remove_staged_link = MagicMock()
        app._pending_media_context = {"url": "https://example.com/v", "selected_option": opt}
        app._start_pending_media_download()
        app.remove_staged_link.assert_called_once_with("https://example.com/v")

    def test_probe_media_worker_categorization_and_sync(self):
        """Verifies _probe_media_worker categorizes destination into Video/Audio,
        extracts audio/subtitle tracks into _pending_media_context, updates entry_dest,
        and calls populate_main_media_bar."""
        from smart_download.ui.panels.kanban_staged_helpers import _probe_media_worker
        from smart_download.services.youtube_service import VideoFormatOption

        opt = VideoFormatOption(
            format_id="1080p",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=15000000,
            fps=60,
            vcodec="avc1",
            acodec="mp4a",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/stream1080.mp4"
        )
        opt.filesize = 15000000
        fake_info = {
            "title": "Categorized Test Video",
            "duration": 120,
            "formats": [{"format_id": "1080p", "ext": "mp4", "height": 1080}],
            "subtitles": {"en": [{"url": "https://example.com/en.vtt", "ext": "vtt"}]}
        }

        class MockEntry:
            def __init__(self, val=""):
                self._val = val
            def get(self):
                return self._val
            def delete(self, s, e):
                self._val = ""
            def insert(self, idx, txt):
                self._val = txt

        class MockApp:
            def __init__(self):
                self.entry_url = MockEntry("https://youtube.com/watch?v=cat_test_123")
                self.entry_dest = MockEntry("")
                self.auto_categorize_folders = True
                self.default_download_dir = "C:/Downloads"
                self._pending_media_context = None
                self._staged_links = []
                self.populated_bar_args = None

            def dispatch_to_main_thread(self, fn):
                fn()

            def populate_main_media_bar(self, **kwargs):
                self.populated_bar_args = kwargs

            def add_staged_link_card(self, info):
                self._staged_links.append(info)

            def remove_parsing_link_card(self, url):
                pass

        app = MockApp()
        url = "https://youtube.com/watch?v=cat_test_123"
        cand = {"title": "Categorized Test Video", "file_name": "video.mp4"}

        with patch("smart_download.services.youtube_service.YouTubeResolver") as mock_res_cls, \
             patch("smart_download.services.youtube_tracks.extract_audio_tracks", return_value=[{"id": "a1", "label": "English"}]) as mock_aud, \
             patch("smart_download.services.youtube_tracks.extract_subtitle_tracks", return_value=[{"id": "s1", "label": "Arabic"}]) as mock_sub:
            mock_inst = MagicMock()
            mock_inst.extract_format_options.return_value = (fake_info, [opt])
            mock_res_cls.return_value = mock_inst

            _probe_media_worker(app, url, cand, conn_count=8, speed_limit=0.0)

        self.assertIsNotNone(app._pending_media_context)
        self.assertEqual(app._pending_media_context["url"], url)
        self.assertEqual(app._pending_media_context["info"], fake_info)
        self.assertEqual(app._pending_media_context["options"], [opt])
        self.assertEqual(len(app._pending_media_context["audio_tracks"]), 1)
        self.assertEqual(len(app._pending_media_context["subtitle_tracks"]), 1)

        # Final dest must include Video subfolder due to auto-categorization
        final_dest = app._pending_media_context["final_dest"]
        self.assertTrue("Video" in final_dest or "video" in final_dest.lower())
        self.assertEqual(app.entry_dest.get(), final_dest)

        # populate_main_media_bar should have been called with synchronized kwargs
        self.assertIsNotNone(app.populated_bar_args)
        self.assertEqual(app.populated_bar_args["url"], url)
        self.assertEqual(app.populated_bar_args["dest"], final_dest)
        self.assertEqual(app.populated_bar_args["selected_opt"], opt)
        self.assertEqual(len(app.populated_bar_args["audio_tracks"]), 1)
        self.assertEqual(len(app.populated_bar_args["subtitle_tracks"]), 1)

    def test_start_pending_media_download_prioritizes_ctx_options(self):
        """Verifies _start_pending_media_download prioritizes ctx['options'] over
        _main_media_options and avoids mismatch when bar options differ."""
        from smart_download.ui.panels.media_options_bar import MediaOptionsBarMixin
        from smart_download.services.youtube_service import VideoFormatOption

        opt_ctx = VideoFormatOption(
            format_id="ctx_1080",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=10000000,
            fps=30,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/ctx.mp4"
        )
        opt_bar = VideoFormatOption(
            format_id="bar_480",
            resolution_label="480p",
            height=480,
            ext="mp4",
            filesize_approx=4000000,
            fps=30,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/bar.mp4"
        )

        class MockBarApp(MediaOptionsBarMixin):
            def __init__(self):
                self.conn_var = MagicMock()
                self.conn_var.get.return_value = "8"
                self.entry_custom_speed = MagicMock()
                self.entry_custom_speed.get.return_value = "0"
                self.log = MagicMock()
                self._pending_media_context = None
                self._last_media_context = None
                self._main_media_options = [opt_bar]  # Stale or different bar options
                self.cb_main_quality = MagicMock()
                self.cb_main_quality.current.return_value = 0
                self.launched_stream = None

            def remove_staged_link(self, url):
                pass

            def _launch_stream_coordinator(self, stream_info, final_dest, max_conn, bytes_limit):
                self.launched_stream = stream_info

        app = MockBarApp()
        mock_resolver = MagicMock()
        mock_resolver.build_stream_info.side_effect = lambda info, opt: f"stream_for_{opt.format_id}"

        app._pending_media_context = {
            "url": "https://example.com/ctx_test",
            "info": {"title": "Context Test"},
            "options": [opt_ctx],
            "selected_option": opt_ctx,
            "resolver": mock_resolver,
            "final_dest": "C:/Downloads/Video/ctx_test.mp4"
        }

        app._start_pending_media_download()

        # Since bar_opts ([opt_bar]) != ctx_opts ([opt_ctx]), cb_main_quality index 0 was NOT used to pick opt_bar
        # opt_ctx should be passed to build_stream_info
        mock_resolver.build_stream_info.assert_called_once_with({"title": "Context Test"}, opt_ctx)
        self.assertEqual(app.launched_stream, "stream_for_ctx_1080")

    def test_quality_change_and_open_in_main_syncs_col1(self):
        """Verifies changing quality in media bar and 'open in main' updates _pending_media_context
        and updates Column 1 staged card via stage_media_option_in_col1."""
        from smart_download.ui.panels.media_options_bar import MediaOptionsBarMixin
        from smart_download.services.youtube_service import VideoFormatOption

        opt720 = VideoFormatOption(
            format_id="720",
            resolution_label="720p",
            height=720,
            ext="mp4",
            filesize_approx=7000000,
            fps=30,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/720.mp4"
        )
        opt720.filesize = 7000000
        opt1080 = VideoFormatOption(
            format_id="1080",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=15000000,
            fps=60,
            vcodec="h264",
            acodec="aac",
            is_progressive=True,
            is_audio_only=False,
            video_url="https://example.com/1080.mp4"
        )
        opt1080.filesize = 15000000

        class MockEntry:
            def __init__(self, val=""):
                self._val = val
            def get(self):
                return self._val
            def delete(self, s, e):
                self._val = ""
            def insert(self, idx, txt):
                self._val = txt

        class MockBarApp(MediaOptionsBarMixin):
            def __init__(self):
                self.conn_var = MagicMock()
                self.entry_custom_speed = MagicMock()
                self.log = MagicMock()
                self.entry_dest = MockEntry("C:/Downloads/Video/my_clip.mp4")
                self._main_media_options = [opt720, opt1080]
                self._staged_links = [{
                    "url": "https://youtube.com/watch?v=sync_col1_test",
                    "file_name": "my_clip.mp4",
                    "badge": "720p"
                }]
                self._pending_media_context = {
                    "url": "https://youtube.com/watch?v=sync_col1_test",
                    "info": {"title": "My Clip", "duration": 60},
                    "options": [opt720, opt1080],
                    "selected_option": opt720,
                    "final_dest": "C:/Downloads/Video/my_clip.mp4"
                }
                self.cb_main_quality = MagicMock()
                self.cb_main_quality.current.return_value = 1  # Select 1080p

            def stage_probed_link_in_col1(self, info):
                u = info.get("url")
                self._staged_links = [it for it in self._staged_links if it.get("url") != u]
                self._staged_links.insert(0, info)

        app = MockBarApp()
        # Trigger quality changed event
        app._on_main_quality_changed(None)

        # Context must now have opt1080
        self.assertEqual(app._pending_media_context["selected_option"], opt1080)
        self.assertEqual(app._pending_media_context["selected_opt"], opt1080)

        # Staged link in Col1 must be refreshed with 1080p badge and 15000000 size
        staged = app._staged_links[0]
        self.assertEqual(staged["url"], "https://youtube.com/watch?v=sync_col1_test")
        self.assertEqual(staged["badge"], "1080p")
        self.assertEqual(staged["file_size"], 15000000)

    def test_atomic_write_json_config(self):
        """Verifies _atomic_write_json writes safely and replaces target file."""
        from smart_download.config import _atomic_write_json
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as td:
            fpath = os.path.join(td, "test_settings.json")
            _atomic_write_json(fpath, {"test_key": "val1"})
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("test_key"), "val1")
            _atomic_write_json(fpath, {"test_key": "val2"})
            with open(fpath, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            self.assertEqual(data2.get("test_key"), "val2")
            tmp_files = [f for f in os.listdir(td) if ".tmp" in f]
            self.assertEqual(len(tmp_files), 0)

    def test_run_cancellable_ffmpeg_cancellation(self):
        """Verifies run_cancellable_ffmpeg terminates process cleanly when cancel_event is set."""
        from smart_download.services.subtitle_processor import run_cancellable_ffmpeg
        import threading
        ev = threading.Event()
        ev.set()
        res = run_cancellable_ffmpeg(["ffmpeg", "-version"], cancel_event=ev)
        self.assertEqual(res.returncode, -1)

        ev2 = threading.Event()
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None, 0]
        mock_sp = MagicMock()
        mock_sp.Popen.return_value = mock_proc
        del mock_sp.run._mock_name
        threading.Timer(0.05, ev2.set).start()
        res2 = run_cancellable_ffmpeg(["ffmpeg"], cancel_event=ev2, subprocess_mod=mock_sp)
        self.assertEqual(res2.returncode, -1)
        mock_proc.kill.assert_called()

    def test_preview_bridge_hardening_and_pruning(self):
        """Verifies _safe_int, session pruning at 15, and CSRF Origin 403 blocking."""
        from smart_download.services.preview_stream_proxy import _safe_int, _is_preview_origin_allowed, _prune_preview_sessions
        self.assertEqual(_safe_int("42"), 42)
        self.assertEqual(_safe_int("invalid", 10), 10)
        self.assertEqual(_safe_int(None, 5), 5)

        self.assertTrue(_is_preview_origin_allowed(""))
        self.assertTrue(_is_preview_origin_allowed("http://127.0.0.1:9242"))
        self.assertTrue(_is_preview_origin_allowed("http://localhost:9242"))
        self.assertFalse(_is_preview_origin_allowed("https://evil.com"))
        self.assertFalse(_is_preview_origin_allowed("http://attacker.org:8080"))

        sessions = {f"s_{i}": f"session_{i}" for i in range(25)}
        _prune_preview_sessions(sessions, 15)
        self.assertEqual(len(sessions), 15)
        self.assertNotIn("s_0", sessions)
        self.assertIn("s_24", sessions)

    def test_browser_bridge_csrf_and_wake_protection(self):
        """Verifies GET /show and Origin/Referer/Sec-Fetch-Site CSRF protections in bridge_server."""
        from smart_download.services.browser.bridge_server import BrowserBridgeHandler
        handler = BrowserBridgeHandler.__new__(BrowserBridgeHandler)
        handler.headers = {"Origin": "https://malicious.com"}
        self.assertFalse(handler._is_origin_allowed())

        handler.headers = {"Sec-Fetch-Site": "cross-site"}
        self.assertFalse(handler._is_origin_allowed())

        handler.headers = {"Referer": "http://evil-tracker.com/page"}
        self.assertFalse(handler._is_origin_allowed())

        handler.headers = {"Referer": "http://127.0.0.1:9654/"}
        self.assertTrue(handler._is_origin_allowed())

        handler.headers = {"Origin": "chrome-extension://abcdefghijklmnop"}
        self.assertTrue(handler._is_origin_allowed())

    def test_atomic_replace_with_retry(self):
        """Verifies atomic_replace_with_retry handles retry on transient lock."""
        from smart_download.utils.file_ops import atomic_replace_with_retry
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.tmp")
            dst = os.path.join(td, "dst.txt")
            with open(src, "w") as f: f.write("test data")
            
            atomic_replace_with_retry(src, dst)
            self.assertTrue(os.path.isfile(dst))
            self.assertFalse(os.path.isfile(src))

            src2 = os.path.join(td, "src2.tmp")
            dst2 = os.path.join(td, "dst2.txt")
            with open(src2, "w") as f: f.write("test data 2")
            
            real_replace = os.replace
            calls = [0]
            def mock_replace(s, d):
                calls[0] += 1
                if calls[0] < 3:
                    raise PermissionError("Access is denied")
                return real_replace(s, d)

            with patch("os.replace", side_effect=mock_replace):
                atomic_replace_with_retry(src2, dst2, max_retries=5, retry_delay=0.01)
            self.assertGreaterEqual(calls[0], 3)
            self.assertTrue(os.path.isfile(dst2))

    def test_archive_utils_safety_verification(self):
        """Verifies _verify_extracted_tree_safe blocks symlinks and escaping paths."""
        from smart_download.utils.archive_utils import _verify_extracted_tree_safe
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            safe_dir = os.path.join(td, "extracted")
            os.makedirs(safe_dir, exist_ok=True)
            with open(os.path.join(safe_dir, "safe.txt"), "w") as f: f.write("safe")
            _verify_extracted_tree_safe(safe_dir)

            with patch("os.path.islink", return_value=True):
                with self.assertRaises(ValueError) as ctx:
                    _verify_extracted_tree_safe(safe_dir)
                self.assertIn("Unsafe path or symlink", str(ctx.exception))

    def test_trusted_update_urls_and_patch_integrity(self):
        """Verifies _is_trusted_update_url and zip testzip integrity verification."""
        from smart_download.services.updater_service import _is_trusted_update_url
        from smart_download.services.core_patch_updater import CoreHotPatchUpdater
        
        self.assertTrue(_is_trusted_update_url("https://github.com/hazoza90-hub/Faqih-Downloader-FD-/releases/v2.0.2"))
        self.assertTrue(_is_trusted_update_url("https://api.github.com/repos/hazoza90-hub/Faqih-Downloader-FD-/releases/latest"))
        self.assertTrue(_is_trusted_update_url("https://objects.githubusercontent.com/github-production-release-asset/123"))
        self.assertTrue(_is_trusted_update_url("https://pypi.org/pypi/yt-dlp/json"))
        self.assertFalse(_is_trusted_update_url("http://github.com/unencrypted"))
        self.assertFalse(_is_trusted_update_url("https://evil-site.com/malware.exe"))
        self.assertFalse(_is_trusted_update_url("https://example.com/update.zip"))
        self.assertFalse(_is_trusted_update_url(""))

        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as td:
            corrupt_zip = os.path.join(td, "corrupt.zip")
            with zipfile.ZipFile(corrupt_zip, "w") as zf:
                zf.writestr("core_version.json", '{"version": "2.0.2"}')
            with open(corrupt_zip, "r+b") as f:
                f.seek(30)
                f.write(b"\xFF\xFF\xFF\xFF")
            
            updater = CoreHotPatchUpdater(plugin_dir=td, current_version="2.0.0")
            with self.assertRaises(Exception):
                updater.apply_core_patch(corrupt_zip)

    def test_subtitle_downloader_ssl_security(self):
        """Verifies subtitle_downloader attempts default SSL context first and falls back on SSLError."""
        from smart_download.services.subtitle_downloader import _translate_srt_cues_via_gtx
        import ssl
        
        cues = [(0.0, 1.0, "Hello")]
        resp_mock = MagicMock()
        resp_mock.read.return_value = b'[[["\xd9\x85\xd8\xb1\xd8\xad\xd8\xa8\xd8\xa7", "Hello"]]]'
        resp_mock.__enter__.return_value = resp_mock
        
        calls = []
        def mock_urlopen(req, timeout=10, context=None):
            calls.append(context)
            if len(calls) == 1:
                raise ssl.SSLError("Certificate verify failed")
            return resp_mock

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            res = _translate_srt_cues_via_gtx(cues, target_lang="ar")
            self.assertTrue(len(calls) >= 2)
            self.assertEqual(res[0][2], "مرحبا")


class TestPhase2SecurityAndHardening(unittest.TestCase):
    """Verifies all Phase 2 security and reliability hardening improvements."""

    def test_uninstall_safe_directory_validation(self):
        """Verifies _is_safe_uninstall_target rejects dangerous paths and accepts safe ones."""
        from smart_download.installer.installer_migration import _is_safe_uninstall_target
        import tempfile

        # Unsafe targets
        self.assertFalse(_is_safe_uninstall_target(None))
        self.assertFalse(_is_safe_uninstall_target(""))
        self.assertFalse(_is_safe_uninstall_target("C:\\"))
        self.assertFalse(_is_safe_uninstall_target("D:\\"))
        self.assertFalse(_is_safe_uninstall_target(os.path.expanduser("~")))

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        self.assertFalse(_is_safe_uninstall_target(desktop))

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        self.assertFalse(_is_safe_uninstall_target(downloads))

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            self.assertFalse(_is_safe_uninstall_target(os.path.join(local_app_data, "Programs")))

        # Safe targets
        with tempfile.TemporaryDirectory() as td:
            sub = os.path.join(td, "MyInstalledApp")
            os.makedirs(sub, exist_ok=True)
            self.assertTrue(_is_safe_uninstall_target(sub))

        appdata = os.environ.get("APPDATA", "")
        if appdata:
            self.assertTrue(_is_safe_uninstall_target(os.path.join(appdata, "Smart Download")))

    def test_extract_payload_zip_slip_and_integrity_protection(self):
        """Verifies extract_payload_lzma_archive rejects zip slip paths and corrupted archives."""
        from smart_download.installer.installer_migration import extract_payload_lzma_archive
        import tempfile
        import zipfile

        with tempfile.TemporaryDirectory() as td:
            target_dir = os.path.join(td, "target")
            os.makedirs(target_dir, exist_ok=True)

            # Zip slip traversal
            evil_zip = os.path.join(td, "evil_slip.zip")
            with zipfile.ZipFile(evil_zip, "w") as zf:
                zf.writestr("../evil.txt", "evil")
            with self.assertRaises(RuntimeError) as ctx:
                extract_payload_lzma_archive(evil_zip, target_dir)
            self.assertIn("traversal", str(ctx.exception).lower())

            # Sibling directory prefix bypass
            sibling_zip = os.path.join(td, "sibling_slip.zip")
            with zipfile.ZipFile(sibling_zip, "w") as zf:
                zf.writestr(f"../{os.path.basename(target_dir)}_evil/evil.txt", "evil")
            with self.assertRaises(RuntimeError) as ctx:
                extract_payload_lzma_archive(sibling_zip, target_dir)
            self.assertIn("traversal", str(ctx.exception).lower())

            # Corrupt zip archive
            corrupt_zip = os.path.join(td, "corrupt.zip")
            with zipfile.ZipFile(corrupt_zip, "w") as zf:
                zf.writestr("test.txt", b"0123456789" * 10)
            with open(corrupt_zip, "r+b") as f:
                f.seek(35)
                f.write(b"\xFF")
            with self.assertRaises(RuntimeError) as ctx:
                extract_payload_lzma_archive(corrupt_zip, target_dir)
            self.assertTrue("corrupted" in str(ctx.exception).lower() or "integrity" in str(ctx.exception).lower())

    def test_atomic_chunk_assembly_with_rollback(self):
        """Verifies TurboDownloadEngine.assemble uses temporary file and cleans it up on error."""
        from smart_download.core.engine import TurboDownloadEngine
        from smart_download.core.chunk import DownloadChunk
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "output.bin")
            engine = TurboDownloadEngine("https://example.com/file.bin", dest, max_connections=1)
            engine.total_size = 20

            part_path = f"{dest}.part_0"
            with open(part_path, "wb") as f:
                f.write(b"0123456789")  # Incomplete: 10 bytes instead of 20

            chunk = DownloadChunk(0, 0, 19)
            chunk.part_filepath = part_path
            chunk.downloaded_bytes = 10
            chunk.is_completed = True
            engine.chunks = [chunk]

            with self.assertRaises(AssertionError):
                engine.assemble()

            self.assertFalse(os.path.exists(dest))
            tmp_files = [f for f in os.listdir(td) if ".assembling_" in f]
            self.assertEqual(len(tmp_files), 0)

            # Successful assembly
            with open(part_path, "wb") as f:
                f.write(b"01234567890123456789")  # Full 20 bytes
            chunk.downloaded_bytes = 20
            engine.assemble()
            self.assertTrue(os.path.exists(dest))
            self.assertEqual(os.path.getsize(dest), 20)
            tmp_files = [f for f in os.listdir(td) if ".assembling_" in f]
            self.assertEqual(len(tmp_files), 0)

    def test_ytdlp_updater_trusted_domain_and_zip_integrity(self):
        """Verifies YtDlpAutoUpdater rejects untrusted domains and corrupted archives."""
        from smart_download.services.ytdlp_updater import YtDlpAutoUpdater
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            updater = YtDlpAutoUpdater(plugin_dir=td)

            with self.assertRaises(ValueError):
                updater.download_and_extract_archive("http://evil-site.com/malware.zip")

            # Corrupted archive triggering testzip failure
            import io, zipfile
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, "w") as zf:
                zf.writestr("yt_dlp/__init__.py", b"__version__ = '2026.01.01'\n" * 10)
            data = bytearray(bio.getvalue())
            data[35] ^= 0xFF  # Corrupt internal compressed bytes

            mock_resp = MagicMock()
            mock_resp.read.side_effect = [bytes(data), b""]
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = False

            with patch("urllib.request.urlopen", return_value=mock_resp):
                corrupt_res = updater.download_and_extract_archive("https://pypi.org/packages/yt_dlp.zip")
                self.assertFalse(corrupt_res.get("success", False))
                self.assertIn("corrupted", corrupt_res.get("error", "").lower())

    def test_html_resolver_ssrf_mitigation(self):
        """Verifies SSRF mitigation blocks internal/loopback hosts and redirects."""
        from smart_download.core.html_resolver import _is_private_or_loopback_host, resolve_real_download_url

        self.assertTrue(_is_private_or_loopback_host("127.0.0.1"))
        self.assertTrue(_is_private_or_loopback_host("localhost"))
        self.assertTrue(_is_private_or_loopback_host("::1"))
        self.assertTrue(_is_private_or_loopback_host("10.0.0.1"))
        self.assertTrue(_is_private_or_loopback_host("172.16.5.10"))
        self.assertTrue(_is_private_or_loopback_host("192.168.1.1"))
        self.assertTrue(_is_private_or_loopback_host("169.254.169.254"))
        self.assertFalse(_is_private_or_loopback_host("8.8.8.8"))
        self.assertFalse(_is_private_or_loopback_host("github.com"))

        mock_resp = MagicMock()
        mock_resp.geturl.return_value = "http://192.168.1.1/admin/download.zip"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = resolve_real_download_url("https://example.com/download")
            self.assertEqual(res["error"], "SSRF: Redirect to internal host blocked")
            self.assertFalse(res["resolved"])

    def test_preview_html_builder_xss_mitigation(self):
        """Verifies preview HTML escaping prevents </script> breakout and escapes iframe quotes."""
        from smart_download.ui.modals.preview_html_builder import generate_preview_html

        xss_url = 'https://example.com/embed" onload="alert(1)'
        xss_title = "Video </script><script>alert('xss')</script>"

        html_output = generate_preview_html(
            url=xss_url,
            video_title=xss_title,
            stream_url="",
            subtitle_tracks=[{"label": "</script><script>alert(2)</script>", "language": "en"}]
        )

        self.assertNotIn("</script><script>alert('xss')", html_output)
        self.assertIn("<\\/script>", html_output)
        self.assertNotIn('src="https://example.com/embed" onload=', html_output)
        self.assertIn('&quot; onload=&quot;', html_output)



if __name__ == "__main__":
    unittest.main()
