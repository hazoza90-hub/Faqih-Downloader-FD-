"""
Unit tests for Preview Window Reopen & Safe Wi-Fi Network Stability (tests/test_preview_reopen_and_network_stability.py).
Verifies:
1. Prevention of ValueError: Circular reference detected in generate_preview_html even after multiple in-place syncs.
2. Clean cache reset in _show_cached_quality_modal (clears clip/chapter tags and [Clip] suffix).
3. 8MB safe window division and auto-reconnect for googlevideo CDN streams without Premature EOF.
4. Safe auto-reconnect FFmpeg CLI flags in download_clipped_stream_direct.
"""
from __future__ import annotations

import os
import sys
import json
import copy
import io
import threading
import unittest
from unittest.mock import MagicMock, patch

from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo
from faqih_downloader.services.preview_stream_bridge import (
    PreviewSession, _apply_session_sub_styles
)
from faqih_downloader.services.media_clipper_engine import (
    clone_clean_subtitle_track, sync_clipper_state_from_body, download_clipped_stream_direct
)
from faqih_downloader.ui.modals.preview_html_builder import generate_preview_html
from faqih_downloader.ui.panels.media_options_actions import MediaOptionsActionsMixin
from faqih_downloader.core.engine import TurboDownloadEngine
from faqih_downloader.core.chunk import DownloadChunk
from faqih_downloader.core.engine_workers import GOOGLEVIDEO_WINDOW_BYTES


class TestPreviewReopenAndNetworkStability(unittest.TestCase):
    """Test suite for preview reopening, cache hygiene, and network auto-healing."""

    def test_prevent_circular_reference_in_preview_html(self):
        """1. generate_preview_html must not fail with Circular reference detected after repeated syncs."""
        opt = VideoFormatOption(
            format_id="137",
            resolution_label="1080p (Full HD)",
            height=1080,
            ext="mp4",
            filesize_approx=50_000_000,
            fps=30,
            vcodec="avc1",
            acodec="none",
            video_url="https://example.com/video.mp4"
        )
        sub1 = {"sub_id": "ar", "language": "ar", "label": "Arabic", "url": "https://example.com/ar.vtt"}
        sub2 = {"sub_id": "en", "language": "en", "label": "English", "url": "https://example.com/en.vtt"}

        session = PreviewSession(
            sid="test_session_123",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            video_title="Never Gonna Give You Up",
            options=[opt],
            subtitle_tracks=[sub1, sub2],
            selected_sub_track=sub1,
        )

        # Simulate user repeatedly changing clips, chapters, and dual subtitles
        for i in range(5):
            body = {
                "clip_start": float(i * 5),
                "clip_end": float(i * 5 + 20),
                "sub_custom_edits": {str(i): f"custom text {i}"},
                "dual_sub": True,
                "sec_s_idx": 1 if i % 2 == 0 else 0,
                "audio_boost": True,
                "chapter_title": f"Chapter {i}",
                "duration": 200.0,
            }
            sync_clipper_state_from_body(session, body, opt=opt)
            _apply_session_sub_styles(opt, session)

        # Directly inject potential circular reference into subtitle track dicts
        sub1["self_ref"] = sub1
        sub2["other_ref"] = sub1
        session.subtitle_tracks = [sub1, sub2]

        # generate_preview_html must sanitize and succeed cleanly without ValueError
        html_out = generate_preview_html(
            url=session.url,
            video_title=session.video_title,
            stream_url="https://example.com/stream.mp4",
            options=session.options,
            subtitle_tracks=session.subtitle_tracks,
            selected_sub_track=opt.selected_subtitle_track,
            sid=session.sid,
            bridge_port=9654,
        )
        self.assertIsInstance(html_out, str)
        self.assertIn("Never Gonna Give You Up", html_out)

    def test_show_cached_quality_modal_resets_clip_and_filename(self):
        """2. _show_cached_quality_modal resets previous clip/chapter attributes and clears [Clip] suffix."""
        class MockApp(MediaOptionsActionsMixin):
            def __init__(self):
                self.root = None
                self.conn_var = MagicMock()
                self.conn_var.get.return_value = "8"
                self.entry_custom_speed = MagicMock()
                self.entry_custom_speed.get.return_value = "0"
                self.history_manager = None
                self._pending_media_context = None

            def _get_base_downloads_dir(self):
                return "C:\\Downloads"

            def _theme_dict(self):
                return {"c_bg": "#1e1e1e"}

        app = MockApp()
        raw_opt = VideoFormatOption(
            format_id="22",
            resolution_label="720p (HD)",
            height=720,
            ext="mp4",
            filesize_approx=25_000_000,
            fps=30,
            vcodec="avc1",
            acodec="mp4a",
            video_url="https://example.com/720.mp4"
        )
        # Previous run had clip and chapter set
        raw_opt.clip_start_sec = 12.5
        raw_opt.clip_end_sec = 45.0
        raw_opt.selected_chapter_title = "Highlight"
        raw_opt.dual_subtitle_enabled = True
        raw_opt.subtitle_custom_edits = {"0": "edit"}
        raw_opt.audio_boost_enabled = True
        raw_opt.audio_volume_percent = 150

        ctx = {
            "info": {"title": "Wildlife Documentary", "duration": 300},
            "options": [raw_opt],
            "url": "https://www.youtube.com/watch?v=wildlife123",
            "final_dest": "C:\\Downloads\\Wildlife Documentary [Highlight] [Clip].mp4",
            "subtitle_tracks": [{"language": "ar", "label": "Arabic", "style_config": {"clip_start": 12.5}}],
        }

        with patch("faqih_downloader.ui.modals.quality_modal.QualitySelectionModal.__init__", return_value=None):
            app._show_cached_quality_modal(ctx)

        # Context must be cleanly reset
        pending = app._pending_media_context
        self.assertIsNotNone(pending)
        res_opt = pending["options"][0]
        self.assertIsNone(res_opt.clip_start_sec)
        self.assertIsNone(res_opt.clip_end_sec)
        self.assertIsNone(res_opt.selected_chapter_title)
        self.assertFalse(res_opt.dual_subtitle_enabled)
        self.assertFalse(res_opt.audio_boost_enabled)
        self.assertEqual(res_opt.audio_volume_percent, 100)

        # Filename must NOT retain the stale [Highlight] or [Clip] tags
        clean_dest = pending["final_dest"]
        self.assertNotIn("[Highlight]", clean_dest)
        self.assertNotIn("[Clip]", clean_dest)
        self.assertTrue(clean_dest.endswith("Wildlife Documentary.mp4") or "Wildlife Documentary" in clean_dest)

    def test_googlevideo_chunk_worker_8mb_window_and_continuation(self):
        """3. TurboDownloadEngine chunk worker downloads googlevideo URL in sequential 8MB windows without EOF error."""
        engine = TurboDownloadEngine(
            url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=123",
            destination_path="dummy_gv.mp4",
            max_connections=1,
            allow_dynamic_split=False,
        )
        engine.is_running = True
        engine.supports_ranges = True
        engine.is_googlevideo = True
        total_test_size = 20 * 1024 * 1024  # 20 MB stream (requires 3 windows: 8MB, 8MB, 4MB)
        engine.total_size = total_test_size

        chunk = DownloadChunk(
            chunk_id=0,
            start_byte=0,
            end_byte=total_test_size - 1,
            downloaded_bytes=0,
            status="pending",
        )
        chunk.part_filepath = os.path.join(os.path.dirname(__file__), "test_gv_part.tmp")

        # Mock urllib.request.urlopen to track range requests and simulate successful byte serving
        ranges_requested = []

        class FakeHTTPResponse:
            def __init__(self, data, code=206):
                self._buf = io.BytesIO(data)
                self.code = code
            def read(self, amt=-1):
                return self._buf.read(amt)
            def getcode(self):
                return self.code
            def close(self):
                pass

        def fake_urlopen(req, timeout=15, context=None):
            rng_hdr = req.get_header("Range")
            ranges_requested.append(rng_hdr)
            parts = rng_hdr.replace("bytes=", "").split("-")
            s, e = int(parts[0]), int(parts[1])
            seg_len = e - s + 1
            return FakeHTTPResponse(b"X" * seg_len, code=206)

        try:
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                engine._chunk_worker(chunk)

            # Verification:
            # 1. Chunk completed
            self.assertEqual(chunk.status, "completed")
            self.assertEqual(chunk.downloaded_bytes, total_test_size)

            # 2. Sequential 8MB windows were requested:
            # Window 1: 0 - 8388607 (8 MB)
            # Window 2: 8388608 - 16777215 (8 MB)
            # Window 3: 16777216 - 20971519 (4 MB)
            expected_w1 = f"bytes=0-{GOOGLEVIDEO_WINDOW_BYTES - 1}"
            expected_w2 = f"bytes={GOOGLEVIDEO_WINDOW_BYTES}-{2 * GOOGLEVIDEO_WINDOW_BYTES - 1}"
            expected_w3 = f"bytes={2 * GOOGLEVIDEO_WINDOW_BYTES}-{total_test_size - 1}"

            self.assertEqual(ranges_requested, [expected_w1, expected_w2, expected_w3])
        finally:
            if os.path.exists(chunk.part_filepath):
                try: os.remove(chunk.part_filepath)
                except Exception: pass

    def test_ffmpeg_reconnect_parameters_in_clipped_stream_direct(self):
        """4. download_clipped_stream_direct passes safe Wi-Fi reconnect args to FFmpeg for HTTP streams."""
        si = YouTubeStreamInfo(
            video_id="video123",
            title="Test Stream",
            clean_filename="Test_Stream",
            is_progressive=False,
            video_url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?id=video",
            audio_url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?id=audio",
            video_size=10_000_000,
            audio_size=2_000_000,
            duration=60,
        )
        si.clip_start_sec = 5.0
        si.clip_end_sec = 15.0

        coordinator = MagicMock()
        coordinator.stream_info = si
        coordinator.destination_path = os.path.join(os.path.dirname(__file__), "test_clip.mp4")
        coordinator.is_running = True
        coordinator.is_paused = False
        coordinator._cancel_event = threading.Event()
        coordinator._lock = threading.Lock()

        captured_cmd = []

        class MockProc:
            def __init__(self, cmd, *args, **kwargs):
                captured_cmd.extend(cmd)
                self.pid = 12345
                self.stderr = io.BytesIO(b"time=00:00:10.00 size=5000kB\n")
                self.returncode = 0
            def wait(self, timeout=None):
                return 0
            def poll(self):
                return 0

        with patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"), \
             patch("subprocess.Popen", side_effect=MockProc):
            download_clipped_stream_direct(coordinator)

        # Verify safe reconnect arguments exist in the command
        cmd_str = " ".join(captured_cmd)
        self.assertIn("-reconnect 1", cmd_str)
        self.assertIn("-reconnect_streamed 1", cmd_str)
        self.assertIn("-reconnect_on_network_error 1", cmd_str)
        self.assertIn("-reconnect_delay_max 4", cmd_str)
        self.assertIn("-rw_timeout 15000000", cmd_str)


if __name__ == "__main__":
    unittest.main()
