"""
YouTube and social media stream info builder mixin for Faqih Downloader.
"""
import sys
import copy
from typing import Dict, Any

from .models import (
    VideoFormatOption,
    YouTubeStreamInfo,
    sanitize_filename,
)
from .url_matcher import (
    extract_media_platform,
    extract_youtube_id,
    extract_media_id,
)
from .client_tier import get_format_client_tier


def _get_has_ffmpeg():
    mod = sys.modules.get("faqih_downloader.services.youtube_format_builder")
    if mod and hasattr(mod, "has_ffmpeg"):
        return getattr(mod, "has_ffmpeg")
    try:
        from ..youtube_models import has_ffmpeg
        return has_ffmpeg
    except Exception:
        from ..media_env.ffmpeg_probe import has_ffmpeg
        return has_ffmpeg


class YouTubeStreamInfoBuilderMixin:
    """Mixin constructing YouTubeStreamInfo instance ready for StreamDownloadCoordinator."""

    def build_stream_info(self, info: Dict[str, Any], option: VideoFormatOption) -> YouTubeStreamInfo:
        """
        Constructs a YouTubeStreamInfo instance ready for StreamDownloadCoordinator
        based on the selected VideoFormatOption.
        """
        opt = copy.copy(option)
        web_url = info.get("webpage_url") or ""
        platform = extract_media_platform(web_url)
        video_id = str(info.get("id") or extract_youtube_id(web_url) or extract_media_id(web_url) or "video")
        raw_title = info.get("title") or f"{platform}_Video_{video_id}"
        clean_title = sanitize_filename(raw_title)
        duration = int(info.get("duration") or 0)
        thumbnail = info.get("thumbnail", "")

        res_str = opt.resolution_label if (opt.resolution_label and "Vertical" in opt.resolution_label) else (f"{opt.height}p" if opt.height > 0 else "Audio Only")

        sel_audio = getattr(opt, "selected_audio_track", None) or getattr(opt, "audio_track", None)
        sub_track = getattr(opt, "selected_subtitle_track", None) or getattr(opt, "subtitle_track", None)
        if sub_track and sub_track.get("sub_id") in (None, "none"):
            sub_track = None
        sub_mode = getattr(opt, "subtitle_embed_mode", None)
        if not sub_mode:
            try:
                from ...config import get_setting
                sub_mode = get_setting("subtitle_embed_mode", "hard_burn")
            except Exception:
                sub_mode = "hard_burn"
        sub_pos = getattr(opt, "subtitle_position", None)
        if not sub_pos:
            try:
                from ...config import get_setting
                sub_pos = get_setting("subtitle_position", "bottom")
            except Exception:
                sub_pos = "bottom"
        sub_preset = getattr(opt, "subtitle_preset", None) or "youtube"
        sub_scale = float(getattr(opt, "subtitle_font_scale", 1.0) or 1.0)
        sub_color = getattr(opt, "subtitle_text_color", None) or "#FFFFFF"
        sub_bg = getattr(opt, "subtitle_bg_mode", None) or "box"
        sub_px = float(getattr(opt, "subtitle_pos_x", 50.0) or 50.0)
        sub_py = float(getattr(opt, "subtitle_pos_y", 86.0) or 86.0)
        audio_lang = sel_audio.get("language") if sel_audio else None

        is_dubbed_selection = bool(
            sel_audio and sel_audio.get("url") and (
                sel_audio.get("track_id") != "original" or not sel_audio.get("is_original", True)
            )
        )

        ffmpeg_available = _get_has_ffmpeg()()

        if opt.is_audio_only:
            if sel_audio and sel_audio.get("url"):
                opt.video_url = sel_audio["url"]
                opt.video_headers = sel_audio.get("http_headers") or info.get("http_headers") or {}
                if sel_audio.get("ext"):
                    opt.ext = sel_audio["ext"]
                if sel_audio.get("filesize"):
                    opt.filesize_approx = int(sel_audio["filesize"])
        elif is_dubbed_selection and (not opt.is_progressive or ffmpeg_available):
            opt.is_progressive = False
            opt.audio_url = sel_audio["url"]
            opt.audio_ext = sel_audio.get("ext", "m4a")
            opt.audio_headers = sel_audio.get("http_headers") or info.get("http_headers") or {}
            if hasattr(opt, "audio_format_id"):
                setattr(opt, "audio_format_id", sel_audio.get("format_id", ""))
            if sel_audio.get("filesize"):
                opt.audio_size = int(sel_audio["filesize"])
        elif sel_audio and sel_audio.get("url") and not opt.is_progressive:
            is_orig_sel = bool(sel_audio.get("is_original") or sel_audio.get("track_id") == "original")
            ext_opt_m4a = (opt.audio_ext or "").lower() in ("m4a", "mp4")
            ext_sel_m4a = (sel_audio.get("ext") or "").lower() in ("m4a", "mp4")
            opt_tier = get_format_client_tier({"url": opt.audio_url})
            sel_tier = get_format_client_tier(sel_audio)
            keep_existing = (
                is_orig_sel and bool(opt.audio_url)
                and (opt_tier >= sel_tier)
                and (opt_tier > sel_tier or ext_opt_m4a >= ext_sel_m4a)
            )
            if not keep_existing:
                opt.audio_url = sel_audio["url"]
                opt.audio_ext = sel_audio.get("ext", "m4a")
                opt.audio_headers = sel_audio.get("http_headers") or info.get("http_headers") or {}
                if hasattr(opt, "audio_format_id"):
                    setattr(opt, "audio_format_id", sel_audio.get("format_id", ""))
                if sel_audio.get("filesize"):
                    opt.audio_size = int(sel_audio["filesize"])

        webpage_url = str(info.get("webpage_url") or info.get("original_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else ""))
        out_fn = f"{clean_title}.{opt.ext}"

        if opt.is_audio_only:
            res_info = YouTubeStreamInfo(
                video_id=video_id, title=raw_title, clean_filename=out_fn, is_progressive=True,
                video_url=opt.video_url, video_headers=opt.video_headers, video_ext=opt.ext,
                video_resolution="Audio Only", video_size=opt.filesize_approx, audio_url=None,
                audio_headers={}, audio_ext=opt.audio_ext or opt.ext, audio_size=0,
                duration=duration, thumbnail_url=thumbnail, is_audio_only=True,
                platform=platform, subtitle_track=sub_track, audio_language=audio_lang,
                subtitle_embed_mode=sub_mode, subtitle_position=sub_pos,
                subtitle_preset=sub_preset, subtitle_font_scale=sub_scale,
                subtitle_text_color=sub_color, subtitle_bg_mode=sub_bg,
                subtitle_pos_x=sub_px, subtitle_pos_y=sub_py, webpage_url=webpage_url,
            )
        elif opt.is_progressive or not opt.audio_url:
            res_info = YouTubeStreamInfo(
                video_id=video_id, title=raw_title, clean_filename=out_fn, is_progressive=True,
                video_url=opt.video_url, video_headers=opt.video_headers, video_ext=opt.ext,
                video_resolution=res_str, video_size=opt.filesize_approx, audio_url=None,
                audio_headers={}, audio_ext="", audio_size=0, duration=duration,
                thumbnail_url=thumbnail, is_audio_only=False, platform=platform,
                subtitle_track=sub_track, audio_language=audio_lang, subtitle_embed_mode=sub_mode,
                subtitle_position=sub_pos, subtitle_preset=sub_preset, subtitle_font_scale=sub_scale,
                subtitle_text_color=sub_color, subtitle_bg_mode=sub_bg,
                subtitle_pos_x=sub_px, subtitle_pos_y=sub_py, webpage_url=webpage_url,
            )
        else:
            v_size = max(0, opt.filesize_approx - opt.audio_size) if opt.audio_size else opt.filesize_approx
            af_id = str(opt.selected_audio_track.get("format_id") or "") if isinstance(opt.selected_audio_track, dict) else ""
            res_info = YouTubeStreamInfo(
                video_id=video_id, title=raw_title, clean_filename=out_fn, is_progressive=False,
                video_url=opt.video_url, video_headers=opt.video_headers, video_ext=opt.ext,
                video_resolution=res_str, video_size=v_size, audio_url=opt.audio_url,
                audio_headers=opt.audio_headers, audio_ext=opt.audio_ext, audio_size=opt.audio_size,
                duration=duration, thumbnail_url=thumbnail, is_audio_only=False, platform=platform,
                subtitle_track=sub_track, audio_language=audio_lang, subtitle_embed_mode=sub_mode,
                subtitle_position=sub_pos, subtitle_preset=sub_preset, subtitle_font_scale=sub_scale,
                subtitle_text_color=sub_color, subtitle_bg_mode=sub_bg,
                subtitle_pos_x=sub_px, subtitle_pos_y=sub_py, webpage_url=webpage_url, audio_format_id=af_id,
            )
        from ..clipper.state_sync import enrich_stream_info_with_clip
        return enrich_stream_info_with_clip(res_info, opt)
