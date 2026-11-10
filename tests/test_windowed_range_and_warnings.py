"""
Tests for Windowed Range Proxy, Clipboard URL Sniffing Fixes, and 32 Connections Warning.
"""
import io
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
