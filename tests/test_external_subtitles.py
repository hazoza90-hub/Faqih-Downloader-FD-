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


if __name__ == "__main__":
    unittest.main()
