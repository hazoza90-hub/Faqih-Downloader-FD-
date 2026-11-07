import os, unittest, tempfile
from faqih_downloader.services.subtitle_style_engine import (
    format_ass_timestamp,
    parse_srt_timestamp_to_seconds,
    _extract_cue_item,
    _split_single_cue,
    normalize_and_dedupe_cues,
    sanitize_arabic_subtitle_text,
    hex_to_ass_color,
    generate_styled_ass_file,
)
from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo


class TestSubtitleStyleEngineComprehensive(unittest.TestCase):
    def test_format_ass_timestamp(self):
        self.assertEqual(format_ass_timestamp(0.0), "0:00:00.00")
        self.assertEqual(format_ass_timestamp(1.234), "0:00:01.23")
        self.assertEqual(format_ass_timestamp(65.45), "0:01:05.45")
        self.assertEqual(format_ass_timestamp(3665.12), "1:01:05.12")
        self.assertEqual(format_ass_timestamp(59.999), "0:01:00.00")

    def test_parse_srt_timestamp_to_seconds(self):
        self.assertAlmostEqual(parse_srt_timestamp_to_seconds("00:01:05,500"), 65.5)
        self.assertAlmostEqual(parse_srt_timestamp_to_seconds("01:05.500"), 65.5)
        self.assertAlmostEqual(parse_srt_timestamp_to_seconds("123.45"), 123.45)
        self.assertAlmostEqual(parse_srt_timestamp_to_seconds(""), 0.0)

    def test_extract_cue_item(self):
        # Tuple
        self.assertEqual(_extract_cue_item((1.0, 2.5, "test")), (1.0, 2.5, "test"))
        # Dict with start/end
        self.assertEqual(_extract_cue_item({"start": 2.0, "end": 4.0, "text": "hello"}), (2.0, 4.0, "hello"))
        # Dict with tStartMs/dDurationMs (YouTube json3 format)
        self.assertEqual(_extract_cue_item({"tStartMs": 1500, "dDurationMs": 2000, "utf8": "yt"}), (1.5, 3.5, "yt"))

    def test_normalize_and_dedupe_cues_rollup(self):
        cues = [
            (1.0, 3.0, "Line 1\nLine 2"),
            (2.5, 4.5, "Line 2\nLine 3"),
        ]
        res = normalize_and_dedupe_cues(cues)
        # Res should deduplicate "Line 2" from beginning of cue 2
        # And ensure cue 0 ends before cue 1 starts (min(3.0, 2.5 - 0.02) = 2.48)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0][0], 1.0)
        self.assertEqual(res[0][1], 2.48)
        self.assertEqual(res[0][2], "Line 1\nLine 2")
        self.assertEqual(res[1][0], 2.5)
        self.assertEqual(res[1][2], "Line 3")

    def test_normalize_and_dedupe_cues_overlap_elimination(self):
        cues = [
            (1.0, 4.0, "First cue"),
            (2.0, 5.0, "Second cue"),
        ]
        res = normalize_and_dedupe_cues(cues)
        self.assertEqual(len(res), 2)
        self.assertLessEqual(res[0][1], res[1][0] - 0.02)
        self.assertEqual(res[0][1], 1.98)

    def test_normalize_and_dedupe_cues_max_lines_and_words(self):
        long_text = "This is a very long sentence that has way more than fourteen words to trigger the recursive splitting logic cleanly."
        cues = [(0.0, 10.0, long_text)]
        res = normalize_and_dedupe_cues(cues, max_words=14)
        self.assertGreaterEqual(len(res), 2)
        for s, e, text in res:
            self.assertLessEqual(len(text.splitlines()), 2)
            self.assertLessEqual(len(text.split()), 14)

    def test_sanitize_arabic_subtitle_text(self):
        # Ligature text and NFC normalization
        sample = "علشان اللي ما لوش خير في عضلاته والأولى والأخيرة في ثلاث أيام والعلاقة."
        clean = sanitize_arabic_subtitle_text(sample, for_ass=True)
        # Terminal period should be moved to front (left) for ASS dialogue
        self.assertTrue(clean.startswith("."))
        self.assertFalse(clean.endswith("."))

        # English sentence ending with period should keep period at end
        eng = "Watch YouTube."
        clean_eng = sanitize_arabic_subtitle_text(eng, for_ass=True)
        self.assertEqual(clean_eng, "Watch YouTube.")

        # Arabic sentence ending with English word + period
        mixed = "شاهد فيديو YouTube."
        clean_mixed = sanitize_arabic_subtitle_text(mixed, for_ass=True)
        self.assertEqual(clean_mixed, "شاهد فيديو YouTube.")

        # Arabic sentence ending with parenthesis then exclamation mark
        paren = "مرحبا (بالجميع)!"
        clean_paren = sanitize_arabic_subtitle_text(paren, for_ass=True)
        self.assertTrue(clean_paren.startswith("!"))

    def test_generate_styled_ass_file_presets(self):
        with tempfile.TemporaryDirectory() as td:
            for p in ["youtube", "tiktok", "golden", "custom"]:
                out_path = os.path.join(td, f"{p}.ass")
                cues = [(0.0, 2.0, "مرحبا بكم {تجربة}")]
                ok = generate_styled_ass_file(cues, out_path, preset=p, width=1920, height=1080)
                self.assertTrue(ok)
                self.assertTrue(os.path.isfile(out_path))
                with open(out_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertIn("PlayResX: 1920", content)
                    self.assertIn("PlayResY: 1080", content)
                    self.assertIn("Style: Default", content)
                    self.assertIn("Dialogue: 0,0:00:00.00,0:00:02.00,Default", content)
                    # Curly braces should be escaped to fullwidth to avoid override tag swallowing
                    self.assertIn("｛تجربة｝", content)

    def test_youtube_models_style_inheritance(self):
        opt = VideoFormatOption(
            format_id="137+140", resolution_label="1080p", height=1080, ext="mp4", filesize_approx=1000,
            subtitle_preset="tiktok", subtitle_font_scale=1.2, subtitle_text_color="#00FFFF",
            subtitle_bg_mode="outline", subtitle_pos_x=45.0, subtitle_pos_y=80.0
        )
        self.assertEqual(opt.subtitle_preset, "tiktok")
        self.assertEqual(opt.subtitle_font_scale, 1.2)
        self.assertEqual(opt.subtitle_text_color, "#00FFFF")

        sub_track = {
            "sub_id": "ar", "language": "ar",
            "style_config": {
                "preset": "golden", "font_scale": 1.4, "text_color": "#FFD700",
                "bg_mode": "box", "pos_x": 50.0, "pos_y": 70.0
            }
        }
        stream_info = YouTubeStreamInfo(
            video_id="xyz123", title="Test", clean_filename="test.mp4", is_progressive=True,
            video_url="https://test.com", subtitle_track=sub_track
        )
        # Should automatically inherit style_config from subtitle_track
        self.assertEqual(stream_info.subtitle_preset, "golden")
        self.assertEqual(stream_info.subtitle_font_scale, 1.4)
        self.assertEqual(stream_info.subtitle_text_color, "#FFD700")
        self.assertEqual(stream_info.subtitle_pos_y, 70.0)


if __name__ == "__main__":
    unittest.main()
