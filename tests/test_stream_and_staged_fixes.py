"""
Unit tests for StreamCoordinator dubbing fault tolerance,
subtitle [Sub] filename tag accuracy, and Staged Card / Media Options Bar responsiveness.
"""
import os
import unittest
import inspect
from unittest.mock import MagicMock

from faqih_downloader.services.youtube_models import VideoFormatOption
from faqih_downloader.utils.file_ops import apply_media_filename_tags


class TestStreamCoordinatorDubbingFixes(unittest.TestCase):
    """Verifies audio engine parameters and error isolation in StreamDownloadCoordinator."""

    def test_audio_engine_single_connection_and_no_split(self):
        """Verifies a_conn=1 and allow_dynamic_split=False for audio stream download."""
        from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator

        src = inspect.getsource(StreamDownloadCoordinator._run_coordinator)
        self.assertIn("a_conn = 1", src)
        self.assertIn("allow_dynamic_split=False", src)
        a_error_func = src.split("def _on_a_error")[1].split("def _on_a_progress")[0]
        self.assertNotIn("v_completed.set()", a_error_func)
        self.assertNotIn("v_engine.cancel()", a_error_func)
        self.assertIn("while not (v_completed.is_set() and a_completed.is_set())", src)
        self.assertIn("if v_error:\n                    break", src)

    def test_audio_error_resets_metrics_without_cancelling_video(self):
        from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
        src = inspect.getsource(StreamDownloadCoordinator._run_coordinator)
        a_error_func = src.split("def _on_a_error")[1].split("def _on_a_progress")[0]
        self.assertIn("self._a_speed = 0.0", a_error_func)
        self.assertIn("self._a_active = 0", a_error_func)
        self.assertIn("_report_combined()", a_error_func)
        self.assertNotIn("v_engine.cancel()", a_error_func)


class TestSubtitleFilenameTagAccuracy(unittest.TestCase):
    """Verifies that [Sub] tag only appears when an actual subtitle track is selected."""

    def test_no_sub_tag_when_subtitle_track_is_none(self):
        """When subtitle embed mode is hard_burn but selected_subtitle_track is None, no [Sub] is added."""
        opt = VideoFormatOption(
            format_id="137",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=1024 * 1024
        )
        opt.subtitle_embed_mode = "hard_burn"
        opt.selected_subtitle_track = None

        sub_mode = opt.subtitle_embed_mode
        is_sub_burned = (sub_mode == "hard_burn") and bool(getattr(opt, "selected_subtitle_track", None))
        self.assertFalse(is_sub_burned)

        cur_dest = "C:\\Downloads\\MyVideo.mp4"
        updated_dest = apply_media_filename_tags(cur_dest, quality_label=opt.resolution_label, is_sub_burned=is_sub_burned, ext=opt.ext)
        self.assertNotIn("[Sub]", updated_dest)
        self.assertIn("[1080p]", updated_dest)

    def test_sub_tag_added_when_subtitle_track_is_selected(self):
        """When subtitle embed mode is hard_burn and selected_subtitle_track is valid, [Sub] is added."""
        opt = VideoFormatOption(
            format_id="137",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=1024 * 1024
        )
        opt.subtitle_embed_mode = "hard_burn"
        opt.selected_subtitle_track = {"sub_id": "ar", "language": "ar", "label": "Arabic"}

        sub_mode = opt.subtitle_embed_mode
        is_sub_burned = (sub_mode == "hard_burn") and bool(getattr(opt, "selected_subtitle_track", None))
        self.assertTrue(is_sub_burned)

        cur_dest = "C:\\Downloads\\MyVideo.mp4"
        updated_dest = apply_media_filename_tags(cur_dest, quality_label=opt.resolution_label, is_sub_burned=is_sub_burned, ext=opt.ext)
        self.assertIn("[Sub]", updated_dest)
        self.assertIn("[1080p]", updated_dest)


class TestMediaOptionsBarAndStagedCard(unittest.TestCase):
    """Verifies that populate_main_media_bar accepts ctx dict and staged card reflects options."""

    def test_populate_main_media_bar_accepts_ctx_dict(self):
        from faqih_downloader.ui.panels.media_options_bar import MediaOptionsBarMixin

        class DummyGUI(MediaOptionsBarMixin):
            def __init__(self):
                self.c_panel = "#1e293b"
                self.c_panel_light = "#334155"
                self.c_text_bright = "#f8fafc"
                self.c_accent = "#38bdf8"
                self.c_accent_dark = "#0284c7"
                self._staged_links = []
                self._main_sub_mode_codes = ["soft_embed", "srt_only", "hard_burn"]
                self._main_sub_pos_codes = ["bottom", "middle", "top"]
                self.media_bar_host = MagicMock()
                self.media_options_frame = MagicMock()
                self.cb_main_quality = MagicMock()
                self.cb_main_quality.current.return_value = 0
                self.cb_main_audio = MagicMock()
                self.cb_main_audio.current.return_value = 0
                self.cb_main_sub = MagicMock()
                self.cb_main_sub.current.return_value = 0
                self.cb_main_sub_mode = MagicMock()
                self.cb_main_sub_mode.current.return_value = 0
                self.cb_main_sub_pos = MagicMock()
                self.cb_main_sub_pos.current.return_value = 0
                self.entry_url = MagicMock()
                self.entry_dest = MagicMock()
                self.entry_url.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                self.entry_dest.get.return_value = "C:\\Downloads\\video.mp4"
                self.kanban_container = MagicMock()

        gui = DummyGUI()
        opt = VideoFormatOption(
            format_id="137", resolution_label="1080p", height=1080, ext="mp4", filesize_approx=1024 * 1024
        )
        ctx = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "info": {"title": "Never Gonna Give You Up"},
            "options": [opt],
            "audio_tracks": [{"language": "en", "label": "English"}],
            "subtitle_tracks": [{"sub_id": "ar", "language": "ar", "label": "Arabic"}],
            "selected_option": opt,
            "final_dest": "C:\\Downloads\\video.mp4"
        }

        gui.populate_main_media_bar(ctx)
        self.assertIsNotNone(gui._pending_media_context)
        self.assertEqual(gui._pending_media_context["url"], ctx["url"])
        self.assertEqual(len(gui._main_media_options), 1)
        self.assertTrue(gui.media_bar_host.pack.called)

    def test_on_staged_probe_ready_callback(self):
        from faqih_downloader.ui.panels.media_options_bar import MediaOptionsBarMixin

        class DummyGUI(MediaOptionsBarMixin):
            def __init__(self):
                self.media_options_frame = MagicMock()
                self.media_bar_host = MagicMock()
                self._main_sub_mode_codes = ["soft_embed", "srt_only", "hard_burn"]
                self._main_sub_pos_codes = ["bottom", "middle", "top"]
                self.cb_main_quality = MagicMock()
                self.cb_main_audio = MagicMock()
                self.cb_main_sub = MagicMock()
                self.cb_main_sub_mode = MagicMock()
                self.cb_main_sub_pos = MagicMock()
                self.entry_url = MagicMock()
                self.entry_dest = MagicMock()
                self.entry_url.get.return_value = ""
                self.entry_dest.get.return_value = ""
                self.called = False

            def populate_main_media_bar(self, *args, **kwargs):
                self.called = True

        gui = DummyGUI()
        ctx = {"url": "https://example.com/video", "options": []}
        gui._on_staged_probe_ready(ctx)
        self.assertTrue(gui.called)
        self.assertEqual(gui._pending_media_context, ctx)

    def test_stage_media_option_in_col1_preserves_selected_opt(self):
        from faqih_downloader.ui.panels.kanban_staged_prober import stage_media_option_in_col1

        class DummyGUI:
            def __init__(self):
                self._staged_links = []

            def stage_probed_link_in_col1(self, info_dict):
                self._staged_links = [it for it in self._staged_links if it.get("url") != info_dict.get("url")]
                self._staged_links.insert(0, info_dict)

        gui = DummyGUI()
        opt1 = VideoFormatOption(
            format_id="18", resolution_label="360p", height=360, ext="mp4", filesize_approx=1024 * 500
        )
        stage_media_option_in_col1(gui, "https://example.com/v", "Video", opt1, "C:\\vid.mp4", 100)
        self.assertEqual(len(gui._staged_links), 1)
        self.assertEqual(gui._staged_links[0]["selected_opt"], opt1)

        # Update with new option
        opt2 = VideoFormatOption(
            format_id="137", resolution_label="1080p", height=1080, ext="mp4", filesize_approx=1024 * 1024
        )
        stage_media_option_in_col1(gui, "https://example.com/v", "Video", opt2, "C:\\vid.mp4", 100)
        self.assertEqual(len(gui._staged_links), 1)
        self.assertEqual(gui._staged_links[0]["selected_opt"], opt2)

    def test_sync_modal_selection_to_staged_updates_media_bar_comboboxes(self):
        from faqih_downloader.ui.modals.quality_modal_helpers import sync_modal_selection_to_staged

        class MockApp:
            def __init__(self):
                self._staged_links = []
                self._pending_media_context = {}
                self._main_sub_mode_codes = ["soft_embed", "srt_only", "hard_burn"]
                self._main_sub_pos_codes = ["bottom", "middle", "top"]
                self.cb_main_quality = MagicMock()
                self.cb_main_audio = MagicMock()
                self.cb_main_sub = MagicMock()
                self.cb_main_sub_mode = MagicMock()
                self.cb_main_sub_pos = MagicMock()
                self._main_media_options = [
                    VideoFormatOption("1", "720p", 720, "mp4", 100),
                    VideoFormatOption("2", "1080p", 1080, "mp4", 200)
                ]
                self._main_audio_tracks = [{"track_id": "a1", "language": "en"}]
                self._main_subtitle_tracks = [{"sub_id": "s1", "language": "ar"}]

        app = MockApp()
        modal = MagicMock()
        modal.parent_app = app
        modal.selected_option = app._main_media_options[1]
        modal.selected_option.selected_audio_track = app._main_audio_tracks[0]
        modal.selected_option.selected_subtitle_track = app._main_subtitle_tracks[0]
        modal.audio_tracks = app._main_audio_tracks
        modal.subtitle_tracks = app._main_subtitle_tracks
        modal.cb_audio = None
        modal.cb_sub = None
        modal.entry_dest.get.return_value = "C:\\vid.mp4"
        modal.video_url = "https://youtu.be/test"

        sync_modal_selection_to_staged(modal)
        app.cb_main_quality.current.assert_called_with(1)
        app.cb_main_audio.current.assert_called_with(0)
        app.cb_main_sub.current.assert_called_with(0)

    def test_start_pending_media_download_preserves_modal_selected_opt(self):
        from faqih_downloader.ui.panels.media_options_actions import MediaOptionsActionsMixin

        class MockGUI(MediaOptionsActionsMixin):
            def __init__(self):
                self._staged_links = []
                self._main_sub_mode_codes = ["soft_embed", "srt_only", "hard_burn"]
                self._main_sub_pos_codes = ["bottom", "middle", "top"]
                self._main_bar_url = "https://youtu.be/test"
                self.entry_dest = MagicMock()
                self.entry_dest.get.return_value = "C:\\vid.mp4"
                self.conn_var = MagicMock()
                self.conn_var.get.return_value = "8"
                self.entry_custom_speed = MagicMock()
                self.entry_custom_speed.get.return_value = "0"
                self.cb_main_quality = MagicMock()
                self.cb_main_quality.current.return_value = 0
                self.cb_main_audio = MagicMock()
                self.cb_main_audio.current.return_value = 0
                self.cb_main_sub = MagicMock()
                self.cb_main_sub.current.return_value = 0
                self.cb_main_sub_mode = MagicMock()
                self.cb_main_sub_mode.current.return_value = 0
                self.cb_main_sub_pos = MagicMock()
                self.cb_main_sub_pos.current.return_value = 0
                self._main_media_options = [
                    VideoFormatOption("1", "720p", 720, "mp4", 100),
                    VideoFormatOption("2", "1080p", 1080, "mp4", 200)
                ]
                self._pending_media_context = {
                    "url": "https://youtu.be/test",
                    "options": self._main_media_options,
                    "selected_option": self._main_media_options[1],
                    "selected_opt": self._main_media_options[1],
                    "info": {"title": "vid"},
                    "resolver": MagicMock()
                }

            def _launch_stream_coordinator(self, stream_info, final_dest, max_conn, bytes_limit):
                pass

        gui = MockGUI()
        gui._start_pending_media_download()
        self.assertEqual(gui._last_media_context["selected_option"].resolution_label, "1080p")


if __name__ == "__main__":
    unittest.main()
