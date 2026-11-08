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
)
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


if __name__ == "__main__":
    unittest.main()
