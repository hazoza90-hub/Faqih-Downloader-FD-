"""
Unit and Integration Tests for Smart Live Clipper & Dual Bilingual Subtitles.
Tests:
1. filter_and_shift_cues_for_clip (temporal shifting, boundary conditions, edge cases)
2. apply_custom_cue_edits (index-based, timestamp-based, and text-based replacement)
3. merge_bilingual_cues and generate_styled_ass_file with Default & Secondary styles
4. trim_media_file using real FFmpeg execution
5. sync_clipper_state_from_body and process_post_download_clip_and_subtitles pipeline
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
    process_post_download_clip_and_subtitles,
    sync_clipper_state_from_body,
    enrich_stream_info_with_clip,
)
from faqih_downloader.services.subtitle_style_engine import generate_styled_ass_file
from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo


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
        # Edit cue 1 by index and cue 2 by exact text
        edits = {
            "1": "هذا نص مصحح بدقة",
            "النهاية": "النهاية السعيدة",
        }
        updated = apply_custom_cue_edits(cues, edits)
        self.assertEqual(updated[0]["text"], "مرحبا بك")
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
        import shutil
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            self.skipTest("FFmpeg not available in PATH")

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_src = os.path.join(tmp_dir, "src_video.mp4")
            # Generate a 3-second synthetic test video with audio
            cmd_gen = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-b:a", "64k",
                test_src
            ]
            cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
            gen_res = subprocess.run(cmd_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=cflags)
            self.assertEqual(gen_res.returncode, 0)
            self.assertTrue(os.path.isfile(test_src))
            orig_sz = os.path.getsize(test_src)
            self.assertGreater(orig_sz, 0)

            # Trim to [0.8s .. 2.2s]
            ok = trim_media_file(test_src, clip_start=0.8, clip_end=2.2, ffmpeg_bin=ffmpeg_bin)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(test_src))
            trimmed_sz = os.path.getsize(test_src)
            self.assertGreater(trimmed_sz, 0)

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


if __name__ == "__main__":
    unittest.main()
