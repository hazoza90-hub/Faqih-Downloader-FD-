"""
Unit tests verifying Media Options Bar UI wiring and Dubbing & Subtitle continuity fixes.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo
from faqih_downloader.services.youtube_tracks import extract_audio_tracks
from faqih_downloader.services.subtitle_downloader import _translate_srt_cues_via_gtx
from faqih_downloader.core.engine import TurboDownloadEngine


class TestMediaOptionsAndContinuity(unittest.TestCase):
    """Test suite for media options bar synchronization, engine clen parsing, and subtitle continuity."""

    def test_extract_audio_tracks_dubbing_and_size_estimation(self):
        """Verifies dubbed audio formats are not merged into 'original' and filesize is calculated from duration."""
        info = {
            "duration": 120.0,
            "language": "en",
            "formats": [
                {
                    "format_id": "140-orig",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "ext": "m4a",
                    "language": "en",
                    "format_note": "original",
                    "language_preference": 1,
                    "url": "https://googlevideo.com/audio140_orig",
                },
                {
                    "format_id": "140-ar-dub",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "ext": "m4a",
                    "language": "ar",
                    "format_note": "dubbed Arabic",
                    "language_preference": 0,
                    "url": "https://googlevideo.com/audio140_ar",
                    "filesize": None,
                    "filesize_approx": None,
                },
            ]
        }
        tracks = extract_audio_tracks(info)
        self.assertGreaterEqual(len(tracks), 2)
        orig_track = next((t for t in tracks if t.get("is_original")), None)
        ar_track = next((t for t in tracks if t.get("language") == "ar"), None)
        self.assertIsNotNone(orig_track)
        self.assertIsNotNone(ar_track)
        self.assertFalse(ar_track.get("is_original"))
        # Estimated filesize: 128.0 kbps * 1000 / 8 * 120s = 1,920,000 bytes
        expected_size = int((128.0 * 1000.0 / 8.0) * 120.0)
        self.assertEqual(ar_track.get("filesize"), expected_size)

    def test_engine_probe_googlevideo_clen_extraction(self):
        """Verifies TurboDownloadEngine.probe extracts clen from googlevideo URL when Content-Length is missing."""
        test_url = "https://rr3---sn-4g5ednks.googlevideo.com/videoplayback?expire=123&clen=987654321&dur=500"
        engine = TurboDownloadEngine(test_url, "test_output.mp4")

        # Mock urllib to return response without Content-Length or Content-Range
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = test_url
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            engine.probe()

        self.assertEqual(engine.total_size, 987654321)
        self.assertTrue(engine.supports_ranges)

    def test_translate_srt_cues_via_gtx_post_and_batching(self):
        """Verifies _translate_srt_cues_via_gtx sends POST requests and handles sub-batches without losing cues."""
        cues = [
            (0.0, 2.0, f"Sentence number {i}") for i in range(30)
        ]

        def fake_urlopen(req, timeout=12, context=None):
            # Check that request uses POST with body
            self.assertIsNotNone(req.data)
            self.assertEqual(req.get_method(), "POST")
            mock_r = MagicMock()
            # Simulate GTX JSON response format: [[["ترجمة", "original", None, None]]]
            # We return translated string with delimiter |||
            q_str = req.data.decode("utf-8")
            from urllib.parse import parse_qs
            parsed = parse_qs(q_str)
            raw_text = parsed.get("q", [""])[0]
            # Replace sentences with arabic equivalent
            items = raw_text.split("\n ||| \n")
            trans_items = [f"جملة {it.strip()}" for it in items]
            resp_data = [[["\n ||| \n".join(trans_items), raw_text, None, None]]]
            import json
            mock_r.read.return_value = json.dumps(resp_data).encode("utf-8")
            mock_r.__enter__.return_value = mock_r
            return mock_r

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            res = _translate_srt_cues_via_gtx(cues, target_lang="ar")

        self.assertEqual(len(res), 30)
        self.assertTrue(res[0][2].startswith("جملة"))
        self.assertTrue(res[-1][2].startswith("جملة"))

    def test_media_options_bar_population_and_sync(self):
        """Verifies media options bar populates controls and synchronizes choices with pending context."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tkinter display not available")

        try:
            from faqih_downloader.ui.panels.media_options_bar import MediaOptionsBarMixin

            class DummyGUI(MediaOptionsBarMixin):
                def __init__(self, r):
                    self.root = r
                    self.c_panel = "#151a24"
                    self.c_panel_light = "#1e293b"
                    self.c_text_bright = "#ffffff"
                    self.c_accent = "#19f3ee"
                    self.c_accent_dark = "#0ea5e9"
                    self.container = tk.Frame(r)
                    self.container.pack()
                    self.kanban_container = tk.Frame(self.container)
                    self.kanban_container.pack()
                    self.media_bar_host = tk.Frame(self.container)
                    self._build_media_options_bar(self.media_bar_host)
                    self.entry_url = tk.Entry(r)
                    self.entry_url.insert(0, "https://youtube.com/watch?v=demo123")
                    self.entry_dest = tk.Entry(r)
                    self.entry_dest.insert(0, "video.mp4")
                    self._staged_links = []

            gui = DummyGUI(root)
            opt1 = VideoFormatOption(
                format_id="137", ext="mp4", resolution_label="1080p", height=1080,
                filesize_approx=50000000, is_audio_only=False
            )
            opt2 = VideoFormatOption(
                format_id="18", ext="mp4", resolution_label="720p", height=720,
                filesize_approx=25000000, is_audio_only=False
            )
            audio1 = {"track_id": "original", "language": "en", "label": "Original (Default)"}
            audio2 = {"track_id": "ar", "language": "ar", "label": "العربية (ar)"}
            sub1 = {"sub_id": "none", "label": "None", "language": "none"}
            sub2 = {"sub_id": "ar", "label": "العربية", "language": "ar"}

            gui.populate_main_media_bar(
                info={"title": "Demo Video", "duration": 180},
                options=[opt1, opt2],
                audio_tracks=[audio1, audio2],
                subtitle_tracks=[sub1, sub2],
                selected_option=opt1,
                url="https://youtube.com/watch?v=demo123",
                dest="video.mp4"
            )

            # Check that pending context is created and media bar host packed
            self.assertIsNotNone(gui._pending_media_context)
            self.assertEqual(gui.cb_main_quality.current(), 0)

            # Change to Arabic audio (index 1)
            gui.cb_main_audio.current(1)
            gui._on_main_audio_changed(event=MagicMock())
            pending = gui._pending_media_context
            self.assertEqual(pending["selected_option"].selected_audio_track["language"], "ar")

            # Change to Arabic subtitle (index 1)
            gui.cb_main_sub.current(1)
            gui._on_main_sub_changed(event=MagicMock())
            self.assertEqual(pending["selected_option"].selected_subtitle_track["language"], "ar")

            # Hide media bar
            gui.hide_main_media_bar()
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
