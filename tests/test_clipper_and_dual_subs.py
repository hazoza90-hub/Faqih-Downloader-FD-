"""
Unit and Integration Tests for Smart Live Clipper & Dual Bilingual Subtitles.
Tests:
1. filter_and_shift_cues_for_clip (temporal shifting, boundary conditions, edge cases)
2. apply_custom_cue_edits (index-based, timestamp-based, text-based, and empty string replacement)
3. merge_bilingual_cues and generate_styled_ass_file with Default & Secondary styles
4. Long sentence bilingual cues preservation (no splitting across [[DUAL]])
5. trim_media_file using real FFmpeg execution with probed duration accuracy
6. prepare_post_download_subtitles and export_cues_to_srt for soft_embed / srt_only modes
7. sync_clipper_state_from_body and process_post_download_clip_and_subtitles pipeline
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import subprocess

_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from faqih_downloader.services.media_clipper_engine import (
    apply_custom_cue_edits,
    filter_and_shift_cues_for_clip,
    merge_bilingual_cues,
    trim_media_file,
    probe_media_duration,
    export_cues_to_srt,
    prepare_post_download_subtitles,
    process_post_download_clip_and_subtitles,
    sync_clipper_state_from_body,
    enrich_stream_info_with_clip,
    estimate_clip_total_bytes,
    download_clipped_stream_direct,
)
from faqih_downloader.core.engine import TurboDownloadEngine
from faqih_downloader.services.subtitle_processor import burn_subtitle_into_video
from faqih_downloader.services.subtitle_style_engine import generate_styled_ass_file, normalize_and_dedupe_cues
from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo
from faqih_downloader.services.audio_and_chapters_engine import (
    extract_video_chapters,
    build_smart_auto_chapters,
    get_studio_audio_boost_filter,
    apply_audio_boost_to_file,
)
from faqih_downloader.ui.modals.preview_clipper_studio import (
    get_clipper_toolbar_html,
    get_clipper_js,
)
from faqih_downloader.services.preview_stream_bridge import (
    PreviewSession,
    PreviewBridgeRequestHandler,
    register_preview_session,
    get_preview_session,
    unregister_preview_session,
)


class TestClipperAndDualSubs(unittest.TestCase):

    def test_filter_and_shift_cues_for_clip(self):
        cues = [
            {"start": 1.0, "end": 4.0, "text": "Intro"},
            {"start": 5.0, "end": 9.0, "text": "Clip Segment 1"},
            {"start": 9.5, "end": 14.0, "text": "Clip Segment 2"},
            {"start": 16.0, "end": 20.0, "text": "Outro"},
        ]
        # Clip from 5.0 to 12.0
        shifted = filter_and_shift_cues_for_clip(cues, clip_start=5.0, clip_end=12.0)
        self.assertEqual(len(shifted), 2)

        # First kept cue: originally [5.0, 9.0] -> shifted: [0.0, 4.0]
        self.assertAlmostEqual(shifted[0]["start"], 0.0)
        self.assertAlmostEqual(shifted[0]["end"], 4.0)
        self.assertEqual(shifted[0]["text"], "Clip Segment 1")

        # Second kept cue: originally [9.5, 14.0] -> clamped to 12.0 -> shifted: [4.5, 7.0]
        self.assertAlmostEqual(shifted[1]["start"], 4.5)
        self.assertAlmostEqual(shifted[1]["end"], 7.0)
        self.assertEqual(shifted[1]["text"], "Clip Segment 2")

        # Tuple format support
        tuple_cues = [(0.0, 3.0, "Skip"), (4.0, 8.0, "Keep")]
        res_tup = filter_and_shift_cues_for_clip(tuple_cues, clip_start=4.0, clip_end=10.0)
        self.assertEqual(len(res_tup), 1)
        self.assertAlmostEqual(res_tup[0][0], 0.0)
        self.assertAlmostEqual(res_tup[0][1], 4.0)
        self.assertEqual(res_tup[0][2], "Keep")

        # Invalid or non-clipping ranges return unchanged
        self.assertEqual(filter_and_shift_cues_for_clip(cues, 10.0, 5.0), cues)
        self.assertEqual(filter_and_shift_cues_for_clip(cues, -1.0, 5.0), cues)
        self.assertEqual(filter_and_shift_cues_for_clip([], 0.0, 10.0), [])

    def test_apply_custom_cue_edits(self):
        cues = [
            {"start": 1.0, "end": 3.0, "text": "مرحبا بك"},
            {"start": 4.0, "end": 6.0, "text": "هذا خطأ مطبعي"},
            {"start": 7.0, "end": 9.0, "text": "النهاية"},
        ]
        # Edit cue 1 by index, cue 2 by exact text, and cue 0 to empty string ""
        edits = {
            "0": "",
            "1": "هذا نص مصحح بدقة",
            "النهاية": "النهاية السعيدة",
        }
        updated = apply_custom_cue_edits(cues, edits)
        self.assertEqual(updated[0]["text"], "")
        self.assertEqual(updated[1]["text"], "هذا نص مصحح بدقة")
        self.assertEqual(updated[2]["text"], "النهاية السعيدة")

        # Test tuple cues
        tuple_cues = [(1.0, 3.0, "Original")]
        updated_tup = apply_custom_cue_edits(tuple_cues, {"0": "Modified"})
        self.assertEqual(updated_tup[0][2], "Modified")

        # None or empty edits return cues as is
        self.assertEqual(apply_custom_cue_edits(cues, None), cues)
        self.assertEqual(apply_custom_cue_edits(cues, {}), cues)

    def test_merge_bilingual_cues(self):
        primary = [
            {"start": 1.0, "end": 4.0, "text": "مرحبا بالعالم"},
            {"start": 5.0, "end": 8.0, "text": "فقيه التنزيلات"},
            {"start": 9.0, "end": 12.0, "text": "بدون تطابق"},
        ]
        secondary = [
            {"start": 1.2, "end": 3.9, "text": "Hello World"},
            {"start": 5.1, "end": 7.8, "text": "Faqih Downloader"},
            {"start": 15.0, "end": 18.0, "text": "Far Away"},
        ]
        merged = merge_bilingual_cues(primary, secondary)
        self.assertEqual(len(merged), 3)
        self.assertIn("[[DUAL]]", merged[0]["text"])
        self.assertEqual(merged[0]["text"], "مرحبا بالعالم\n[[DUAL]]Hello World")
        self.assertIn("Faqih Downloader", merged[1]["text"])
        self.assertEqual(merged[2]["text"], "بدون تطابق")

    def test_bilingual_cue_long_sentence_defense(self):
        # Primary has 7 words, Secondary has 9 words -> total 16 words (> 10 words default threshold)
        long_dual_cue = (0.0, 5.0, "هذه هي الجملة الأولى في المقطع التجريبي للترجمة\n[[DUAL]]This is the first sentence in the test subtitle clip")
        res = normalize_and_dedupe_cues([long_dual_cue])
        # Must NOT be split across [[DUAL]]
        self.assertEqual(len(res), 1)
        self.assertIn("[[DUAL]]", res[0][2])
        self.assertIn("هذه هي الجملة الأولى", res[0][2])
        self.assertIn("This is the first sentence", res[0][2])

    def test_generate_styled_ass_file_with_clip_and_dual_subs(self):
        srt_content = """1
00:00:01,000 --> 00:00:04,000
مرحبا بكم جميعا

2
00:00:06,000 --> 00:00:10,000
تجربة قاص المقاطع الذكي

3
00:00:12,000 --> 00:00:15,000
نهاية الفيديو
"""
        sec_srt_content = """1
00:00:01,200 --> 00:00:03,800
Welcome everyone

2
00:00:06,200 --> 00:00:09,800
Smart Live Clipper Test
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            srt_path = os.path.join(tmp_dir, "primary.srt")
            sec_srt_path = os.path.join(tmp_dir, "secondary.srt")
            ass_path = os.path.join(tmp_dir, "output.ass")

            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            with open(sec_srt_path, "w", encoding="utf-8") as f:
                f.write(sec_srt_content)

            custom_edits = {"1": "تجربة القاص المصححة"}
            # Clip from 5.0s to 11.0s, secondary SRT, and custom edit
            ok = generate_styled_ass_file(
                srt_source=srt_path,
                output_ass_path=ass_path,
                custom_edits=custom_edits,
                clip_start=5.0,
                clip_end=11.0,
                secondary_srt_source=sec_srt_path,
            )
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(ass_path))

            with open(ass_path, "r", encoding="utf-8") as f:
                ass_text = f.read()

            # Verify styles
            self.assertIn("Style: Default", ass_text)
            self.assertIn("Style: Secondary", ass_text)
            self.assertIn("&H00E2E8F0", ass_text)

            # Verify cue shifting: cue was originally at 6.0s, so in clip from 5.0s it should start around 1.0s (0:00:01.00)
            self.assertIn("Dialogue: 0,0:00:01.00", ass_text)
            # Verify edited text was applied
            self.assertIn("تجربة القاص المصححة", ass_text)
            # Verify dual styling switch
            self.assertIn(r"\N{\rSecondary}Smart Live Clipper Test", ass_text)
            # Cue 1 (1.0s - 4.0s) should NOT be present because clip_start is 5.0
            self.assertNotIn("مرحبا بكم جميعا", ass_text)

    def test_trim_media_file_with_ffmpeg(self):
        from faqih_downloader.services.media_env_helpers import find_ffmpeg_bin
        ffmpeg_bin = find_ffmpeg_bin()
        if not ffmpeg_bin:
            self.skipTest("FFmpeg not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_src = os.path.join(tmp_dir, "src_video.mp4")
            # Generate a 4-second synthetic test video with audio
            cmd_gen = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=4:size=160x120:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-b:a", "64k",
                test_src
            ]
            cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
            gen_res = subprocess.run(cmd_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=cflags)
            self.assertEqual(gen_res.returncode, 0)
            self.assertTrue(os.path.isfile(test_src))

            # Trim to [1.0s .. 2.5s] -> expected duration 1.5s
            ok = trim_media_file(test_src, clip_start=1.0, clip_end=2.5, ffmpeg_bin=ffmpeg_bin)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(test_src))
            dur = probe_media_duration(test_src, ffmpeg_bin)
            self.assertGreater(dur, 0.0)
            self.assertAlmostEqual(dur, 1.5, delta=0.4)

    def test_export_cues_to_srt_and_dual_rendering(self):
        cues = [
            {"start": 0.0, "end": 3.0, "text": "مرحبا\n[[DUAL]]Hello"},
            {"start": 4.0, "end": 7.0, "text": "العالم\n[[DUAL]]World"},
        ]
        with tempfile.TemporaryDirectory() as td:
            srt_f = os.path.join(td, "test_dual.srt")
            ok = export_cues_to_srt(cues, srt_f)
            self.assertTrue(ok)
            with open(srt_f, "r", encoding="utf-8") as f:
                c = f.read()
            self.assertIn("00:00:00,000 --> 00:00:03,000", c)
            self.assertIn("مرحبا\nHello", c)
            self.assertNotIn("[[DUAL]]", c)

    def test_sync_clipper_state_and_models(self):
        class DummySession:
            def __init__(self):
                self.clip_start = 0.0
                self.clip_end = 0.0
                self.sub_custom_edits = {}
                self.dual_sub = False
                self.sec_s_idx = -1
                self.subtitle_tracks = [
                    {"sub_id": "none", "language": "none"},
                    {"sub_id": "ar", "language": "Arabic", "url": "http://127.0.0.1/ar.vtt"},
                    {"sub_id": "en", "language": "English", "url": "http://127.0.0.1/en.vtt"},
                ]
                self.selected_sub_track = self.subtitle_tracks[1]
                self.modal_ref = None

        session = DummySession()
        body = {
            "clip_start": 4.5,
            "clip_end": 18.2,
            "sub_custom_edits": {"0": "Test Fix"},
            "dual_sub": True,
            "sec_s_idx": 2,
        }
        opt = VideoFormatOption(
            format_id="18", resolution_label="360p", height=360,
            ext="mp4", filesize_approx=1000
        )
        sync_clipper_state_from_body(session, body, opt)

        self.assertAlmostEqual(session.clip_start, 4.5)
        self.assertAlmostEqual(session.clip_end, 18.2)
        self.assertTrue(session.dual_sub)
        self.assertAlmostEqual(opt.clip_start_sec, 4.5)
        self.assertAlmostEqual(opt.clip_end_sec, 18.2)
        self.assertTrue(opt.dual_subtitle_enabled)
        self.assertIsNotNone(opt.secondary_subtitle_track)
        self.assertEqual(opt.secondary_subtitle_track["sub_id"], "en")

        # Test enrichment of YouTubeStreamInfo
        s_info = YouTubeStreamInfo(
            video_id="test_id", title="Title", clean_filename="Title.mp4",
            is_progressive=True, video_url="http://test"
        )
        enrich_stream_info_with_clip(s_info, opt)
        self.assertAlmostEqual(s_info.clip_start_sec, 4.5)
        self.assertAlmostEqual(s_info.clip_end_sec, 18.2)
        self.assertTrue(s_info.dual_subtitle_enabled)
        self.assertEqual(s_info.subtitle_custom_edits, {"0": "Test Fix"})

    def test_process_post_download_clip_and_companion_srt_rename(self):
        with tempfile.TemporaryDirectory() as td:
            vid = os.path.join(td, "MyVideo.mp4")
            srt = os.path.join(td, "MyVideo.srt")
            with open(vid, "wb") as f: f.write(b"video_bytes")
            with open(srt, "w", encoding="utf-8") as f: f.write("1\n00:00:00,000 --> 00:00:01,000\nHi\n")

            s_info = YouTubeStreamInfo(
                video_id="test", title="MyVideo", clean_filename="MyVideo.mp4",
                is_progressive=True, video_url="http://test",
                clip_start_sec=1.0, clip_end_sec=5.0
            )
            # Calling process_post_download_clip_and_subtitles
            res_path = process_post_download_clip_and_subtitles(s_info, vid)
            self.assertIn("[Clip]", res_path)
            self.assertTrue(os.path.isfile(res_path))
            # Companion SRT must also be renamed
            clip_srt = os.path.join(td, "MyVideo [Clip].srt")
            self.assertTrue(os.path.isfile(clip_srt))

    def test_handle_subtitles_post_download_hard_burn_with_clip_no_double_shift(self):
        """Verifies hard_burn mode with clip does not double-shift timestamps into ASS file."""
        from faqih_downloader.services.subtitle_processor import handle_subtitles_post_download
        from faqih_downloader.services.subtitle_style_engine import generate_styled_ass_file as real_generate_ass
        from unittest.mock import patch

        srt_content = """1
00:00:31,000 --> 00:00:35,000
جملة اختبار القص مع الحرق
"""
        with tempfile.TemporaryDirectory() as td:
            v_path = os.path.join(td, "Clip_Test [Burn].mp4")
            srt_path = os.path.join(td, "Clip_Test [Burn].srt")
            with open(v_path, "wb") as f: f.write(b"video_bytes")
            with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)

            stream_info = YouTubeStreamInfo(
                video_id="clip_test_1",
                title="Clip Test",
                clean_filename="Clip_Test [Burn].mp4",
                is_progressive=True,
                video_url="http://test_url",
                clip_start_sec=30.0,
                clip_end_sec=36.0,
                subtitle_track={"sub_id": "ar", "language": "Arabic", "url": "http://fake.vtt"},
                subtitle_embed_mode="hard_burn",
                subtitle_preset="youtube",
            )

            captured_ass_texts = []
            def spy_generate_styled_ass(srt_source, output_ass_path, **kwargs):
                res = real_generate_ass(srt_source, output_ass_path, **kwargs)
                if os.path.isfile(output_ass_path):
                    with open(output_ass_path, "r", encoding="utf-8") as af:
                        captured_ass_texts.append(af.read())
                return res

            def fake_run(cmd, *args, **kwargs):
                out_file = cmd[-1]
                with open(out_file, "wb") as f:
                    f.write(b"burned_result_bytes")
                from subprocess import CompletedProcess
                return CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", return_value=srt_path), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.subtitle_style_engine.generate_styled_ass_file", side_effect=spy_generate_styled_ass), \
                 patch("faqih_downloader.services.subtitle_processor.subprocess.run", side_effect=fake_run):
                handle_subtitles_post_download(stream_info, v_path)

            self.assertTrue(len(captured_ass_texts) > 0, "generate_styled_ass_file was not called")
            ass_text = captured_ass_texts[0]

            # The cue originally at 31.0s-35.0s shifted by -30.0s must be at 1.0s-5.0s (0:00:01.00 -> 0:00:05.00)
            self.assertIn("0:00:01.00,0:00:05.00", ass_text)
            self.assertIn("جملة اختبار القص مع الحرق", ass_text)

    def test_handle_subtitles_post_download_hard_burn_fallback_soft_embed(self):
        """Verifies hard_burn failure falls back to soft_embed with single subtitle shift."""
        from faqih_downloader.services.subtitle_processor import handle_subtitles_post_download
        from unittest.mock import patch, MagicMock

        srt_content = """1
00:00:20,000 --> 00:00:25,000
Fallback test
"""
        with tempfile.TemporaryDirectory() as td:
            v_path = os.path.join(td, "Vid [Sub-Burned].mp4")
            srt_path = os.path.join(td, "Vid [Sub-Burned].srt")
            with open(v_path, "wb") as f: f.write(b"video_bytes")
            with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)

            stream_info = YouTubeStreamInfo(
                video_id="fallback_1",
                title="Fallback Test",
                clean_filename="Vid [Sub-Burned].mp4",
                is_progressive=True,
                video_url="http://test_url",
                clip_start_sec=15.0,
                clip_end_sec=25.0,
                subtitle_track={"sub_id": "en", "language": "English", "url": "http://fake.vtt"},
                subtitle_embed_mode="hard_burn",
            )

            captured_embed_srt = []
            def spy_embed(vid, srt, *args, **kwargs):
                with open(srt, "r", encoding="utf-8") as sf:
                    captured_embed_srt.append(sf.read())
                return True

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", return_value=srt_path), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.subtitle_processor.burn_subtitle_into_video", return_value=False), \
                 patch("faqih_downloader.services.subtitle_processor.embed_subtitle_into_mp4", side_effect=spy_embed):
                final_path = handle_subtitles_post_download(stream_info, v_path)

            self.assertNotIn("[Sub-Burned]", final_path)
            self.assertEqual(len(captured_embed_srt), 1)
            # The SRT content passed to embed should have been shifted by -15s (20s-25s -> 5s-10s)
            self.assertIn("00:00:05,000 --> 00:00:10,000", captured_embed_srt[0])
            self.assertIn("Fallback test", captured_embed_srt[0])

    def test_handle_subtitles_post_download_hard_burn_non_mp4(self):
        """Verifies hard_burn on non-mp4 files strips burn tag and shifts standalone SRT."""
        from faqih_downloader.services.subtitle_processor import handle_subtitles_post_download
        from unittest.mock import patch

        srt_content = """1
00:00:40,000 --> 00:00:45,000
Non-mp4 clip cue
"""
        with tempfile.TemporaryDirectory() as td:
            v_path = os.path.join(td, "NonMp4 [Sub-Burned].mkv")
            srt_path = os.path.join(td, "NonMp4 [Sub-Burned].srt")
            with open(v_path, "wb") as f: f.write(b"mkv_bytes")
            with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)

            stream_info = YouTubeStreamInfo(
                video_id="mkv_1",
                title="MKV Test",
                clean_filename="NonMp4 [Sub-Burned].mkv",
                is_progressive=True,
                video_url="http://test_url",
                clip_start_sec=35.0,
                clip_end_sec=50.0,
                subtitle_track={"sub_id": "en", "language": "English", "url": "http://fake.vtt"},
                subtitle_embed_mode="hard_burn",
            )

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", return_value=srt_path), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"):
                final_path = handle_subtitles_post_download(stream_info, v_path)

            self.assertNotIn("[Sub-Burned]", final_path)
            with open(srt_path, "r", encoding="utf-8") as sf:
                shifted_srt = sf.read()
            # 40s-45s shifted by -35s -> 5s-10s
            self.assertIn("00:00:05,000 --> 00:00:10,000", shifted_srt)

    def test_generated_preview_javascript_has_zero_syntax_errors(self):
        """Verifies that generate_preview_html produces syntactically valid JavaScript across configs."""
        import re
        import shutil
        from faqih_downloader.ui.modals.preview_html_builder import generate_preview_html

        test_configs = [
            {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "video_title": "Test Video Title with 'Quotes' and Special Characters",
                "stream_url": "http://127.0.0.1:9655/stream_video?sid=test_session",
                "vtt_data_uri": "data:text/vtt;base64,V0VCVlRUCgoxCjAwOjAwOjAxLjAwMCAtLT4gMDA6MDA6MDUuMDAwCuinmNmF2YTYqQo=",
                "video_id": "dQw4w9WgXcQ",
                "sub_label": "Arabic",
                "session_id": "test_session",
                "quality_options": [{"format_id": "18", "format_note": "360p", "ext": "mp4", "filesize": 1000}],
                "audio_tracks": [{"label": "Original Audio", "language": "en"}],
                "subtitle_tracks": [{"label": "None", "language": "none"}, {"label": "Arabic", "language": "ar"}],
            },
            {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "video_title": "Web Player Fallback Title with Quotes",
                "stream_url": None,
                "session_id": "sess_no_stream",
                "clip_start": 10.0,
                "clip_end": 45.0,
                "dual_sub": True,
                "subtitle_preset": "tiktok",
            },
            {
                "url": "https://twitter.com/i/status/123",
                "video_title": "Empty Tracks & Generic Platform",
                "stream_url": "http://127.0.0.1:9655/stream",
                "session_id": "sess_generic",
                "quality_options": [],
                "audio_tracks": [],
                "subtitle_tracks": [],
            },
            {
                "url": "https://www.youtube.com/watch?v=chapters_test",
                "video_title": "Video with Chapters & Studio Boost",
                "stream_url": "http://127.0.0.1:9655/stream",
                "session_id": "sess_chapters",
                "chapters": [
                    {"title": "00:00 Intro & Welcome", "start_time": 0.0, "end_time": 45.0},
                    {"title": "00:45 Studio Sound 'Filter'", "start_time": 45.0, "end_time": 120.0},
                ],
                "audio_boost": True,
                "chapter_title": "Studio Sound 'Filter'",
            },
        ]

        node_bin = shutil.which("node")
        for i, cfg in enumerate(test_configs):
            html = generate_preview_html(**cfg)
            match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
            self.assertIsNotNone(match, f"Config {i}: No <script> block found in generated preview HTML")
            js_code = match.group(1)

            # Check that no unescaped newlines broke string literals
            self.assertNotIn('indexOf("\n")', js_code)
            self.assertNotIn('indexOf(\'\n\')', js_code)
            self.assertNotIn(' + "\n" + ', js_code)
            self.assertNotIn(' + \'\n\' + ', js_code)

            # If node is available on system, execute node --check
            if node_bin:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                    f.write(js_code)
                    tmp_js = f.name
                try:
                    proc = subprocess.run([node_bin, "--check", tmp_js], capture_output=True, text=True)
                    self.assertEqual(
                        proc.returncode, 0,
                        f"Config {i}: node --check failed with exit code {proc.returncode}:\n{proc.stderr}\n{proc.stdout}"
                    )
                finally:
                    if os.path.exists(tmp_js):
                        try:
                            os.remove(tmp_js)
                        except OSError:
                            pass

    def test_extract_video_chapters_official(self):
        info_dict = {
            "chapters": [
                {"title": "Introduction", "start_time": 0.0, "end_time": 30.0},
                {"title": "Main Content", "start_time": 30.0, "end_time": 0.0},
                {"title": "Outro", "start_time": 90.0, "end_time": 0.0},
            ]
        }
        chapters = extract_video_chapters(info_dict, total_duration=120.0)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0]["title"], "Introduction")
        self.assertEqual(chapters[0]["start_time"], 0.0)
        self.assertEqual(chapters[0]["end_time"], 30.0)
        self.assertEqual(chapters[1]["end_time"], 90.0)
        self.assertEqual(chapters[2]["end_time"], 120.0)

    def test_extract_video_chapters_from_description(self):
        desc = """
        شاهد هذا الفيديو المفيد!
        الفصول:
        00:00 المقدمة
        03:45 - الفصل الأول: الأساسيات
        [07:15] الفصل الثاني: التطبيق العملي
        (12:30) خاتمة وتوصيات
        """
        info_dict = {"description": desc}
        chapters = extract_video_chapters(info_dict, total_duration=900.0)
        self.assertEqual(len(chapters), 4)
        self.assertEqual(chapters[0]["start_time"], 0.0)
        self.assertIn("المقدمة", chapters[0]["title"])
        self.assertEqual(chapters[1]["start_time"], 225.0)
        self.assertIn("الأساسيات", chapters[1]["title"])
        self.assertEqual(chapters[2]["start_time"], 435.0)
        self.assertEqual(chapters[3]["start_time"], 750.0)
        self.assertEqual(chapters[3]["end_time"], 900.0)

    def test_get_studio_audio_boost_filter(self):
        filt = get_studio_audio_boost_filter()
        self.assertIn("highpass=f=75", filt)
        self.assertIn("acompressor=threshold=-20dB", filt)
        self.assertIn("volume=1.45", filt)
        self.assertIn("alimiter=limit=0.95", filt)

    def test_apply_audio_boost_to_file_mock(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            video_f = os.path.join(td, "test.mp4")
            with open(video_f, "wb") as f:
                f.write(b"fake_mp4_bytes")

            def fake_ffmpeg(cmd, cancel_event=None):
                out_path = cmd[-1]
                with open(out_path, "wb") as out_f:
                    out_f.write(b"boosted_mp4_bytes")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

            with patch("faqih_downloader.services.subtitle_processor.run_cancellable_ffmpeg", side_effect=fake_ffmpeg):
                ok = apply_audio_boost_to_file(video_f, ffmpeg_bin="ffmpeg")
                self.assertTrue(ok)
                with open(video_f, "rb") as rf:
                    self.assertEqual(rf.read(), b"boosted_mp4_bytes")

    def test_sync_clipper_state_audio_boost_and_chapter(self):
        from unittest.mock import MagicMock
        session = MagicMock()
        session.clip_start = 0.0
        session.clip_end = 0.0
        session.subtitle_tracks = []
        opt = VideoFormatOption(
            format_id="18", resolution_label="360p", height=360, ext="mp4", filesize_approx=1000
        )
        body = {
            "clip_start": 10.0,
            "clip_end": 50.0,
            "audio_boost": True,
            "chapter_title": "First Chapter",
        }
        sync_clipper_state_from_body(session, body, opt=opt)
        self.assertTrue(session.audio_boost)
        self.assertEqual(session.chapter_title, "First Chapter")
        self.assertTrue(opt.audio_boost_enabled)
        self.assertEqual(opt.selected_chapter_title, "First Chapter")

    def test_process_post_download_with_audio_boost_and_chapter(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "MyVideo.mp4")
            with open(target, "wb") as f:
                f.write(b"video_data")
            info = YouTubeStreamInfo(
                video_id="vid123",
                title="MyVideo",
                clean_filename="MyVideo.mp4",
                is_progressive=True,
                video_url="http://test",
                clip_start_sec=10.0,
                clip_end_sec=30.0,
                audio_boost_enabled=True,
                selected_chapter_title="Intro",
            )
            with patch("faqih_downloader.services.media_clipper_engine.trim_media_file", return_value=True), \
                 patch("faqih_downloader.services.media_clipper_engine.probe_media_duration", return_value=100.0), \
                 patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"):
                res_path = process_post_download_clip_and_subtitles(info, target)
                self.assertIn("[Intro]", res_path)
                self.assertIn("[Clip]", res_path)

    def test_extract_video_chapters_official_unsorted(self):
        info_dict = {
            "chapters": [
                {"title": "Outro", "start_time": 90.0, "end_time": 0.0},
                {"title": "Introduction", "start_time": 0.0, "end_time": 0.0},
                {"title": "Main Content", "start_time": 30.0, "end_time": 0.0},
            ]
        }
        chapters = extract_video_chapters(info_dict, total_duration=120.0)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0]["title"], "Introduction")
        self.assertEqual(chapters[0]["start_time"], 0.0)
        self.assertEqual(chapters[0]["end_time"], 30.0)
        self.assertEqual(chapters[1]["title"], "Main Content")
        self.assertEqual(chapters[1]["start_time"], 30.0)
        self.assertEqual(chapters[1]["end_time"], 90.0)
        self.assertEqual(chapters[2]["title"], "Outro")
        self.assertEqual(chapters[2]["start_time"], 90.0)
        self.assertEqual(chapters[2]["end_time"], 120.0)

    def test_extract_video_chapters_edge_cases(self):
        desc = """
        00:00 Intro
        03:45- Chapter 1
        05:30: Chapter 2
        08:00| Discussion
        120:00 Big Jump
        """
        chapters = extract_video_chapters({"description": desc}, total_duration=8000.0)
        self.assertEqual(len(chapters), 5)
        self.assertEqual(chapters[0]["title"], "Intro")
        self.assertEqual(chapters[1]["title"], "Chapter 1")
        self.assertEqual(chapters[1]["start_time"], 225.0)
        self.assertEqual(chapters[2]["title"], "Chapter 2")
        self.assertEqual(chapters[2]["start_time"], 330.0)
        self.assertEqual(chapters[3]["title"], "Discussion")
        self.assertEqual(chapters[3]["start_time"], 480.0)
        self.assertEqual(chapters[4]["title"], "Big Jump")
        self.assertEqual(chapters[4]["start_time"], 7200.0)

        # Arabic-Indic numerals
        arabic_desc = "٠٠:٠٠ المقدمة\n٠٣:٤٥ الأساسيات"
        ar_chapters = extract_video_chapters({"description": arabic_desc}, total_duration=500.0)
        self.assertEqual(len(ar_chapters), 2)
        self.assertEqual(ar_chapters[0]["start_time"], 0.0)
        self.assertEqual(ar_chapters[1]["start_time"], 225.0)

        # Single timestamp mid-video rejected as not a chapter list
        single_desc = "Look at the funny dog at 03:45 in this clip!"
        self.assertEqual(extract_video_chapters({"description": single_desc}, total_duration=600.0), [])

    def test_process_post_download_avoids_double_boost_and_sanitizes_brackets(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "MyVideo.mp4")
            with open(target, "wb") as f:
                f.write(b"video_data")
            info = YouTubeStreamInfo(
                video_id="vid123",
                title="MyVideo",
                clean_filename="MyVideo.mp4",
                is_progressive=True,
                video_url="http://test",
                clip_start_sec=10.0,
                clip_end_sec=30.0,
                audio_boost_enabled=True,
                selected_chapter_title="[Intro]",
            )
            # Simulate hard burn already applied boost
            setattr(info, "_audio_boost_applied", True)
            captured_trim_args = {}
            def fake_trim(file_path, clip_start, clip_end, **kwargs):
                captured_trim_args.update(kwargs)
                return True

            with patch("faqih_downloader.services.media_clipper_engine.trim_media_file", side_effect=fake_trim), \
                 patch("faqih_downloader.services.media_clipper_engine.probe_media_duration", return_value=100.0), \
                 patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"):
                res_path = process_post_download_clip_and_subtitles(info, target)
                # Boost must NOT be requested again during trim since it was already applied
                self.assertFalse(captured_trim_args.get("audio_boost", False))
                # Brackets in chapter title must be stripped so we don't get [[Intro]]
                self.assertIn("[Intro]", res_path)
                self.assertNotIn("[[Intro]]", res_path)
                self.assertIn("[Clip]", res_path)

    def test_get_clipper_toolbar_html_always_renders_chapter_select(self):
        # Empty chapters list
        html_empty = get_clipper_toolbar_html(chapters=[])
        self.assertIn('<select id="chapterSelect"', html_empty)
        self.assertIn("📑 الفصول (تقسيم ذكي للمقطع...)", html_empty)

        # None chapters
        html_none = get_clipper_toolbar_html(chapters=None)
        self.assertIn('<select id="chapterSelect"', html_none)
        self.assertIn("📑 الفصول (تقسيم ذكي للمقطع...)", html_none)

        # Non-empty chapters list
        chapters = [
            {"title": "المقدمة", "start_time": 0.0, "end_time": 75.0},
            {"title": "الشرح الرئيسي", "start_time": 75.0, "end_time": 300.0},
        ]
        html_ch = get_clipper_toolbar_html(chapters=chapters)
        self.assertIn('<select id="chapterSelect"', html_ch)
        self.assertIn("📑 الفصول (2 فصل متاح - اختر لتحميله)", html_ch)
        self.assertIn("[00:00 - 01:15] المقدمة", html_ch)
        self.assertIn("[01:15 - 05:00] الشرح الرئيسي", html_ch)
        self.assertIn('data-start="0.00"', html_ch)
        self.assertIn('data-end="75.00"', html_ch)

    def test_clipper_js_audio_boost_true_bypass_and_node_check(self):
        js = get_clipper_js()
        # Verify function declarations
        self.assertIn("function initStudioWebAudioBoost()", js)
        self.assertIn("function applyStudioWebAudioRouting()", js)
        self.assertIn("function populateAutoChaptersIfNeeded()", js)
        self.assertIn("function requestUpdatedFilename()", js)

        # Verify True Bypass routing when disabled
        self.assertIn("item.source.connect(_studioAudioCtx.destination)", js)
        self.assertIn("item.connectedBoost = false", js)

        # Verify Presence EQ and Highpass filter in audio chain
        self.assertIn("createBiquadFilter()", js)
        self.assertIn("peaking", js)
        self.assertIn("highpass", js)
        self.assertIn("createDynamicsCompressor()", js)
        self.assertIn("2.8", js)

        # Verify chapter unselect resets clip range to full video
        self.assertIn("clipStartSec = 0.0; clipEndSec = 0.0;", js)

        # Verify JavaScript syntax via node --check
        import shutil
        node_bin = shutil.which("node")
        if node_bin:
            res = subprocess.run([node_bin, "--check"], input=js, encoding="utf-8", capture_output=True)
            self.assertEqual(res.returncode, 0, f"Node syntax error in clipper JS: {res.stderr}")

    def test_audio_boost_filter_contains_alimiter(self):
        flt = get_studio_audio_boost_filter()
        self.assertIn("alimiter", flt)
        self.assertIn("limit=0.95", flt)
        self.assertIn("highpass=f=75", flt)
        self.assertIn("acompressor=", flt)
        self.assertIn("makeup=2.5", flt)
        self.assertIn("volume=1.45", flt)

    def test_smart_auto_split_chapters(self):
        # Short video < 180s returns empty
        self.assertEqual(build_smart_auto_chapters(120.0), [])

        # 3 to 15 min: split every 300s
        ch_300 = build_smart_auto_chapters(300.0)
        self.assertEqual(len(ch_300), 1)
        self.assertEqual(ch_300[0]["start_time"], 0.0)
        self.assertEqual(ch_300[0]["end_time"], 300.0)
        self.assertTrue(ch_300[0]["is_auto"])

        ch_600 = build_smart_auto_chapters(600.0)
        self.assertEqual(len(ch_600), 2)
        self.assertEqual(ch_600[1]["start_time"], 300.0)
        self.assertEqual(ch_600[1]["end_time"], 600.0)

        # 15 to 60 min: split every 600s
        ch_1800 = build_smart_auto_chapters(1800.0)
        self.assertEqual(len(ch_1800), 3)
        self.assertEqual(ch_1800[0]["end_time"], 600.0)
        self.assertEqual(ch_1800[1]["start_time"], 600.0)
        self.assertEqual(ch_1800[2]["end_time"], 1800.0)

        # > 60 min: split every 900s
        ch_5400 = build_smart_auto_chapters(5400.0)
        self.assertEqual(len(ch_5400), 6)
        self.assertEqual(ch_5400[0]["end_time"], 900.0)

        # extract_video_chapters pure behavior without flag
        self.assertEqual(extract_video_chapters({"description": "No timestamps"}, total_duration=600.0, auto_split_if_empty=False), [])

        # extract_video_chapters fallback when auto_split_if_empty=True
        ch_fallback = extract_video_chapters({"description": "No timestamps"}, total_duration=600.0, auto_split_if_empty=True)
        self.assertEqual(len(ch_fallback), 2)
        self.assertTrue(ch_fallback[0]["is_auto"])

    def test_preview_bridge_update_filename_with_chapter_and_clip(self):
        class DummyHandler:
            def __init__(self):
                self.sent_data = None
            def _send_json(self, data):
                self.sent_data = data

        handler = DummyHandler()
        session = PreviewSession(
            sid="test_sid",
            url="http://test.com/video",
            video_title="Lecture Video",
            default_dest_path=r"C:\Downloads\Lecture Video.mp4",
        )
        opt = VideoFormatOption(
            format_id="137+140",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=1000000,
        )
        session.options = [opt]

        # 1. Update filename with chapter title and clip range
        body = {
            "q_idx": 0,
            "current_dest": session.default_dest_path,
            "chapter_title": "مقدمة الدرس",
            "clip_start": 0.0,
            "clip_end": 180.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body)
        self.assertIsNotNone(handler.sent_data)
        dest1 = handler.sent_data["dest_path"]
        self.assertIn("[1080p]", dest1)
        self.assertIn("[مقدمة الدرس]", dest1)
        self.assertIn("[Clip]", dest1)

        # 2. Switch to another chapter
        body2 = {
            "q_idx": 0,
            "current_dest": dest1,
            "chapter_title": "القسم الثاني",
            "clip_start": 180.0,
            "clip_end": 450.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body2)
        dest2 = handler.sent_data["dest_path"]
        self.assertIn("[القسم الثاني]", dest2)
        self.assertNotIn("[مقدمة الدرس]", dest2)
        self.assertIn("[Clip]", dest2)

        # 3. Reset clip back to full video (no chapter, no clip)
        body3 = {
            "q_idx": 0,
            "current_dest": dest2,
            "chapter_title": "",
            "clip_start": 0.0,
            "clip_end": 0.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body3)
        dest3 = handler.sent_data["dest_path"]
        self.assertNotIn("[القسم الثاني]", dest3)
        self.assertNotIn("[Clip]", dest3)
        self.assertIn("[1080p]", dest3)
        self.assertTrue(dest3.endswith("Lecture Video [1080p].mp4"))

        # 4. Chapter with colons / illegal characters (e.g. "01: Intro - Getting Started")
        body4 = {
            "q_idx": 0,
            "current_dest": dest3,
            "chapter_title": "01: Intro - Getting Started",
            "clip_start": 0.0,
            "clip_end": 120.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body4)
        dest4 = handler.sent_data["dest_path"]
        self.assertIn("[1080p]", dest4)
        self.assertIn("[01 Intro - Getting Started]", dest4)
        self.assertIn("[Clip]", dest4)

        # 5. Switch to auto-split chapter: "الجزء 1 (تقسيم تلقائي)"
        body5 = {
            "q_idx": 0,
            "current_dest": dest4,
            "chapter_title": "الجزء 1 (تقسيم تلقائي)",
            "clip_start": 0.0,
            "clip_end": 300.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body5)
        dest5 = handler.sent_data["dest_path"]
        self.assertNotIn("01 Intro", dest5)
        self.assertIn("[1080p]", dest5)
        self.assertIn("الجزء 1", dest5)
        self.assertIn("[Clip]", dest5)
        self.assertIn("[الجزء 1 (تقسيم تلقائي)]", dest5)
        self.assertNotIn("[الجزء 1 (تقسيم تلقائي]", dest5)
        self.assertEqual(dest5.count("("), dest5.count(")"))

        # 6. Switch to next auto-split chapter: "الجزء 2 (تقسيم تلقائي)"
        body6 = {
            "q_idx": 0,
            "current_dest": dest5,
            "chapter_title": "الجزء 2 (تقسيم تلقائي)",
            "clip_start": 300.0,
            "clip_end": 600.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body6)
        dest6 = handler.sent_data["dest_path"]
        self.assertNotIn("الجزء 1", dest6)
        self.assertIn("الجزء 2", dest6)
        self.assertIn("[Clip]", dest6)
        self.assertIn("[الجزء 2 (تقسيم تلقائي)]", dest6)
        self.assertNotIn("[الجزء 2 (تقسيم تلقائي]", dest6)
        self.assertEqual(dest6.count("("), dest6.count(")"))

        # 7. Reset to full video from auto-split chapter
        body7 = {
            "q_idx": 0,
            "current_dest": dest6,
            "chapter_title": "",
            "clip_start": 0.0,
            "clip_end": 0.0,
        }
        PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body7)
        dest7 = handler.sent_data["dest_path"]
        self.assertNotIn("الجزء 2", dest7)
        self.assertNotIn("[Clip]", dest7)
        self.assertTrue(dest7.endswith("Lecture Video [1080p].mp4"))

    def test_register_preview_session_auto_split_chapters_and_clean_filename(self):
        """
        Verifies:
        1. register_preview_session with 2700s video and empty chapters creates 5 auto-split segments.
        2. Segments are named 'الجزء X - تقسيم تلقائي' without breaking parentheses.
        3. get_clipper_toolbar_html displays '5 جزء بالتقسيم الذكي - اختر لتحميله'.
        4. _handle_api_update_filename outputs filenames without broken parentheses.
        5. Fallback duration from options[0].duration works if info_dict duration is 0.
        """
        class DummyHandler:
            def __init__(self):
                self.sent_data = None
            def _send_json(self, data):
                self.sent_data = data

        info_dict = {
            "title": "Long Lecture 2700s",
            "duration": 2700.0,
            "description": "Video lecture description without any timestamp chapters.",
        }
        opt = VideoFormatOption(
            format_id="137+140",
            resolution_label="1080p",
            height=1080,
            ext="mp4",
            filesize_approx=50000000,
        )

        sid = register_preview_session(
            url="https://youtube.com/watch?v=lec2700",
            video_title="Long Lecture 2700s",
            default_dest_path=r"C:\Downloads\Long Lecture 2700s.mp4",
            info_dict=info_dict,
            options=[opt],
            chapters=[],
        )
        try:
            session = get_preview_session(sid)
            self.assertIsNotNone(session)
            self.assertEqual(len(session.chapters), 5)
            self.assertEqual(session.chapters[0]["title"], "الجزء 1 - تقسيم تلقائي")
            self.assertEqual(session.chapters[1]["title"], "الجزء 2 - تقسيم تلقائي")
            self.assertEqual(session.chapters[2]["title"], "الجزء 3 - تقسيم تلقائي")
            self.assertEqual(session.chapters[3]["title"], "الجزء 4 - تقسيم تلقائي")
            self.assertEqual(session.chapters[4]["title"], "الجزء 5 - تقسيم تلقائي")
            for ch in session.chapters:
                self.assertTrue(ch.get("is_auto"))
                self.assertNotIn("(", ch["title"])
                self.assertNotIn(")", ch["title"])

            # Verify toolbar HTML header indicates smart split
            html = get_clipper_toolbar_html(chapters=session.chapters)
            self.assertIn("📑 الفصول (5 جزء بالتقسيم الذكي - اختر لتحميله)", html)

            # Test _handle_api_update_filename with auto-split chapter
            handler = DummyHandler()
            body = {
                "q_idx": 0,
                "current_dest": session.default_dest_path,
                "chapter_title": session.chapters[0]["title"],
                "clip_start": session.chapters[0]["start_time"],
                "clip_end": session.chapters[0]["end_time"],
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body)
            dest1 = handler.sent_data["dest_path"]
            self.assertIn("[1080p]", dest1)
            self.assertIn("[الجزء 1 - تقسيم تلقائي]", dest1)
            self.assertIn("[Clip]", dest1)
            self.assertNotIn("(", dest1)
            self.assertNotIn(")", dest1)
            self.assertEqual(dest1.count("["), dest1.count("]"))

            # Switch to second auto chapter
            body2 = {
                "q_idx": 0,
                "current_dest": dest1,
                "chapter_title": session.chapters[1]["title"],
                "clip_start": session.chapters[1]["start_time"],
                "clip_end": session.chapters[1]["end_time"],
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body2)
            dest2 = handler.sent_data["dest_path"]
            self.assertNotIn("الجزء 1", dest2)
            self.assertIn("[الجزء 2 - تقسيم تلقائي]", dest2)
            self.assertEqual(dest2.count("["), dest2.count("]"))

            # Test that a chapter title containing parenthesis preserves closing parenthesis
            body_paren = {
                "q_idx": 0,
                "current_dest": dest2,
                "chapter_title": "الجزء 3 (تقسيم تلقائي)",
                "clip_start": session.chapters[2]["start_time"],
                "clip_end": session.chapters[2]["end_time"],
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body_paren)
            dest_paren = handler.sent_data["dest_path"]
            self.assertNotIn("الجزء 2", dest_paren)
            self.assertIn("[الجزء 3 (تقسيم تلقائي)]", dest_paren)
            self.assertNotIn("[الجزء 3 (تقسيم تلقائي]", dest_paren)
            self.assertEqual(dest_paren.count("("), dest_paren.count(")"))
            self.assertEqual(dest_paren.count("["), dest_paren.count("]"))

            # Reset back to full video
            body_reset = {
                "q_idx": 0,
                "current_dest": dest_paren,
                "chapter_title": "",
                "clip_start": 0.0,
                "clip_end": 0.0,
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session, body_reset)
            dest_reset = handler.sent_data["dest_path"]
            self.assertNotIn("الجزء 3", dest_reset)
            self.assertNotIn("[Clip]", dest_reset)
            self.assertTrue(dest_reset.endswith("Long Lecture 2700s [1080p].mp4"))
        finally:
            unregister_preview_session(sid)

        # Verify fallback duration from options[0].duration when info_dict duration is 0
        opt_fb = VideoFormatOption(
            format_id="22",
            resolution_label="720p",
            height=720,
            ext="mp4",
            filesize_approx=25000000,
        )
        setattr(opt_fb, "duration", 2700.0)
        sid_fb = register_preview_session(
            url="https://youtube.com/watch?v=fb2700",
            video_title="Fallback Video",
            default_dest_path=r"C:\Downloads\Fallback Video.mp4",
            info_dict={"title": "Fallback Video", "description": ""},
            options=[opt_fb],
        )
        try:
            session_fb = get_preview_session(sid_fb)
            self.assertIsNotNone(session_fb)
            self.assertEqual(len(session_fb.chapters), 5)
            self.assertEqual(session_fb.chapters[0]["title"], "الجزء 1 - تقسيم تلقائي")
        finally:
            unregister_preview_session(sid_fb)

        # Verify fallback when info_dict is None but options[0].duration is available
        sid_none_info = register_preview_session(
            url="https://youtube.com/watch?v=fb_none",
            video_title="None Info Video",
            default_dest_path=r"C:\Downloads\None Info Video.mp4",
            info_dict=None,
            options=[opt_fb],
            chapters=[],
        )
        try:
            session_none = get_preview_session(sid_none_info)
            self.assertIsNotNone(session_none)
            self.assertEqual(len(session_none.chapters), 5)
            self.assertEqual(session_none.chapters[0]["title"], "الجزء 1 - تقسيم تلقائي")

            # Verify _handle_api_update_filename survives None clip ranges without TypeError
            handler = DummyHandler()
            body_none_clips = {
                "q_idx": 0,
                "current_dest": session_none.default_dest_path,
                "chapter_title": " [الجزء 1 - تقسيم تلقائي] ",
                "clip_start": None,
                "clip_end": None,
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session_none, body_none_clips)
            dest_none = handler.sent_data["dest_path"]
            self.assertIn("[الجزء 1 - تقسيم تلقائي]", dest_none)
            self.assertNotIn("[[", dest_none)
            self.assertEqual(dest_none.count("["), dest_none.count("]"))

            # Verify legacy broken bracket tag [الجزء 1 (تقسيم تلقائي] is cleanly stripped
            legacy_dest = r"C:\Downloads\None Info Video [الجزء 1 (تقسيم تلقائي] [Clip].mp4"
            body_legacy = {
                "q_idx": 0,
                "current_dest": legacy_dest,
                "chapter_title": session_none.chapters[1]["title"],
                "clip_start": 300.0,
                "clip_end": 600.0,
            }
            PreviewBridgeRequestHandler._handle_api_update_filename(handler, session_none, body_legacy)
            dest_cleaned = handler.sent_data["dest_path"]
            self.assertNotIn("الجزء 1", dest_cleaned)
            self.assertIn("[الجزء 2 - تقسيم تلقائي]", dest_cleaned)
            self.assertEqual(dest_cleaned.count("["), dest_cleaned.count("]"))
        finally:
            unregister_preview_session(sid_none_info)

    def test_kanban_active_card_telemetry_and_layout(self):
        """Verifies active stream card layout (speed packed before progress canvas, row3 labels) and live telemetry updates."""
        try:
            import tkinter as tk
        except Exception:
            self.skipTest("Tkinter not available")

        from unittest.mock import MagicMock
        from faqih_downloader.ui.panels.kanban_cards import build_active_card_shell
        from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin
        from faqih_downloader.utils.window_effects import RoundedGlassCard

        try:
            root = tk.Tk()
            root.withdraw()
        except Exception as e:
            self.skipTest(f"Tkinter display not available: {e}")

        try:
            # 1. Test build_active_card_shell layout and widgets
            card_frame = tk.Frame(root)
            card_frame.pack()
            dummy_app = MagicMock()
            widgets = build_active_card_shell(card_frame, dummy_app)

            # Check that lbl_size and lbl_eta are created and present in returned dict
            self.assertIn("lbl_size", widgets)
            self.assertIn("lbl_eta", widgets)
            lbl_size = widgets["lbl_size"]
            lbl_eta = widgets["lbl_eta"]
            lbl_spd = widgets["lbl_speed"]
            cv_prog = widgets["canvas_prog"]
            lbl_pct = widgets["lbl_pct"]

            self.assertIsInstance(lbl_size, tk.Label)
            self.assertIsInstance(lbl_eta, tk.Label)
            self.assertIsInstance(lbl_spd, tk.Label)
            self.assertIsInstance(cv_prog, tk.Canvas)

            # Check packing order inside row2: lbl_spd must be packed with side=RIGHT BEFORE cv_prog
            row2 = lbl_spd.master
            slaves = row2.pack_slaves()
            self.assertIn(lbl_pct, slaves)
            self.assertIn(lbl_spd, slaves)
            self.assertIn(cv_prog, slaves)
            self.assertLess(
                slaves.index(lbl_spd),
                slaves.index(cv_prog),
                "lbl_spd must be packed before cv_prog so canvas expansion does not push speed label off-screen!",
            )
            self.assertEqual(lbl_spd.pack_info().get("side"), "right")
            self.assertEqual(cv_prog.pack_info().get("side"), "left")

            # 2. Test update_kanban_active_stream telemetry updates
            class DummyActiveGUI(KanbanActiveColumnMixin):
                def __init__(self, r):
                    self.root = r
                    self._active_stream_live = False
                    self.active_stream_body = tk.Frame(r)
                    self.active_stream_body.pack()
                    self.lbl_col2_title = tk.Label(r)
                    self.lbl_col2_total_speed = tk.Label(r)
                    self.card_active_1 = RoundedGlassCard(
                        self.active_stream_body,
                        height=148,
                    )
                    self._build_active_card_shell(self.card_active_1.inner)

                def _show_active_card_menu(self, btn):
                    pass

                def _draw_neon_bar(self, cv, ratio):
                    pass

            gui = DummyActiveGUI(root)

            # Test updating with downloaded & total in MB (e.g. 9.0 MB / 69.4 MB)
            d_bytes = int(9.0 * 1024 * 1024)
            t_bytes = int(69.4 * 1024 * 1024)
            gui.update_kanban_active_stream(
                "My_Test_Video.mp4",
                13.0,
                "3.5 MB/s",
                [],
                4,
                downloaded=d_bytes,
                total=t_bytes,
                eta="01:23",
            )
            self.assertTrue(gui._active_stream_live)
            self.assertIn("9.0 MB / 69.4 MB", gui.lbl_a1_size.cget("text"))
            self.assertIn("01:23", gui.lbl_a1_eta.cget("text"))
            self.assertIn("4", gui.lbl_a1_eta.cget("text"))

            # Test processing state: Burning Subtitles...
            gui.update_kanban_active_stream(
                "My_Test_Video.mp4",
                95.0,
                "1.0 MB/s",
                [],
                2,
                downloaded=d_bytes,
                total=t_bytes,
                eta="Burning Subtitles...",
            )
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "🔥 جاري حرق الترجمة...")

            # Test processing state: Merging...
            gui.update_kanban_active_stream(
                "My_Test_Video.mp4",
                99.0,
                "0 B/s",
                [],
                1,
                downloaded=t_bytes,
                total=t_bytes,
                eta="Merging...",
            )
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "⚙️ جاري دمج الصوت والفيديو...")

            # Test processing state: Transcoding...
            gui.update_kanban_active_stream(
                "My_Test_Audio.mp3",
                99.0,
                "0 B/s",
                [],
                1,
                downloaded=t_bytes,
                total=t_bytes,
                eta="Transcoding...",
            )
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "🎵 جاري تحويل الصوت...")

            # Test case-insensitivity and whitespace in processing states
            gui.update_kanban_active_stream("My_Test_Video.mp4", 95.0, "0 B/s", [], 0, downloaded=t_bytes, total=t_bytes, eta="  merging...  ")
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "⚙️ جاري دمج الصوت والفيديو...")
            gui.update_kanban_active_stream("My_Test_Video.mp4", 95.0, "0 B/s", [], 0, downloaded=t_bytes, total=t_bytes, eta="burning subtitles...")
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "🔥 جاري حرق الترجمة...")
            gui.update_kanban_active_stream("My_Test_Audio.mp3", 95.0, "0 B/s", [], 0, downloaded=t_bytes, total=t_bytes, eta="transcoding...")
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "🎵 جاري تحويل الصوت...")

            # Test post-processing state with pct=0.0 and engine stopped does not prematurely reset card
            mock_stopped_eng = MagicMock()
            mock_stopped_eng.is_running = False
            gui.engine = mock_stopped_eng
            gui.update_kanban_active_stream("Stopped_Eng_Merge.mp4", 0.0, "0 B/s", [], 0, eta="Merging...")
            self.assertTrue(gui._active_stream_live, "Active card should not reset while post-processing merging is active!")
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "⚙️ جاري دمج الصوت والفيديو...")

            # Test safe handling when eta is None (must NOT raise TypeError)
            gui.update_kanban_active_stream("None_Eta_Test.mp4", 50.0, "1.5 MB/s", [], 3, eta=None)
            self.assertEqual(gui.lbl_a1_eta.cget("text"), "⚡ 3 مسارات نشطة")

            # Test size formatting: GB / GB
            g_down = int(1.25 * 1024**3)
            g_total = int(2.50 * 1024**3)
            gui.update_kanban_active_stream("Huge_File.iso", 50.0, "10 MB/s", [], 8, downloaded=g_down, total=g_total)
            self.assertIn("1.25 GB / 2.50 GB", gui.lbl_a1_size.cget("text"))

            # Test size formatting: downloaded only when total is 0 (streaming)
            gui.engine = None
            gui.update_kanban_active_stream("Stream.m3u8", 0.0, "500 KB/s", [1], 1, downloaded=int(4.2 * 1024 * 1024), total=0)
            self.assertEqual(gui.lbl_a1_size.cget("text"), "📦 4.2 MB")

            # Test size formatting: connecting state when downloaded and total are 0
            gui.update_kanban_active_stream("Connecting.mp4", 0.0, "10 KB/s", [1], 1, downloaded=0, total=0)
            self.assertEqual(gui.lbl_a1_size.cget("text"), "📦 جاري الاتصال...")

            # Test backward compatibility: call with 5 parameters only (no downloaded, total, eta)
            gui.update_kanban_active_stream("Legacy_Call.mp4", 45.0, "2.0 MB/s", [], 6)
            self.assertTrue(gui._active_stream_live)
            self.assertIn("6 مسارات نشطة", gui.lbl_a1_eta.cget("text"))

            # Test engine fallback when downloaded/total are 0 but engine.total_size is set
            mock_eng = MagicMock()
            mock_eng.total_size = int(50.0 * 1024 * 1024)
            mock_eng.is_running = True
            gui.engine = mock_eng
            gui.update_kanban_active_stream("Engine_Probe.mp4", 20.0, "5.0 MB/s", [], 4)
            # total = 50.0 MB, downloaded = 20% of 50 MB = 10.0 MB
            self.assertIn("10.0 MB / 50.0 MB", gui.lbl_a1_size.cget("text"))

            # 3. Test DownloadCallbacksMixin._engine_progress_cb integration & fallback
            from faqih_downloader.ui.controllers.download_callbacks_mixin import DownloadCallbacksMixin

            class DummyCallbacksHost(DownloadCallbacksMixin):
                def __init__(self):
                    self.root = MagicMock()
                    self.root.winfo_exists.return_value = True
                    self.root.after = lambda delay, fn: fn()
                    self.card_speed = MagicMock()
                    self.card_size = MagicMock()
                    self.card_eta = MagicMock()
                    self.card_threads = MagicMock()
                    self.engine = MagicMock()
                    self.engine.total_size = 80000000
                    self.engine.dest_path = "C:/test/file.mp4"
                    self.engine.get_chunks_snapshot.return_value = []
                    self.received_args = None
                    self.type_error_triggered = False

                def _draw_main_progress(self, pct):
                    pass

                def update_kanban_active_stream(self, fn, pct, sp, snap, ac, **kwargs):
                    if self.type_error_triggered:
                        if kwargs:
                            raise TypeError("Legacy signature does not take kwargs")
                    self.received_args = (fn, pct, sp, snap, ac, kwargs)

            host = DummyCallbacksHost()
            # Call progress callback
            host._engine_progress_cb(20000000, 80000000, 1048576, "00:45", 4)
            self.assertIsNotNone(host.received_args)
            self.assertEqual(host.received_args[0], "C:/test/file.mp4")
            self.assertEqual(host.received_args[5].get("downloaded"), 20000000)
            self.assertEqual(host.received_args[5].get("total"), 80000000)
            self.assertEqual(host.received_args[5].get("eta"), "00:45")

            # Test TypeError fallback when host only accepts 5 arguments
            host.type_error_triggered = True
            host.received_args = None
            host._engine_progress_cb(10000000, 80000000, 1048576, "01:10", 2)
            self.assertIsNotNone(host.received_args)
            self.assertEqual(host.received_args[5], {})
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_pause_closes_live_and_mock_connections(self):
        """Verifies engine.pause() closes all active connections immediately (unblocking workers)."""
        engine = TurboDownloadEngine(
            url="http://example.com/test.mp4",
            destination_path=os.path.join(tempfile.gettempdir(), "test_pause_live.mp4")
        )
        engine.is_running = True

        class FakeLiveHTTPResponse:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True

        live_conn = FakeLiveHTTPResponse()
        mock_conn = MagicMock()
        engine._active_connections.extend([live_conn, mock_conn])

        with patch.object(engine, "save_state"):
            engine.pause()

        self.assertTrue(engine.is_paused)
        self.assertTrue(engine._pause_event.is_set())
        self.assertTrue(live_conn.closed)
        mock_conn.close.assert_called_once()
        self.assertEqual(len(engine._active_connections), 0)

    def test_estimate_clip_total_bytes_accuracy(self):
        """Verifies estimate_clip_total_bytes calculates proportional size for a chapter accurately."""
        si = YouTubeStreamInfo(
            video_id="test_vid",
            title="Sample Video",
            clean_filename="sample.mp4",
            is_progressive=True,
            video_url="https://example.com/v.mp4",
            duration=3000,
            clip_start_sec=0.0,
            clip_end_sec=600.0,
        )
        full_bytes = 50 * 1024 * 1024
        est = estimate_clip_total_bytes(si, full_bytes)
        expected = 10 * 1024 * 1024
        self.assertEqual(est, expected)

        si.clip_end_sec = 3000.0
        self.assertEqual(estimate_clip_total_bytes(si, full_bytes), full_bytes)

        si.clip_start_sec = 0.0
        si.clip_end_sec = 0.0
        self.assertEqual(estimate_clip_total_bytes(si, full_bytes), full_bytes)

    def test_burn_subtitle_does_not_add_ss_when_already_trimmed(self):
        """Verifies burn_subtitle_into_video does not re-add -ss / -to if _already_trimmed is set."""
        with tempfile.TemporaryDirectory() as td:
            dummy_vid = os.path.join(td, "dummy.mp4")
            dummy_ass = os.path.join(td, "dummy.ass")
            with open(dummy_vid, "wb") as f:
                f.write(b"\x00" * 1024)
            with open(dummy_ass, "w", encoding="utf-8") as f:
                f.write("[Script Info]\nTitle: Test\n")

            style_cfg = {
                "clip_start": 10.0,
                "clip_end": 50.0,
                "_already_trimmed": True,
            }

            captured_cmd = []
            def fake_run(cmd, *args, **kwargs):
                captured_cmd.extend(cmd)
                m = MagicMock()
                m.returncode = 0
                m.stderr = ""
                return m

            with patch("faqih_downloader.services.subtitle_processor.subprocess.run", side_effect=fake_run), \
                 patch("os.path.isfile", return_value=True), \
                 patch("os.path.getsize", return_value=2048), \
                 patch("os.replace"):
                burn_subtitle_into_video(dummy_vid, dummy_ass, "ffmpeg", style_config=style_cfg)

            self.assertNotIn("-ss", captured_cmd)
            self.assertNotIn("-to", captured_cmd)

            style_cfg["_already_trimmed"] = False
            captured_cmd.clear()
            with patch("faqih_downloader.services.subtitle_processor.subprocess.run", side_effect=fake_run), \
                 patch("os.path.isfile", return_value=True), \
                 patch("os.path.getsize", return_value=2048), \
                 patch("os.replace"):
                burn_subtitle_into_video(dummy_vid, dummy_ass, "ffmpeg", style_config=style_cfg)

            self.assertIn("-ss", captured_cmd)
            self.assertIn("-to", captured_cmd)

    def test_estimate_clip_total_bytes_dict_and_edge_cases(self):
        """Verifies estimate_clip_total_bytes handles dict structures, boundary conditions, and invalid inputs."""
        dict_si = {
            "clip_start_sec": "100.0",
            "clip_end_sec": "200.0",
            "duration": "1000.0",
        }
        res = estimate_clip_total_bytes(dict_si, 100 * 1024 * 1024)
        self.assertEqual(res, 10 * 1024 * 1024)

        # Non-positive full_total_bytes
        self.assertEqual(estimate_clip_total_bytes(dict_si, 0), 0)
        self.assertEqual(estimate_clip_total_bytes(dict_si, -100), 0)

        # None stream_info falls back to full_total_bytes
        self.assertEqual(estimate_clip_total_bytes(None, 1000), 1000)

    def test_download_clipped_stream_direct_kib_progress_and_chunk_rescaling(self):
        """Verifies download_clipped_stream_direct parses KiB/Lsize stderr correctly and rescales chunks."""
        from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
        from faqih_downloader.services.youtube_models import YouTubeStreamInfo

        si = YouTubeStreamInfo(
            video_id="direct_clip_test",
            title="Clip Test Video",
            clean_filename="test.mp4",
            is_progressive=True,
            video_url="https://example.com/stream.mp4",
            duration=100.0,
            clip_start_sec=10.0,
            clip_end_sec=30.0,
            video_size=100 * 1024 * 1024,
        )

        coord = StreamDownloadCoordinator(si, os.path.join(tempfile.gettempdir(), "test_coord_clip.mp4"))
        coord._is_running = True

        progress_calls = []
        coord.on_progress = lambda dl, tot, spd, eta, ac: progress_calls.append((dl, tot, spd, eta, ac))

        stderr_lines = [
            b"frame=   15 fps=0.0 q=29.0 size=       0KiB time=00:00:00.43 bitrate=   0.9kbits/s\n",
            b"frame=  112 fps=110 q=29.0 size=     500KiB time=00:00:05.00 bitrate= 100.0kbits/s\n",
            b"frame=  300 fps=160 q=-1.0 Lsize=   2000KiB time=00:00:20.00 bitrate= 165.0kbits/s\n",
        ]

        class FakeSubproc:
            def __init__(self):
                self.pid = 99999
                self.returncode = 0
                self._lines = list(stderr_lines)
                class FakeStderr:
                    def __init__(self, lines):
                        self.lines = lines
                    def read1(self, sz):
                        return self.lines.pop(0) if self.lines else b""
                    def read(self, sz):
                        return self.read1(sz)
                self.stderr = FakeStderr(self._lines)
            def poll(self):
                return self.returncode if not self._lines else None
            def wait(self, timeout=None):
                return self.returncode
            def kill(self):
                pass

        fake_proc = FakeSubproc()
        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "target.mp4")
            coord.destination_path = dest
            tmp_clip = f"{dest}.clip.tmp.mp4"
            with open(tmp_clip, "wb") as f:
                f.write(b"\x00" * 2048000)

            with patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("subprocess.Popen", return_value=fake_proc):
                ok = download_clipped_stream_direct(coord)

            self.assertTrue(ok)
            self.assertTrue(getattr(si, "_already_trimmed", False))
            self.assertTrue(os.path.isfile(coord.destination_path))
            self.assertIn("[Clip]", os.path.basename(coord.destination_path))
            self.assertGreater(len(progress_calls), 0)
            last_dl, last_tot, _, _, _ = progress_calls[-1]
            # 2000 KiB was parsed
            self.assertEqual(last_dl, 2000 * 1024)
            # All 8 chunks marked completed
            self.assertEqual(len(coord._clip_chunks), 8)
            for chk in coord._clip_chunks:
                self.assertEqual(chk.status, "completed")
                self.assertEqual(chk.downloaded_bytes, chk.total_bytes)

    def test_stream_coordinator_pause_and_cancel_safeties(self):
        """Verifies pause suspends active subproc and cancel does not fall through to full engine."""
        from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
        from faqih_downloader.services.youtube_models import YouTubeStreamInfo

        si = YouTubeStreamInfo(
            video_id="pause_cancel_test",
            title="Pause Cancel Video",
            clean_filename="pc.mp4",
            is_progressive=True,
            video_url="https://example.com/v.mp4",
            duration=200.0,
            clip_start_sec=10.0,
            clip_end_sec=40.0,
            video_size=50 * 1024 * 1024,
        )

        coord = StreamDownloadCoordinator(si, os.path.join(tempfile.gettempdir(), "test_pc.mp4"))
        coord._is_running = True
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        coord._active_subproc = mock_proc

        with patch("faqih_downloader.services.media_clipper_engine._set_process_suspended") as mock_suspend:
            coord.pause()
            mock_suspend.assert_called_with(mock_proc, True)

            coord.resume()
            mock_suspend.assert_called_with(mock_proc, False)

        # Test cancel in _run_coordinator does NOT fall through to start engines
        with patch("faqih_downloader.core.stream_coordinator.download_clipped_stream_direct", return_value=False), \
             patch("faqih_downloader.core.stream_coordinator.TurboDownloadEngine") as mock_engine_cls:
            coord._cancel_event.set()
            coord._run_coordinator()
            mock_engine_cls.assert_not_called()

    def test_os_suspended_count_guard(self):
        """Verifies that _set_process_suspended guards against multiple consecutive suspensions."""
        import ctypes
        from faqih_downloader.services.media_clipper_engine import _set_process_suspended
        proc = MagicMock()
        proc.pid = 9999

        with patch.object(ctypes.windll.kernel32, "OpenProcess", return_value=123) as mock_open, \
             patch.object(ctypes.windll.ntdll, "NtSuspendProcess") as mock_suspend, \
             patch.object(ctypes.windll.ntdll, "NtResumeProcess") as mock_resume, \
             patch.object(ctypes.windll.kernel32, "CloseHandle"), \
             patch("os.name", "nt"):
            # First suspend: should call NtSuspendProcess and set _os_suspended=True
            _set_process_suspended(proc, True)
            self.assertEqual(mock_suspend.call_count, 1)
            self.assertTrue(getattr(proc, "_os_suspended", False))

            # Second consecutive suspend: should NO-OP and NOT call NtSuspendProcess again
            _set_process_suspended(proc, True)
            self.assertEqual(mock_suspend.call_count, 1)

            # First resume: should call NtResumeProcess and set _os_suspended=False
            _set_process_suspended(proc, False)
            self.assertEqual(mock_resume.call_count, 1)
            self.assertFalse(getattr(proc, "_os_suspended", False))

            # Second consecutive resume: should NO-OP and NOT call NtResumeProcess again
            _set_process_suspended(proc, False)
            self.assertEqual(mock_resume.call_count, 1)

            # Calling resume on a fresh running process must NO-OP
            fresh_proc = MagicMock()
            fresh_proc.pid = 9998
            _set_process_suspended(fresh_proc, False)
            self.assertEqual(mock_resume.call_count, 1)

    def test_ffmpeg_progress_interpolation_and_header_skip(self):
        """Verifies dl_bytes compensation from pct when FFmpeg reports size=0KiB and skips header banner lines."""
        from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
        from faqih_downloader.services.youtube_models import YouTubeStreamInfo

        si = YouTubeStreamInfo(
            video_id="interp_test",
            title="Interp Test",
            clean_filename="interp.mp4",
            is_progressive=True,
            video_url="https://example.com/v.mp4",
            duration=100.0,
            clip_start_sec=0.0,
            clip_end_sec=50.0,
            video_size=10 * 1024 * 1024,
        )
        coord = StreamDownloadCoordinator(si, os.path.join(tempfile.gettempdir(), "interp.mp4"))
        coord._is_running = True
        progress_calls = []
        coord.on_progress = lambda dl, tot, spd, eta, ac: progress_calls.append((dl, tot, spd, eta, ac))

        mock_proc = MagicMock()
        mock_proc.pid = 8888
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0
        mock_proc.stderr.read.side_effect = [
            b"ffmpeg version 6.0-full_build-www.gyan.dev Copyright (c) 2000-2023\n",
            b"frame=  300 fps= 60 q=-0.0 size=       0KiB time=00:00:10.00 bitrate=   0.0kbits/s speed=1.99x\n",
            b""
        ]
        mock_proc.stderr.read1 = mock_proc.stderr.read
        mock_proc.poll.side_effect = [None, None, 0]

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=10 * 1024 * 1024), \
             patch("os.replace"):
            ok = download_clipped_stream_direct(coord)
            self.assertTrue(ok)

        # Header banner line must be skipped, progress must have received interpolated eff_dl > 0
        self.assertGreaterEqual(len(progress_calls), 1)
        first_call = progress_calls[0]
        eff_dl, total_sz, spd, eta, ac = first_call
        self.assertGreater(eff_dl, 0)
        self.assertEqual(total_sz, coord._clip_total_size)
        self.assertAlmostEqual(eff_dl / total_sz, 0.20, places=1)

    def test_sync_clipper_state_propagates_to_all_options_and_kanban_col1(self):
        """Verifies sync_clipper_state_from_body updates all session options and kanban col1 card has estimated size."""
        from faqih_downloader.services.youtube_models import VideoFormatOption
        from faqih_downloader.ui.panels.kanban_staged_prober import stage_media_option_in_col1

        opt1 = VideoFormatOption(format_id="1080p", resolution_label="1080p", height=1080, ext="mp4", filesize_approx=100 * 1024 * 1024)
        opt2 = VideoFormatOption(format_id="720p", resolution_label="720p", height=720, ext="mp4", filesize_approx=50 * 1024 * 1024)
        opt3 = VideoFormatOption(format_id="480p", resolution_label="480p", height=480, ext="mp4", filesize_approx=25 * 1024 * 1024)

        session = MagicMock()
        session.options = [opt1, opt2, opt3]
        session.info_dict = {"duration": 200.0}
        session.subtitle_tracks = []
        session.modal_ref = None

        body = {
            "clip_start": 20.0,
            "clip_end": 70.0,
            "chapter_title": "Test Chapter 1",
            "duration": 200.0,
        }
        sync_clipper_state_from_body(session, body, opt=opt1)

        for opt in (opt1, opt2, opt3):
            self.assertEqual(opt.clip_start_sec, 20.0)
            self.assertEqual(opt.clip_end_sec, 70.0)
            self.assertEqual(opt.selected_chapter_title, "Test Chapter 1")
            self.assertEqual(opt.duration, 200.0)

        gui_mock = MagicMock()
        gui_mock.stage_probed_link_in_col1 = MagicMock()
        stage_media_option_in_col1(
            gui=gui_mock,
            url="https://example.com/video",
            raw_title="Full Video",
            selected_opt=opt1,
            final_dest="/downloads/test.mp4",
            duration=200
        )
        self.assertTrue(gui_mock.stage_probed_link_in_col1.called)
        info_staged = gui_mock.stage_probed_link_in_col1.call_args[0][0]
        self.assertLess(info_staged["file_size"], 100 * 1024 * 1024)
        self.assertAlmostEqual(info_staged["file_size"] / (100 * 1024 * 1024), 0.25, places=2)


if __name__ == "__main__":
    unittest.main()

