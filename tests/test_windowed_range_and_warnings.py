"""
Tests for Windowed Range Proxy, Clipboard URL Sniffing Fixes, and 32 Connections Warning.
"""
import io
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, Mock

import tkinter as tk
from tkinter import ttk

from faqih_downloader.ui.modals.settings_modal import SettingsModal
from faqih_downloader.ui.modals.confirm_modal_widgets import ConfirmModalWidgetsMixin
from faqih_downloader.ui.controllers.clipboard_controller import ClipboardControllerMixin
from faqih_downloader.services.preview_stream_proxy import stream_upstream_media, PreviewStreamBridge


class TestWindowedRangeAndWarnings(unittest.TestCase):
    """Verifies 32 connections warning, clipboard sniffing fixes, and windowed range proxy."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def test_settings_modal_threads_32_warning(self):
        """Verifies SettingsModal displays warning for 32 connections and hides it for 16."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        # Create dummy widget container
        frame = tk.Frame(self.root)
        warn_lbl = tk.Label(frame, text="")

        modal = MagicMock(spec=SettingsModal)
        modal.lbl_threads_warn = warn_lbl
        modal.cb_threads = MagicMock()
        modal.cb_threads.get.return_value = "32"

        # Call the real _update_threads_warning implementation
        SettingsModal._update_threads_warning(modal, "32")
        self.assertIn("32", warn_lbl.cget("text"))

        # Now change to 16
        modal.cb_threads.get.return_value = "16"
        with patch.object(warn_lbl, "pack_forget") as mock_forget:
            SettingsModal._update_threads_warning(modal, "16")
            mock_forget.assert_called()

    def test_confirm_modal_threads_32_warning(self):
        """Verifies ConfirmModalWidgetsMixin displays warning for 32 threads and hides for lower."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        frame = tk.Frame(self.root)
        warn_lbl = tk.Label(frame, text="")

        class DummyConfirmModal(ConfirmModalWidgetsMixin):
            def __init__(self):
                self.lbl_threads_warn = warn_lbl
                self.combo_threads = MagicMock()

        dummy = DummyConfirmModal()
        dummy.combo_threads.get.return_value = "32"
        dummy._update_threads_warning()
        self.assertIn("32", warn_lbl.cget("text"))

        # Switch to 8
        dummy.combo_threads.get.return_value = "8"
        with patch.object(warn_lbl, "pack_forget") as mock_forget:
            dummy._update_threads_warning()
            mock_forget.assert_called()

    def test_clipboard_sniffer_recovery_from_initial_tcl_error(self):
        """Verifies clipboard sniffer captures link on second attempt if first attempt fails with TclError."""
        controller = ClipboardControllerMixin()
        controller.root = MagicMock()
        controller._last_clipboard_seq = 10
        controller._last_clipboard_url = None
        controller._trigger_clipboard_url = MagicMock()

        # Simulate GetClipboardSequenceNumber returning 20 (new sequence)
        with patch("ctypes.windll.user32.GetClipboardSequenceNumber", return_value=20):
            # First tick: clipboard is locked, _read_clipboard_text_safe returns empty
            with patch.object(controller, "_read_clipboard_text_safe", return_value=""):
                controller._check_clipboard_now()
                # Verify seq was NOT updated to 20 yet because reading failed
                self.assertEqual(controller._last_clipboard_seq, 10)
                controller._trigger_clipboard_url.assert_not_called()

            # Second tick: clipboard unlocked, text is read successfully
            test_url = "https://example.com/archive.zip"
            with patch.object(controller, "_read_clipboard_text_safe", return_value=test_url):
                controller._check_clipboard_now()
                # Now seq is updated to 20
                self.assertEqual(controller._last_clipboard_seq, 20)
                # URL is detected and triggered
                controller._trigger_clipboard_url.assert_called_once_with(test_url)

    def test_clipboard_sniffer_retrigger_same_url_on_recopy(self):
        """Verifies re-copying the same URL triggers capture when sequence number changes."""
        controller = ClipboardControllerMixin()
        controller.root = MagicMock()
        controller._last_clipboard_seq = 50
        controller._last_clipboard_url = "https://example.com/video.mp4"
        controller._last_detected_url = "https://example.com/video.mp4"
        controller._trigger_clipboard_url = MagicMock()

        # User copies the same URL again in browser -> seq becomes 55
        test_url = "https://example.com/video.mp4"
        with patch("ctypes.windll.user32.GetClipboardSequenceNumber", return_value=55), \
             patch.object(controller, "_read_clipboard_text_safe", return_value=test_url):
            controller._check_clipboard_now()
            self.assertEqual(controller._last_clipboard_seq, 55)
            controller._trigger_clipboard_url.assert_called_once_with(test_url)

    def test_windowed_range_proxy_googlevideo_streaming(self):
        """Verifies Windowed Range Proxy requests 2MB chunks for googlevideo.com URLs."""
        handler = MagicMock()
        handler.headers = {"Range": "bytes=0-"}
        handler.wfile = io.BytesIO()

        target_url = "https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?id=stream123"

        # Mock requests.Session
        mock_resp = MagicMock()
        mock_resp.status_code = 206
        mock_resp.headers = {
            "Content-Type": "video/mp4",
            "Content-Range": "bytes 0-2097151/2097152",
        }
        mock_resp.iter_content.return_value = [b"A" * 65536, b"B" * 65536]

        with patch("requests.Session") as mock_session_cls:
            mock_session = mock_session_cls.return_value
            mock_session.get.return_value = mock_resp

            stream_upstream_media(handler, target_url, {"User-Agent": "TestUA"}, is_head=False)

            # Assert first request used 2MB range
            first_call_headers = mock_session.get.call_args_list[0][1]["headers"]
            self.assertEqual(first_call_headers.get("Range"), "bytes=0-2097151")

            # Assert client response was sent with 206 and Content-Range
            handler.send_response.assert_called_with(206)
            handler.send_header.assert_any_call("Content-Range", "bytes 0-2097151/2097152")
            handler.send_header.assert_any_call("Content-Length", "2097152")

            # Assert data was written to client wfile
            self.assertEqual(len(handler.wfile.getvalue()), 131072)

    def test_preview_stream_bridge_lifecycle(self):
        """Verifies PreviewStreamBridge starts on ephemeral port and registers stream paths."""
        bridge = PreviewStreamBridge()
        try:
            port = bridge.start()
            self.assertGreater(port, 0)
            reg_url = bridge.register_stream("https://example.com/media.mp4", {"Custom": "123"})
            self.assertTrue(reg_url.startswith(f"http://127.0.0.1:{port}/stream?id="))
        finally:
            bridge.stop()
    def test_read_clipboard_text_safe_win32_fallback(self):
        """Verifies _read_clipboard_text_safe falls back to Win32 ctypes when clipboard_get raises TclError."""
        controller = ClipboardControllerMixin()
        controller.root = MagicMock()
        controller.root.clipboard_get.side_effect = tk.TclError("clipboard locked")

        with patch("sys.platform", "win32"), \
             patch("faqih_downloader.ui.controllers.clipboard_controller.IS_WINDOWS", True), \
             patch("ctypes.windll.user32.OpenClipboard", return_value=True), \
             patch("ctypes.windll.user32.CloseClipboard", return_value=True), \
             patch("ctypes.windll.user32.GetClipboardData", return_value=0x12345678), \
             patch("ctypes.windll.kernel32.GlobalLock", return_value=0x87654321), \
             patch("ctypes.windll.kernel32.GlobalUnlock", return_value=True), \
             patch("ctypes.c_wchar_p") as mock_wchar:
            mock_wchar.return_value.value = "https://example.com/fallback_url.mp4"
            text = controller._read_clipboard_text_safe()
            self.assertEqual(text, "https://example.com/fallback_url.mp4")


    def test_windowed_range_proxy_urllib_fallback_when_requests_missing(self):
        """Verifies Windowed Range Proxy uses urllib.request.urlopen when requests library is unavailable."""
        handler = MagicMock()
        handler.headers = {"Range": "bytes=0-"}
        handler.wfile = io.BytesIO()

        target_url = "https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?id=stream456"

        mock_upstream = MagicMock()
        mock_upstream.getcode.return_value = 206
        mock_upstream.headers = {
            "Content-Type": "video/mp4",
            "Content-Range": "bytes 0-2097151/2097152",
        }
        mock_upstream.read.side_effect = [b"X" * 65536, b"Y" * 65536, b""]

        with patch.dict(sys.modules, {"requests": None}), \
             patch("urllib.request.urlopen", return_value=mock_upstream) as mock_urlopen:

            stream_upstream_media(handler, target_url, {"User-Agent": "TestUA"}, is_head=False)

            # Verify urllib.request.urlopen was called
            self.assertTrue(mock_urlopen.called)
            req_called = mock_urlopen.call_args[0][0]
            # Verify the Request has the 2MB range header
            self.assertEqual(req_called.headers.get("Range"), "bytes=0-2097151")

            # Assert client response was sent with 206 and Content-Range
            handler.send_response.assert_called_with(206)
            handler.send_header.assert_any_call("Content-Range", "bytes 0-2097151/2097152")
            handler.send_header.assert_any_call("Content-Length", "2097152")

            # Assert data was written to handler.wfile
            self.assertEqual(len(handler.wfile.getvalue()), 131072)

    def test_trigger_clipboard_url_respects_hidden_tray_state(self):
        """Verifies _trigger_clipboard_url does not deiconify root when hidden in tray with auto_start enabled."""
        controller = ClipboardControllerMixin()
        controller.root = MagicMock()
        controller._on_clipboard_url_detected = MagicMock()

        # Case 1: Hidden in tray, auto_start is True -> should NOT deiconify or lift
        controller._auto_start_clipboard = True
        controller.is_window_hidden_or_minimized = MagicMock(return_value=True)
        controller._trigger_clipboard_url("https://example.com/file1.zip")
        controller.root.deiconify.assert_not_called()
        controller.root.lift.assert_not_called()
        controller._on_clipboard_url_detected.assert_called_once_with("https://example.com/file1.zip")

        # Case 2: Visible (not hidden), auto_start is True -> should lift, not deiconify
        controller.root.reset_mock()
        controller._on_clipboard_url_detected.reset_mock()
        controller.is_window_hidden_or_minimized.return_value = False
        controller._trigger_clipboard_url("https://example.com/file2.zip")
        controller.root.deiconify.assert_not_called()
        controller.root.lift.assert_called_once()
        controller._on_clipboard_url_detected.assert_called_once_with("https://example.com/file2.zip")

        # Case 3: auto_start is False -> should deiconify and lift to show main window inputs
        controller.root.reset_mock()
        controller._on_clipboard_url_detected.reset_mock()
        controller._auto_start_clipboard = False
        controller.is_window_hidden_or_minimized.return_value = True
        controller._trigger_clipboard_url("https://example.com/file3.zip")
        controller.root.deiconify.assert_called_once()
        controller.root.lift.assert_called_once()
        controller._on_clipboard_url_detected.assert_called_once_with("https://example.com/file3.zip")

    def test_clipboard_sniffer_modal_and_sequence_handling(self):
        """Verifies clipboard captures new URL when non-progress modal is open, but blocks when modal is in progress view."""
        controller = ClipboardControllerMixin()
        controller.root = MagicMock()
        controller._last_clipboard_seq = 100
        controller._last_clipboard_url = "https://example.com/first.mp4"
        controller._trigger_clipboard_url = MagicMock()

        dummy_modal = MagicMock()
        dummy_modal.winfo_exists.return_value = True
        dummy_modal.is_completed = False
        dummy_modal.is_closed = False
        dummy_modal.is_in_progress_view = False
        controller._confirm_modal = dummy_modal

        # Scenario 1: Seq changed, modal is open but NOT in progress -> should capture new URL
        new_url = "https://example.com/second.mp4"
        with patch("ctypes.windll.user32.GetClipboardSequenceNumber", return_value=105), \
             patch.object(controller, "_read_clipboard_text_safe", return_value=new_url):
            controller._check_clipboard_now()
            self.assertEqual(controller._last_clipboard_seq, 105)
            controller._trigger_clipboard_url.assert_called_once_with(new_url)

        # Scenario 2: Seq changed, but modal IS in active progress view -> should block capture
        controller._trigger_clipboard_url.reset_mock()
        dummy_modal.is_in_progress_view = True
        third_url = "https://example.com/third.mp4"
        with patch("ctypes.windll.user32.GetClipboardSequenceNumber", return_value=110), \
             patch.object(controller, "_read_clipboard_text_safe", return_value=third_url):
            controller._check_clipboard_now()
            # trigger should NOT be called
            controller._trigger_clipboard_url.assert_not_called()

        # Scenario 3: Seq did NOT change and modal is open -> should exit early
        dummy_modal.is_in_progress_view = False
        controller._trigger_clipboard_url.reset_mock()
        with patch("ctypes.windll.user32.GetClipboardSequenceNumber", return_value=105):
            controller._check_clipboard_now()
            controller._trigger_clipboard_url.assert_not_called()


    def test_windowed_range_proxy_urllib_multi_window_fallback(self):
        """Verifies Windowed Range Proxy streams multiple 2MB windows via urllib when requests is missing."""
        handler = MagicMock()
        handler.headers = {"Range": "bytes=0-"}
        handler.wfile = io.BytesIO()

        target_url = "https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?id=stream789"
        tot_size = 5 * 1024 * 1024  # 5 MB total

        def _mock_urlopen(req, *args, **kwargs):
            rng = req.headers.get("Range")
            m = re.match(r"bytes=(\d+)-(\d+)", rng)
            s, e = int(m.group(1)), int(m.group(2))
            chunk_data = b"W" * (e - s + 1)

            resp = MagicMock()
            resp.getcode.return_value = 206
            resp.headers = {
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes {s}-{e}/{tot_size}",
            }
            # Stream in 64KB sub-chunks
            sub_chunks = [chunk_data[i:i + 65536] for i in range(0, len(chunk_data), 65536)] + [b""]
            resp.read.side_effect = sub_chunks
            return resp

        with patch.dict(sys.modules, {"requests": None}), \
             patch("urllib.request.urlopen", side_effect=_mock_urlopen) as mock_urlopen:

            stream_upstream_media(handler, target_url, {"User-Agent": "MultiUA"}, is_head=False)

            # 5MB in 2MB windows -> 3 windows: [0-2MB-1], [2MB-4MB-1], [4MB-5MB-1]
            self.assertEqual(mock_urlopen.call_count, 3)
            self.assertEqual(len(handler.wfile.getvalue()), tot_size)
            handler.send_response.assert_called_with(206)
            handler.send_header.assert_any_call("Content-Range", f"bytes 0-{tot_size - 1}/{tot_size}")

    def test_idle_modals_dismissal_on_new_link(self):
        """Verifies opening a direct or YouTube link closes any existing idle modals of the other types."""
        from faqih_downloader.ui.controllers.clipboard_dialog_mixin import ClipboardDialogMixin
        from faqih_downloader.ui.controllers.youtube_download_controller import YouTubeDownloadControllerMixin

        class DummyApp(ClipboardDialogMixin, YouTubeDownloadControllerMixin):
            def __init__(self):
                self.root = MagicMock()
                self.root.winfo_exists.return_value = True
                self.engine = None
                self.conn_var = MagicMock(get=lambda: "8")
                self.entry_custom_speed = MagicMock(get=lambda: "0")
                self.entry_url = MagicMock()
                self.entry_dest = MagicMock()
                self.btn_start = MagicMock()
                self.btn_pause = MagicMock()
                self.btn_cancel = MagicMock()
                self.txt_log = MagicMock()
                self.tree_chunks = MagicMock()
                self.card_size = MagicMock()
                self.is_window_hidden_or_minimized = MagicMock(return_value=False)

            def log(self, *args): pass
            def _show_fetching_toast(self, *args, **kwargs): pass
            def _close_fetching_toast(self): pass
            def _get_base_downloads_dir(self): return tempfile.gettempdir()
            def _theme_dict(self): return {}

        app = DummyApp()

        # Case 1: _quality_modal and _candidates_modal are open; user copies direct download link
        q_modal = MagicMock()
        q_modal.winfo_exists.return_value = True
        app._quality_modal = q_modal

        c_modal = MagicMock()
        c_modal.winfo_exists.return_value = True
        app._candidates_modal = c_modal

        with patch("faqih_downloader.ui.controllers.clipboard_dialog_mixin.DownloadConfirmationModal") as mock_conf:
            app._show_download_confirmation_dialog("https://example.com/file.zip", "/dest/file.zip")
            q_modal.destroy.assert_called_once()
            c_modal.destroy.assert_called_once()
            self.assertIsNone(app._quality_modal)
            self.assertIsNone(app._candidates_modal)

        # Case 2: _confirm_modal (idle) is open; user copies YouTube link
        conf_modal = MagicMock()
        conf_modal.winfo_exists.return_value = True
        conf_modal.is_in_progress_view = False
        app._confirm_modal = conf_modal

        c_modal2 = MagicMock()
        c_modal2.winfo_exists.return_value = True
        app._candidates_modal = c_modal2

        with patch("faqih_downloader.ui.controllers.youtube_download_controller.threading.Thread") as mock_thread, \
             patch.object(app, "_show_fetching_toast"):
            app._start_youtube_download("https://www.youtube.com/watch?v=abcdef12345", "/dest/video.mp4")
            conf_modal.destroy.assert_called_once()
            c_modal2.destroy.assert_called_once()
            self.assertIsNone(app._confirm_modal)
            self.assertIsNone(app._candidates_modal)

    def test_vault_restore_modal_interactive_row_selection(self):
        """Verifies clicking row or name_lbl toggles BooleanVar, highlights row in #1e3a5f, and has no double mousewheel."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        import shutil
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vr_inter_")
        try:
            f1 = os.path.join(tmp_dir, "sample_vid.mp4")
            with open(f1, "wb") as f: f.write(b"data1")
            f2 = os.path.join(tmp_dir, "sample_audio.mp3")
            with open(f2, "wb") as f: f.write(b"data2")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def _refresh_history_table(self, force=False): pass

            gui = DummyGUI(self.root, hm)
            with patch("faqih_downloader.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                self.assertFalse(modal._item_vars[f1].get())
                row_widget = modal._row_widgets[f1]["row"]
                cb = modal._row_widgets[f1]["cb"]

                # Verify no duplicate <MouseWheel> binding on row sub-widget
                self.assertEqual(row_widget.bind("<MouseWheel>"), "")

                # Initially unselected: bg is card color (#1c2333)
                self.assertEqual(row_widget.cget("bg"), modal.c_card)

                # Click row to toggle selection
                modal._toggle_item(f1)
                self.assertTrue(modal._item_vars[f1].get())
                self.assertEqual(row_widget.cget("bg"), "#1e3a5f")
                self.assertIn("1", modal.btn_restore_sel.cget("text"))

                # Toggle off via _toggle_all_selection
                modal._toggle_all_selection(False)
                self.assertFalse(modal._item_vars[f1].get())
                self.assertEqual(row_widget.cget("bg"), modal.c_card)

                # Toggle on via _toggle_all_selection
                modal._toggle_all_selection(True)
                self.assertTrue(modal._item_vars[f1].get())
                self.assertTrue(modal._item_vars[f2].get())
                self.assertEqual(row_widget.cget("bg"), "#1e3a5f")
                self.assertIn("2", modal.btn_restore_sel.cget("text"))

                modal.destroy()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_browse_folder_and_scan_custom_dir(self):
        """Verifies browse_folder() defaults checkboxes to False, then selectively restores."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        import shutil
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_base = tempfile.mkdtemp(prefix="sd_test_vr_base_")
        tmp_custom = tempfile.mkdtemp(prefix="sd_test_vr_custom_")
        try:
            # Create files in custom dir including a subfolder and a temp file to ignore
            sub_dir = os.path.join(tmp_custom, "nested_folder")
            os.makedirs(sub_dir, exist_ok=True)
            doc_file = os.path.join(sub_dir, "contract.pdf")
            with open(doc_file, "wb") as f: f.write(b"pdf data")
            tmp_file = os.path.join(tmp_custom, "ignore.tmp")
            with open(tmp_file, "wb") as f: f.write(b"temp")

            hist_db = os.path.join(tmp_base, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def _refresh_history_table(self, force=False): pass

            gui = DummyGUI(self.root, hm)

            # Test direct scan_unregistered_disk_files with custom_dir
            scanned = scan_unregistered_disk_files(gui, custom_dir=tmp_custom)
            scanned_paths = [s["file_path"] for s in scanned]
            self.assertIn(doc_file, scanned_paths)
            self.assertNotIn(tmp_file, scanned_paths)

            with patch("faqih_downloader.config.get_setting", return_value=tmp_base):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                # Simulate browsing custom folder
                with patch("tkinter.filedialog.askdirectory", return_value=tmp_custom):
                    loaded_count = modal.browse_folder()
                    self.assertEqual(loaded_count, 1)

                self.assertEqual(modal._current_scan_dir, tmp_custom)
                self.assertIn(tmp_custom, modal.lbl_current_folder.cget("text"))
                # Verify custom folder items default to False so user can inspect first
                self.assertFalse(modal._item_vars[doc_file].get())

                # Select item
                modal._toggle_item(doc_file)
                self.assertTrue(modal._item_vars[doc_file].get())

                # Restore selected
                restored = modal.restore_selected()
                self.assertEqual(restored, 1)
                entries = hm.get_entries()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["filename"], "contract.pdf")
        finally:
            shutil.rmtree(tmp_base, ignore_errors=True)
            shutil.rmtree(tmp_custom, ignore_errors=True)

    def test_vault_restore_batch_pagination_and_load_more(self):
        """Verifies pagination limits rendering to 40 items and Show More appends remaining rows."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        import shutil
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vr_page_")
        try:
            # Create 45 files
            for i in range(45):
                f_path = os.path.join(tmp_dir, f"file_{i:02d}.bin")
                with open(f_path, "wb") as f: f.write(b"x")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def _refresh_history_table(self, force=False): pass

            gui = DummyGUI(self.root, hm)
            with patch("faqih_downloader.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                self.assertEqual(len(modal._all_files), 45)
                # First page should display exactly 40 rows
                self.assertEqual(len(modal._row_widgets), 40)
                # Load more button must be present
                self.assertIsNotNone(modal._btn_load_more)
                self.assertIn("5", modal._btn_load_more.cget("text"))

                # Click Load More
                modal._on_load_more(modal._all_files)
                self.root.update_idletasks()

                # All 45 should now be rendered
                self.assertEqual(len(modal._row_widgets), 45)
                # Load more button should be cleaned up
                self.assertIsNone(modal._btn_load_more)

                modal.destroy()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_scan_unregistered_disk_files_ignores_dirs_and_caps_max_results(self):
        """Verifies fast scanner skips ignored directories (node_modules, appdata) and caps results."""
        import shutil
        from faqih_downloader.ui.panels.kanban_vault_ops import scan_unregistered_disk_files
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vr_scan_")
        try:
            # Create normal dir with file
            norm_dir = os.path.join(tmp_dir, "NormalFolder")
            os.makedirs(norm_dir, exist_ok=True)
            norm_f = os.path.join(norm_dir, "movie.mp4")
            with open(norm_f, "wb") as f: f.write(b"video")

            # Create ignored dirs with files
            for ig in ["node_modules", "AppData", ".git"]:
                ig_dir = os.path.join(tmp_dir, ig)
                os.makedirs(ig_dir, exist_ok=True)
                with open(os.path.join(ig_dir, "bad.js"), "wb") as f: f.write(b"bad")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, hm):
                    self.history_manager = hm

            gui = DummyGUI(hm)

            # Test scanning skips ignored dirs
            scanned = scan_unregistered_disk_files(gui, custom_dir=tmp_dir, max_results=10)
            paths = [s["file_path"] for s in scanned]
            self.assertIn(norm_f, paths)
            for p in paths:
                rel_path = os.path.relpath(p, tmp_dir)
                parts = [part.lower() for part in rel_path.split(os.sep)]
                self.assertNotIn("node_modules", parts)
                self.assertNotIn("appdata", parts)
                self.assertNotIn(".git", parts)

            # Test max_results capping
            capped = scan_unregistered_disk_files(gui, custom_dir=tmp_dir, max_results=1)
            self.assertLessEqual(len(capped), 1)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_refreshes_history_and_kanban_col3(self):
        """Verifies _finalize_and_close resets filter to 'all' and invokes both refresh callbacks."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        import shutil
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vr_refresh_")
        try:
            f1 = os.path.join(tmp_dir, "ready.zip")
            with open(f1, "wb") as f: f.write(b"zip")

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                    self._vault_filter_category = "documents"
                    self.refreshed_col3 = False
                    self.refreshed_hist = False
                def refresh_kanban_col3(self):
                    self.refreshed_col3 = True
                def _refresh_history_table(self, force=False):
                    if force:
                        self.refreshed_hist = True

            gui = DummyGUI(self.root, hm)
            with patch("faqih_downloader.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                count = modal.restore_all()
                self.assertEqual(count, 1)
                self.assertEqual(gui._vault_filter_category, "all")
                self.assertTrue(gui.refreshed_col3)
                self.assertTrue(gui.refreshed_hist)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vault_restore_modal_smooth_scrolling_and_debouncing(self):
        """Verifies yscrollincrement=2, debounced configure, and eased smooth scrolling on VaultRestoreModal."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        import shutil
        from faqih_downloader.ui.modals.vault_restore_modal import VaultRestoreModal
        from faqih_downloader.core.history import DownloadHistoryManager

        tmp_dir = tempfile.mkdtemp(prefix="sd_test_vr_smooth_")
        try:
            for i in range(25):
                fp = os.path.join(tmp_dir, f"file_{i:02d}.bin")
                with open(fp, "wb") as f:
                    f.write(b"data" * 100)

            hist_db = os.path.join(tmp_dir, "test_hist.json")
            hm = DownloadHistoryManager(history_file=hist_db)

            class DummyGUI:
                def __init__(self, root, hm):
                    self.root = root
                    self.history_manager = hm
                def refresh_kanban_col3(self): pass
                def _refresh_history_table(self, force=False): pass

            gui = DummyGUI(self.root, hm)
            with patch("faqih_downloader.config.get_setting", return_value=tmp_dir):
                modal = VaultRestoreModal(gui)
                self.root.update_idletasks()

                # Verify yscrollincrement=2
                self.assertEqual(int(modal.canvas.cget("yscrollincrement")), 2)

                # Verify initial state
                self.assertEqual(modal._scroll_steps_remaining, 0)
                self.assertIsNone(modal._scroll_timer_id)
                self.assertFalse(modal._scrollregion_pending)

                # Verify debounced scrollregion scheduling
                modal._schedule_scrollregion_update()
                self.assertTrue(modal._scrollregion_pending)
                self.root.update_idletasks()
                self.assertFalse(modal._scrollregion_pending)

                # Mock scrollbar.get() to simulate overflowing content (top=0.0, btm=0.5)
                with patch.object(modal.scrollbar, "get", return_value=(0.0, 0.5)):
                    wheel_evt = MagicMock()
                    wheel_evt.delta = -120  # Scroll down 1 notch

                    with patch.object(modal.canvas, "yview_scroll") as mock_scroll:
                        modal._on_mousewheel(wheel_evt)
                        # 18 units accumulated; first step int(18 * 0.35) = 6 units executed immediately
                        mock_scroll.assert_called_with(6, "units")
                        self.assertEqual(modal._scroll_steps_remaining, 12)
                        self.assertIsNotNone(modal._scroll_timer_id)

                        # Advance smooth scroll step
                        modal._step_smooth_scroll()
                        # next step = int(12 * 0.35) = 4 units
                        mock_scroll.assert_called_with(4, "units")
                        self.assertEqual(modal._scroll_steps_remaining, 8)

                # Clean destruction cancels timer without errors
                modal.destroy()
                self.assertIsNone(modal._scroll_timer_id)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_kanban_vault_canvas_smooth_scrolling_and_debouncing(self):
        """Verifies yscrollincrement=2, debounced configure, and smooth 10ms interpolation on Completed Vault."""
        if not self.root:
            self.skipTest("Tkinter GUI not available")

        from faqih_downloader.ui.panels.kanban_vault_helpers import setup_vault_scroll_view
        from faqih_downloader.ui.panels.kanban_panel import KanbanPanelMixin

        col_frame = tk.Frame(self.root)
        body = tk.Frame(col_frame)

        class DummyPipeline(KanbanPanelMixin):
            def __init__(self, root):
                self.root = root
                self._vault_scroll_steps = 0
                self._vault_scroll_timer = None

        panel = DummyPipeline(self.root)
        cv, container = setup_vault_scroll_view(col_frame, body, panel=panel)
        panel.vault_cards_canvas = cv
        panel.vault_cards_container = container

        # Verify yscrollincrement=2
        self.assertEqual(int(cv.cget("yscrollincrement")), 2)

        # Verify debounced scrollregion update on container configure
        cv._schedule_vault_scrollregion()
        self.assertTrue(getattr(cv, "_scrollregion_pending", False))
        self.root.update_idletasks()
        self.assertFalse(getattr(cv, "_scrollregion_pending", False))

        # Test smooth mousewheel interpolation on panel
        wheel_evt = MagicMock()
        wheel_evt.delta = -120  # 1 notch down
        with patch.object(cv, "yview_scroll") as mock_scroll:
            panel._on_vault_mousewheel(wheel_evt)
            # 14 units accumulated; first step int(14 * 0.35) = 4 units executed immediately
            mock_scroll.assert_called_with(4, "units")
            self.assertEqual(panel._vault_scroll_steps, 10)
            self.assertIsNotNone(panel._vault_scroll_timer)

            # Advance step
            panel._step_vault_smooth_scroll()
            # step = int(10 * 0.35) = 3 units
            mock_scroll.assert_called_with(3, "units")
            self.assertEqual(panel._vault_scroll_steps, 7)

        col_frame.destroy()


if __name__ == "__main__":
    unittest.main()
