"""
Regression and feature tests for Independent Multi-Language External .SRT Subtitles.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from faqih_downloader.locales.i18n import LocalizationManager, tr
from faqih_downloader.services.media_clipper_engine import (
    enrich_stream_info_with_clip,
    process_post_download_clip_and_subtitles,
)
from faqih_downloader.services.subtitle_processor import (
    handle_subtitles_post_download,
    start_subtitle_prefetch,
)
from faqih_downloader.services.youtube_models import VideoFormatOption, YouTubeStreamInfo


SAMPLE_SRT = (
    "1\n00:00:02,000 --> 00:00:04,000\nBefore clip\n\n"
    "2\n00:00:12,000 --> 00:00:15,000\nInside clip {lang}\n\n"
    "3\n00:00:25,000 --> 00:00:28,000\nAfter clip\n"
)


def _read_utf8(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _fake_download_srt(sub_track, video_filepath):
    lang = str(sub_track.get("language") or sub_track.get("sub_id") or "sub").strip()
    stem = os.path.splitext(video_filepath)[0]
    out_p = f"{stem}.{lang}.srt"
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(SAMPLE_SRT.format(lang=lang))
    return out_p


class TestExternalSubtitlesBackend(unittest.TestCase):
    def _make_tracks(self):
        ar = {"sub_id": "ar", "language": "ar", "label": "Arabic - العربية", "url": "https://ex.com/ar.vtt", "is_auto": False}
        en = {"sub_id": "en", "language": "en", "label": "English", "url": "https://ex.com/en.vtt", "is_auto": False}
        return ar, en

    def test_prefetch_and_multi_external_without_internal_sub_touches_no_ffmpeg(self):
        ar, en = self._make_tracks()
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "Lesson.mp4")
            with open(vid, "wb") as f:
                f.write(b"raw_mp4_bytes")

            si = YouTubeStreamInfo(
                video_id="v1", title="Lesson", clean_filename="Lesson.mp4",
                is_progressive=True, video_url="http://v", video_headers={},
                video_ext="mp4", video_resolution="720p", video_size=100,
                audio_url=None, audio_headers={}, audio_ext="", audio_size=0,
                duration=60.0, subtitle_track=None, subtitle_embed_mode="soft_embed",
                external_subtitle_tracks=[ar, en],
            )
            dl_calls = []

            def _tracked_dl(trk, vpath):
                dl_calls.append(trk.get("language"))
                return _fake_download_srt(trk, vpath)

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", side_effect=_tracked_dl), \
                 patch("faqih_downloader.services.subtitle_processor.embed_subtitle_into_mp4") as mock_embed, \
                 patch("faqih_downloader.services.subtitle_processor.burn_subtitle_into_video") as mock_burn:
                t = start_subtitle_prefetch(si, vid)
                self.assertIsNotNone(t)
                t.join(timeout=5.0)
                self.assertEqual(sorted(dl_calls), ["ar", "en"])
                self.assertEqual(sorted(getattr(si, "_prefetched_external_srts", {}).keys()), ["ar", "en"])

                out = handle_subtitles_post_download(si, vid)
                self.assertEqual(out, vid)
                # Must reuse prefetched files without re-downloading or running FFmpeg
                self.assertEqual(len(dl_calls), 2)
                mock_embed.assert_not_called()
                mock_burn.assert_not_called()
                self.assertTrue(os.path.isfile(os.path.join(tmp, "Lesson.ar.srt")))
                self.assertTrue(os.path.isfile(os.path.join(tmp, "Lesson.en.srt")))

    def test_clip_shift_and_sidecar_rename_without_internal_sub(self):
        ar, en = self._make_tracks()
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "Talk.mp4")
            with open(vid, "wb") as f:
                f.write(b"raw_mp4_bytes")

            opt = VideoFormatOption(
                format_id="22", resolution_label="720p", height=720, ext="mp4",
                filesize_approx=1000, fps=30, vcodec="avc1", acodec="mp4a", note="",
                clip_start_sec=10.0, clip_end_sec=20.0, selected_chapter_title="Intro",
                external_subtitle_tracks=[ar, en],
            )
            si = YouTubeStreamInfo(
                video_id="v2", title="Talk", clean_filename="Talk.mp4",
                is_progressive=True, video_url="http://v", video_headers={},
                video_ext="mp4", video_resolution="720p", video_size=100,
                audio_url=None, audio_headers={}, audio_ext="", audio_size=0,
                duration=60.0, subtitle_track=None,
            )
            enrich_stream_info_with_clip(si, opt)
            self.assertEqual(len(si.external_subtitle_tracks), 2)

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", side_effect=_fake_download_srt), \
                 patch("faqih_downloader.services.media_env_helpers.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.media_clipper_engine.probe_media_duration", return_value=60.0), \
                 patch("faqih_downloader.services.media_clipper_engine.trim_media_file", return_value=True):
                final_vid = process_post_download_clip_and_subtitles(si, vid)

            self.assertEqual(os.path.basename(final_vid), "Talk [Intro] [Clip].mp4")
            ar_srt = os.path.join(tmp, "Talk [Intro] [Clip].ar.srt")
            en_srt = os.path.join(tmp, "Talk [Intro] [Clip].en.srt")
            self.assertTrue(os.path.isfile(ar_srt))
            self.assertTrue(os.path.isfile(en_srt))
            ar_txt = _read_utf8(ar_srt)
            en_txt = _read_utf8(en_srt)
            self.assertIn("00:00:02,000 --> 00:00:05,000", ar_txt)
            self.assertIn("Inside clip ar", ar_txt)
            self.assertNotIn("Before clip", ar_txt)
            self.assertIn("00:00:02,000 --> 00:00:05,000", en_txt)

    def test_soft_embed_and_hard_burn_protect_requested_external_srts_and_prevent_double_shift(self):
        ar, en = self._make_tracks()
        # 1) soft_embed with internal ar + external [en] ONLY -> ar deleted, en kept
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "EmbedOnlyEn.mp4")
            with open(vid, "wb") as f:
                f.write(b"v")
            si = YouTubeStreamInfo(
                video_id="v3", title="T", clean_filename="EmbedOnlyEn.mp4",
                is_progressive=True, video_url="u", video_headers={}, video_ext="mp4",
                video_resolution="720p", video_size=10, audio_url=None, audio_headers={},
                audio_ext="", audio_size=0, duration=30.0,
                subtitle_track=ar, subtitle_embed_mode="soft_embed",
                external_subtitle_tracks=[en],
            )
            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", side_effect=_fake_download_srt), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.subtitle_processor.embed_subtitle_into_mp4", return_value=True):
                handle_subtitles_post_download(si, vid)
            self.assertFalse(os.path.exists(os.path.join(tmp, "EmbedOnlyEn.ar.srt")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "EmbedOnlyEn.en.srt")))

        # 2) soft_embed with internal ar + external [ar, en] -> BOTH kept!
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "EmbedBoth.mp4")
            with open(vid, "wb") as f:
                f.write(b"v")
            si = YouTubeStreamInfo(
                video_id="v4", title="T", clean_filename="EmbedBoth.mp4",
                is_progressive=True, video_url="u", video_headers={}, video_ext="mp4",
                video_resolution="720p", video_size=10, audio_url=None, audio_headers={},
                audio_ext="", audio_size=0, duration=30.0,
                subtitle_track=ar, subtitle_embed_mode="soft_embed",
                external_subtitle_tracks=[ar, en],
            )
            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", side_effect=_fake_download_srt), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.subtitle_processor.embed_subtitle_into_mp4", return_value=True):
                handle_subtitles_post_download(si, vid)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "EmbedBoth.ar.srt")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "EmbedBoth.en.srt")))

        # 3) hard_burn with internal ar + external [ar, en] + clip [10, 20]:
        #    burn receives unshifted ar.srt (00:00:12), cleanup preserves ar.srt & en.srt,
        #    and post-burn shifts ar.srt ONCE to 00:00:02!
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "BurnClip.mp4")
            with open(vid, "wb") as f:
                f.write(b"v")
            si = YouTubeStreamInfo(
                video_id="v5", title="T", clean_filename="BurnClip.mp4",
                is_progressive=True, video_url="u", video_headers={}, video_ext="mp4",
                video_resolution="720p", video_size=10, audio_url=None, audio_headers={},
                audio_ext="", audio_size=0, duration=30.0,
                subtitle_track=ar, subtitle_embed_mode="hard_burn",
                external_subtitle_tracks=[ar, en], clip_start_sec=10.0, clip_end_sec=20.0,
            )
            seen_pre_burn_srt = []

            def _mock_burn(vp, sp, ff, **kw):
                seen_pre_burn_srt.append(_read_utf8(sp))
                return True

            with patch("faqih_downloader.services.subtitle_processor.download_subtitle_as_srt", side_effect=_fake_download_srt), \
                 patch("faqih_downloader.services.subtitle_processor.find_ffmpeg_bin", return_value="ffmpeg"), \
                 patch("faqih_downloader.services.subtitle_processor.burn_subtitle_into_video", side_effect=_mock_burn):
                handle_subtitles_post_download(si, vid)

            self.assertEqual(len(seen_pre_burn_srt), 1)
            self.assertIn("00:00:12,000 --> 00:00:15,000", seen_pre_burn_srt[0])
            ar_final = os.path.join(tmp, "BurnClip.ar.srt")
            en_final = os.path.join(tmp, "BurnClip.en.srt")
            self.assertTrue(os.path.isfile(ar_final))
            self.assertTrue(os.path.isfile(en_final))
            self.assertIn("00:00:02,000 --> 00:00:05,000", _read_utf8(ar_final))
            self.assertIn("00:00:02,000 --> 00:00:05,000", _read_utf8(en_final))


class TestExternalSubtitlesUI(unittest.TestCase):
    def test_modal_tracks_ui_and_main_bar_sync_and_locale_and_staged_badge(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tk display not available")
            return

        loc = LocalizationManager.get_instance()
        orig_lang = loc.get_language()
        try:
            from faqih_downloader.ui.modals.quality_tracks_ui import (
                build_audio_subtitle_row,
                open_ext_srt_popup_menu,
            )
            from faqih_downloader.ui.panels.media_options_bar import MediaOptionsBarMixin
            from faqih_downloader.ui.panels.kanban_staged_helpers import build_staged_link_card

            subs = [
                {"sub_id": "none", "language": "none", "label": "None / بدون ترجمة", "url": ""},
                {"sub_id": "ar", "language": "ar", "label": "Arabic - العربية", "url": "http://ar"},
                {"sub_id": "en", "language": "en", "label": "English", "url": "http://en"},
            ]
            auds = [{"track_id": "original", "language": "en", "label": "Original", "is_original": True}]
            theme = {"c_panel": "#1e293b", "c_border": "#475569", "c_text_bright": "#f8fafc", "c_input_bg": "#0f172a", "c_accent": "#38bdf8"}

            # 1) Modal tracks row UI (isolated from persistent preferred_subtitle_lang)
            with patch("faqih_downloader.ui.modals.quality_tracks_ui.get_setting", side_effect=lambda k, d=None: "none" if k == "preferred_subtitle_lang" else d), \
                 patch("faqih_downloader.ui.panels.media_options_bar.get_setting", side_effect=lambda k, d=None: "none" if k == "preferred_subtitle_lang" else d):
                _, cb_sub = build_audio_subtitle_row(root, theme, auds, subs)
                self.assertEqual(cb_sub._mode_codes, ["soft_embed", "hard_burn"])
                self.assertEqual(len(cb_sub._mode_radios), 2)
                self.assertEqual(str(cb_sub._mode_combobox.cget("state")), "disabled")
                cb_sub.current(1)
                cb_sub._update_mode_state()
                self.assertEqual(str(cb_sub._mode_combobox.cget("state")), "readonly")
                cb_sub.current(0)
                cb_sub._update_mode_state()
                self.assertEqual(str(cb_sub._mode_combobox.cget("state")), "disabled")

                menu = open_ext_srt_popup_menu(cb_sub._ext_srt_button, subs, [], lambda picked: cb_sub.set_external_subtitle_tracks(picked), theme=theme)
                self.assertIn("ar", menu._vars)
                self.assertIn("en", menu._vars)
                menu._vars["ar"].set(True)
                menu._vars["en"].set(True)
                picked = [s for s in menu._tracks if menu._vars[s["language"]].get()]
                cb_sub.set_external_subtitle_tracks(picked)
                self.assertEqual(cb_sub._ext_srt_button.cget("text"), "AR, EN (2)")

                # 2) MediaOptionsBarMixin + locale switch + Column 1 card badge
                class _MiniBar(MediaOptionsBarMixin):
                    c_panel = "#1e293b"
                    c_panel_light = "#334155"
                    c_input_bg = "#0f172a"
                    c_text_bright = "#f8fafc"
                    c_accent = "#38bdf8"
                    c_accent_dark = "#0284c7"

                    def __init__(self, r):
                        self.root = r
                        self._staged_links = []
                        self.entry_dest = tk.Entry(r)
                        self.entry_dest.insert(0, "video.mp4")
                        self._build_media_options_bar(r)

                    def _theme_dict(self):
                        return theme

                loc.set_language("ar")
                bar = _MiniBar(root)
                opt = VideoFormatOption(
                    format_id="22", resolution_label="720p", height=720, ext="mp4",
                    filesize_approx=4 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""
                )
                url = "https://youtube.com/watch?v=exttest"
                bar._pending_media_context = {"url": url, "options": [opt], "audio_tracks": auds, "subtitle_tracks": subs}
                bar.populate_main_media_bar({"title": "Demo", "duration": 60}, [opt], auds, subs, selected_option=opt)
                self.assertEqual(bar._main_sub_mode_codes, ["soft_embed", "hard_burn"])
                self.assertEqual(str(bar.cb_main_sub_mode.cget("state")), "disabled")
                self.assertEqual(bar.btn_main_ext_srt.cget("text"), tr("btn_ext_srt_none", "بدون (0)"))

                bar.cb_main_sub.current(1)
                bar._on_main_sub_changed()
                self.assertEqual(str(bar.cb_main_sub_mode.cget("state")), "readonly")

                bar.set_main_external_subtitles([subs[1], subs[2]], sync_state=True)
                self.assertEqual(bar.btn_main_ext_srt.cget("text"), "AR, EN (2)")
                self.assertEqual(len(opt.external_subtitle_tracks), 2)

                loc.set_language("en")
                bar.refresh_media_options_locale()
                self.assertIn("Ext SRT", bar.lbl_main_ext_srt.cget("text"))
                self.assertEqual(len(bar.cb_main_sub_mode.cget("values")), 2)
                bar.set_main_external_subtitles([], sync_state=True)
                self.assertEqual(bar.btn_main_ext_srt.cget("text"), tr("btn_ext_srt_none", "None (0)"))

                bar.set_main_external_subtitles([subs[1], subs[2]], sync_state=True)
                card = build_staged_link_card(root, {"url": url, "title": "Demo", "selected_opt": opt, "media_context": bar._pending_media_context}, theme)
                labels = []

                def _collect(w):
                    if isinstance(w, tk.Label):
                        labels.append(w.cget("text"))
                    for ch in w.winfo_children():
                        _collect(ch)

                _collect(card)
                self.assertTrue(any("❏ SRT: AR, EN" in txt for txt in labels), f"Badge not found in labels: {labels}")
        finally:
            loc.set_language(orig_lang)
            try:
                root.destroy()
            except Exception:
                pass


class TestPreviewExtSrtAndSubtitleDedup(unittest.TestCase):
    def test_preview_html_contains_ext_srt_dropdown_and_disables_mode_when_no_sub(self):
        from faqih_downloader.ui.modals.preview_html_builder import generate_preview_html
        from faqih_downloader.services.youtube_models import VideoFormatOption

        opt = VideoFormatOption(
            format_id="22", resolution_label="720p", height=720, ext="mp4",
            filesize_approx=5 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""
        )
        subs = [
            {"sub_id": "none", "language": "none", "label": "No Subtitles", "url": ""},
            {"sub_id": "ar", "language": "ar", "label": "Arabic", "url": "https://example.com/ar.vtt", "ext": "vtt"},
            {"sub_id": "en-auto", "language": "en", "label": "English (Auto-Translated)", "url": "https://example.com/en.vtt", "ext": "vtt"},
        ]
        html_empty = generate_preview_html(
            url="https://youtube.com/watch?v=demo1234567",
            video_title="Preview Ext SRT Test",
            options=[opt],
            subtitle_tracks=subs,
            selected_sub_track=subs[0],
        )
        self.assertIn('id="extSrtBtn"', html_empty)
        self.assertIn('id="extSrtDropdown"', html_empty)
        self.assertIn("بدون (0)", html_empty)
        self.assertIn("مسح الكل / Clear All", html_empty)
        self.assertIn('<select id="modeSelect" onchange="onModeChange()" disabled>', html_empty)
        self.assertIn("getSelectedExtSubIndices()", html_empty)
        self.assertIn("getSelectedExtSubLangs()", html_empty)

        opt.external_subtitle_tracks = [subs[1], subs[2]]
        html_selected = generate_preview_html(
            url="https://youtube.com/watch?v=demo1234567",
            video_title="Preview Ext SRT Test",
            options=[opt],
            subtitle_tracks=subs,
            selected_sub_track=subs[1],
        )
        self.assertIn("AR, EN (2)", html_selected)
        self.assertIn('<select id="modeSelect" onchange="onModeChange()">', html_selected)

    def test_sync_preview_external_subtitles_bridge_roundtrip(self):
        from faqih_downloader.services.preview_stream_bridge import PreviewSession
        from faqih_downloader.services.media_clipper_engine import sync_clipper_state_from_body
        from faqih_downloader.services.youtube_models import VideoFormatOption

        opt = VideoFormatOption(
            format_id="22", resolution_label="720p", height=720, ext="mp4",
            filesize_approx=5 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""
        )
        subs = [
            {"sub_id": "none", "language": "none", "label": "No Subtitles", "url": ""},
            {"sub_id": "ar-auto", "language": "ar", "label": "العربية (ترجمة تلقائية)", "url": "https://example.com/ar.vtt"},
            {"sub_id": "en-auto", "language": "en", "label": "English (Auto-Translated)", "url": "https://example.com/en.vtt"},
            {"sub_id": "fr", "language": "fr", "label": "French", "url": "https://example.com/fr.vtt"},
        ]
        sess = PreviewSession(
            sid="sid1", url="https://youtube.com/watch?v=1", video_title="Test",
            options=[opt], subtitle_tracks=subs,
        )
        sync_clipper_state_from_body(sess, {"ext_sub_indices": [1, 3], "ext_sub_langs": ["ar-auto", "fr"]}, opt)
        self.assertEqual([t["sub_id"] for t in sess.external_subtitle_tracks], ["ar-auto", "fr"])
        self.assertEqual([t["sub_id"] for t in opt.external_subtitle_tracks], ["ar-auto", "fr"])

        # Language-only payload fallback
        sync_clipper_state_from_body(sess, {"ext_sub_langs": ["en"]}, opt)
        self.assertEqual([t["sub_id"] for t in sess.external_subtitle_tracks], ["en-auto"])

        # Explicit clear
        sync_clipper_state_from_body(sess, {"ext_sub_indices": [], "ext_sub_langs": []}, opt)
        self.assertEqual(sess.external_subtitle_tracks, [])
        self.assertEqual(opt.external_subtitle_tracks, [])

    def test_extract_subtitle_tracks_deduplicates_orig_variants(self):
        from faqih_downloader.services.youtube_tracks import extract_subtitle_tracks

        info = {
            "subtitles": {},
            "automatic_captions": {
                "ar-orig": [{"url": "https://example.com/ar-orig.vtt", "ext": "vtt"}],
                "ar": [{"url": "https://example.com/ar.vtt", "ext": "vtt"}],
                "en-orig": [{"url": "https://example.com/en-orig.vtt", "ext": "vtt"}],
                "en": [{"url": "https://example.com/en.vtt", "ext": "vtt"}],
                "es": [{"url": "https://example.com/es.vtt", "ext": "vtt"}],
            },
        }
        tracks = extract_subtitle_tracks(info)
        ar_tracks = [t for t in tracks if t.get("language", "").startswith("ar") and t.get("is_auto")]
        en_tracks = [t for t in tracks if t.get("language", "").startswith("en") and t.get("is_auto")]
        self.assertEqual(len(ar_tracks), 1)
        self.assertEqual(ar_tracks[0]["language"], "ar")
        self.assertEqual(len(en_tracks), 1)
        self.assertEqual(en_tracks[0]["language"], "en")

    def test_external_subtitle_service_annotations_valid(self):
        import typing
        from faqih_downloader.services import external_subtitle_service as ess
        hints = typing.get_type_hints(ess.process_external_subtitle_tracks)
        self.assertIn("defer_prepare_langs", hints)
        hints_sync = typing.get_type_hints(ess.sync_preview_external_subtitles)
        self.assertIn("target_opts", hints_sync)

    def test_staged_card_height_and_start_button_visible_with_6_ext_srts(self):
        import tkinter as tk
        from faqih_downloader.ui.panels.kanban_staged_helpers import build_staged_link_card

        root = tk.Tk()
        root.withdraw()
        try:
            container = tk.Frame(root, width=320, height=500, bg="#0b0e14")
            container.pack(fill=tk.BOTH, expand=True)
            ext_tracks = [
                {"sub_id": c, "language": c, "label": c.upper(), "url": f"https://example.com/{c}.vtt"}
                for c in ("ar", "en", "de", "es", "fr", "hi")
            ]
            info = {
                "url": "https://youtu.be/cR4T9MDrlqE",
                "file_name": "Sample Long Arabic And English Video Title For Card Wrapping",
                "file_size": 120 * 1024 * 1024,
                "badge": "1080p • 🎬 MP4",
                "category": "Video",
                "icon": "🎬",
                "duration": 620,
                "platform": "YouTube",
                "external_subtitle_tracks": ext_tracks,
                "selected_opt": VideoFormatOption(
                    format_id="137+140", resolution_label="1080p", height=1080, ext="mp4",
                    filesize_approx=120 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note="",
                    external_subtitle_tracks=ext_tracks,
                ),
            }
            card = build_staged_link_card(
                container, info,
                callbacks={"start": lambda i: None, "info": lambda i: None, "remove": lambda i: None, "quality": lambda i: None}
            )
            root.update_idletasks()
            card_h = int(float(card.cget("height")))
            self.assertGreaterEqual(card_h, 228)
            self.assertGreaterEqual(card_h, card.inner.winfo_reqheight() + 20)

            buttons = []
            def _walk(w):
                if isinstance(w, tk.Button):
                    buttons.append(w)
                for ch in w.winfo_children():
                    _walk(ch)
            _walk(card.inner)
            btn_texts = [str(b.cget("text")) for b in buttons]
            self.assertTrue(any("▶" in t for t in btn_texts), f"Start button missing in {btn_texts}")
            self.assertTrue(any("⚙" in t for t in btn_texts), f"Quality button missing in {btn_texts}")
            for b in buttons:
                self.assertGreater(b.winfo_reqheight(), 0)
        finally:
            root.destroy()

    def test_ext_subs_and_video_folder_preserved_across_bar_card_modal_and_tree_switch(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        from faqih_downloader.ui.panels.media_options_bar import MediaOptionsBarMixin
        from faqih_downloader.ui.panels.media_options_actions import MediaOptionsActionsMixin
        from faqih_downloader.ui.panels.kanban_staged_prober import stage_media_option_in_col1

        class _HarnessApp(MediaOptionsBarMixin, MediaOptionsActionsMixin):
            def __init__(self, tk_root, dl_dir):
                self.root = tk_root
                self._dl_dir = dl_dir
                self.auto_categorize_folders = True
                self.history_manager = None
                self._staged_links = []
                self._pending_media_context = None
                self.entry_url = tk.Entry(tk_root)
                self.entry_dest = tk.Entry(tk_root)
                self.entry_url.insert(0, "https://youtu.be/cR4T9MDrlqE")
                self.entry_dest.insert(0, os.path.join(dl_dir, "Video"))
                self._current_theme = "dark"
                self.current_lang = "ar"
                self.is_downloading = False
                self._launch_stream_coordinator = MagicMock()
                for k, v in self._theme_dict().items():
                    setattr(self, k, v)
                bar_host = tk.Frame(tk_root)
                self._build_media_options_bar(bar_host)

            def _get_base_downloads_dir(self):
                return self._dl_dir

            def _theme_dict(self):
                return {
                    "c_bg": "#0b0e14", "c_panel": "#151a24", "c_panel_light": "#1e293b",
                    "c_accent": "#38bdf8", "c_accent_dark": "#0284c7", "c_text": "#94a3b8",
                    "c_text_bright": "#f8fafc", "c_text_muted": "#64748b", "c_border": "#283548",
                    "c_input_bg": "#0f172a", "c_success": "#10b981", "c_card": "#151a24",
                    "c_danger": "#ef4444", "c_warning": "#f59e0b",
                }

            def _refresh_staged_links_ui(self):
                pass

            def _sync_staged_links_ui(self):
                pass

            def stage_probed_link_in_col1(self, info_dict):
                self._staged_links.append(info_dict)

            def set_status_text(self, *_args, **_kwargs):
                pass

        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dl_dir = os.path.join(tmp, "Downloads")
                os.makedirs(os.path.join(dl_dir, "Video"), exist_ok=True)
                app = _HarnessApp(root, dl_dir)
                opts = [
                    VideoFormatOption(format_id="137+140", resolution_label="1080p", height=1080, ext="mp4",
                                      filesize_approx=50 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""),
                    VideoFormatOption(format_id="136+140", resolution_label="720p", height=720, ext="mp4",
                                      filesize_approx=30 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""),
                    VideoFormatOption(format_id="135+140", resolution_label="480p", height=480, ext="mp4",
                                      filesize_approx=15 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""),
                ]
                subs = [
                    {"sub_id": "none", "language": "none", "label": "No Subtitles", "url": ""},
                ] + [
                    {"sub_id": c, "language": c, "label": c.upper(), "url": f"https://example.com/{c}.vtt"}
                    for c in ("ar", "en", "de", "es", "fr", "hi")
                ]
                import types
                ext6 = [dict(t) for t in subs[1:]]
                url = "https://youtu.be/cR4T9MDrlqE"
                mock_resolver = MagicMock()
                mock_resolver.build_stream_info.side_effect = lambda _info, sel_o: types.SimpleNamespace(
                    opt=sel_o, external_subtitle_tracks=list(getattr(sel_o, "external_subtitle_tracks", []) or [])
                )
                app.populate_main_media_bar(
                    info={"title": "Test Video Clip", "duration": 120},
                    options=opts, audio_tracks=[], subtitle_tracks=subs,
                    url=url, dest=os.path.join(dl_dir, "Video"),
                    resolver=mock_resolver,
                )
                app._main_external_subtitle_tracks = [dict(t) for t in ext6]
                app._sync_media_bar_state()

                for o in app._main_media_options:
                    self.assertEqual([t["sub_id"] for t in o.external_subtitle_tracks], ["ar", "en", "de", "es", "fr", "hi"])
                self.assertEqual(len(app._pending_media_context["external_subtitle_tracks"]), 6)

                # Stage into Col 1 (simulates Kanban staged card)
                stage_media_option_in_col1(app, url, "Test Video Clip", opts[0], app._pending_media_context["final_dest"], duration=120)
                self.assertTrue(app._staged_links, "Expected staged item in Column 1")
                info_dict = app._staged_links[0]
                self.assertEqual(len(info_dict["external_subtitle_tracks"]), 6)

                # Reopen QualitySelectionModal from cached context (as Column 1 Quality btn does)
                app._show_cached_quality_modal(app._pending_media_context)
                modal = app._quality_modal
                self.assertTrue(callable(getattr(modal.cb_sub, "open_external_subtitles_menu", None)))
                self.assertEqual(len(modal.cb_sub.get_external_subtitle_tracks()), 6)
                self.assertEqual(os.path.basename(os.path.dirname(modal.dest_path)).lower(), "video")
                self.assertEqual(os.path.dirname(os.path.dirname(modal.dest_path)), dl_dir)

                # Switch quality row in Treeview (720p -> 480p)
                modal.tree.selection_set("opt_2")
                modal._on_tree_select(None)
                self.assertEqual(modal.selected_option.resolution_label, "480p")
                self.assertEqual([t["sub_id"] for t in modal.selected_option.external_subtitle_tracks], ["ar", "en", "de", "es", "fr", "hi"])
                self.assertEqual(len(modal.cb_sub.get_external_subtitle_tracks()), 6)
                self.assertEqual(len(app._pending_media_context["external_subtitle_tracks"]), 6)

                # Start download from modal
                modal._on_download()
                app._launch_stream_coordinator.assert_called_once()
                stream_info_arg = app._launch_stream_coordinator.call_args[0][0]
                confirmed_dest = app._launch_stream_coordinator.call_args[0][1]
                self.assertEqual([t["sub_id"] for t in stream_info_arg.external_subtitle_tracks], ["ar", "en", "de", "es", "fr", "hi"])
                self.assertEqual(os.path.basename(os.path.dirname(confirmed_dest)).lower(), "video")
                self.assertEqual(os.path.dirname(os.path.dirname(confirmed_dest)), dl_dir)
        finally:
            root.destroy()

    def test_probe_and_stage_pasted_url_preserves_folder_entry_dest(self):
        import types
        from unittest.mock import MagicMock
        from faqih_downloader.ui.panels.kanban_staged_prober import probe_and_stage_pasted_url
        from faqih_downloader.services.youtube_models import YouTubeStreamInfo

        with tempfile.TemporaryDirectory() as tmp:
            dl_dir = os.path.join(tmp, "Downloads")
            video_dir = os.path.join(dl_dir, "Video")
            os.makedirs(video_dir, exist_ok=True)
            for dest_val in (dl_dir, video_dir):
                gui = types.SimpleNamespace(
                    entry_dest=MagicMock(get=MagicMock(return_value=dest_val)),
                    auto_categorize_folders=True,
                    history_manager=None,
                    _staged_links=[],
                    dispatch_to_main_thread=lambda fn: fn(),
                    _get_active_download_cookies=lambda: None,
                    stage_probed_link_in_col1=MagicMock(),
                    _get_base_downloads_dir=lambda: dl_dir,
                )
                opt = VideoFormatOption(
                    format_id="22", resolution_label="720p", height=720, ext="mp4",
                    filesize_approx=10 * 1024 * 1024, fps=30, vcodec="avc1", acodec="mp4a", note=""
                )
                raw_info = {"title": "Category Check", "duration": 60, "extractor_key": "Youtube"}

                class _InlineThread:
                    def __init__(self, target=None, daemon=False):
                        self._target = target
                    def start(self):
                        self._target()

                with patch("faqih_downloader.ui.panels.kanban_staged_prober.threading.Thread", _InlineThread), \
                     patch("faqih_downloader.services.youtube_service.YouTubeResolver.extract_format_options", return_value=(raw_info, [opt])), \
                     patch("faqih_downloader.services.youtube_models.is_ytdlp_extractor_supported", return_value=True):
                    probe_and_stage_pasted_url(gui, "https://youtu.be/cR4T9MDrlqE")

                gui.stage_probed_link_in_col1.assert_called()
                info_dict = gui.stage_probed_link_in_col1.call_args[0][0]
                final_dest = info_dict["final_dest"]
                self.assertEqual(os.path.basename(os.path.dirname(final_dest)).lower(), "video", f"Lost Video folder for entry_dest={dest_val}: {final_dest}")
                self.assertEqual(os.path.dirname(os.path.dirname(final_dest)), dl_dir, f"Parent Downloads truncated for entry_dest={dest_val}: {final_dest}")



if __name__ == "__main__":
    unittest.main()
