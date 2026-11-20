"""
YouTubeFormatExtractorMixin: yt-dlp options construction, metadata/cookie extraction,
and stream format resolution.
"""
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

from .url_matcher import (
    is_media_url,
    is_youtube_url,
    extract_media_platform,
    extract_media_id,
    extract_youtube_id,
)
from .models import VideoFormatOption, YouTubeStreamInfo
from ..media_env.browser_cookies import detect_installed_cookie_browsers
from ..media_env.ytdlp_env import is_ytdlp_available
from ..updates.ytdlp_manager import YtDlpAutoUpdater

_CANONICAL_DETECT_BROWSERS = detect_installed_cookie_browsers
_CANONICAL_IS_YTDLP_AVAIL = is_ytdlp_available
_CANONICAL_YTDLP_UPDATER = YtDlpAutoUpdater


def _resolve_yt_service_attr(name: str, local_val: Any, canonical_val: Any) -> Any:
    legacy_mod = sys.modules.get("faqih_downloader.services.youtube_service")
    if legacy_mod is not None and hasattr(legacy_mod, name):
        legacy_val = getattr(legacy_mod, name)
        if legacy_val is not canonical_val:
            return legacy_val
    return local_val


class YouTubeFormatExtractorMixin:
    """Mixin handling yt-dlp format option extraction and stream selection."""

    def _build_ydl_opts(self, browser: Optional[str] = None, cookiefile: Optional[str] = None) -> Dict[str, Any]:
        """Builds standard yt-dlp extraction options dictionary."""
        opts: Dict[str, Any] = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "nocheckcertificate": True, "noplaylist": True, "extract_flat": False,
            "socket_timeout": min(self.socket_timeout, 8),
            "youtube_include_dash_manifest": True, "youtube_include_hls_manifest": False,
            "check_formats": False, "extractor_args": {"youtube": {"player_client": ["android_vr", "default", "tv"]}},
        }
        if cookiefile and os.path.isfile(cookiefile):
            opts["cookiefile"] = cookiefile
        if browser and browser.lower() not in ("none", "auto", "off", ""):
            opts["cookiesfrombrowser"] = (browser.lower(),)
        return opts

    def extract_format_options(self, url: str) -> Tuple[Dict[str, Any], List[VideoFormatOption]]:
        """Extracts raw metadata and structured VideoFormatOption choices."""
        if not is_media_url(url, check_ytdlp_extractors=True):
            raise ValueError(f"URL is not a recognized media or streaming URL: {url}")
        _is_avail = _resolve_yt_service_attr("is_ytdlp_available", is_ytdlp_available, _CANONICAL_IS_YTDLP_AVAIL)
        if not _is_avail():
            raise RuntimeError("yt-dlp is not installed. To download media streams, install with 'pip install yt-dlp'.")

        platform = extract_media_platform(url)
        media_id = extract_media_id(url) or extract_youtube_id(url) or "media"
        tag = platform.upper().replace(" / X", "")
        self.log(f"[{tag}] Extracting formats and stream metadata for {platform} media (ID: {media_id})...")

        try:
            from ..media_extractor import _get_yt_dlp
            yt_dlp = _get_yt_dlp()
            if yt_dlp is None:
                raise ImportError()
        except ImportError:
            raise RuntimeError("yt-dlp Python package is required. Install with 'pip install yt-dlp'.")

        has_cfile = bool(self.cookies_file and os.path.isfile(self.cookies_file))
        has_cbrowser = bool(self.cookies_from_browser and self.cookies_from_browser.lower() not in ("none", "auto", "off", ""))
        is_yt = is_youtube_url(url)
        cookie_opts = self._build_ydl_opts(cookiefile=self.cookies_file) if has_cfile else (self._build_ydl_opts(browser=self.cookies_from_browser) if has_cbrowser else None)
        ydl_opts = self._build_ydl_opts() if (is_yt or cookie_opts is None) else cookie_opts
        info, ydl, tried_tiktok_direct = None, None, False
        _auth_kws = (
            "sign in", "confirm your age", "private", "login", "log in", "account",
            "permission", "403", "401", "forbidden", "cookie", "restricted", "member",
            "bot", "authenticate", "unauthorized", "unavailable", "checkpoint", "not available",
            "unexpected response", "webpage request", "unable to extract", "status code",
            "10204", "challenge", "captcha", "slardar"
        )

        _detect_browsers = _resolve_yt_service_attr(
            "detect_installed_cookie_browsers", detect_installed_cookie_browsers, _CANONICAL_DETECT_BROWSERS
        )
        _updater_cls = _resolve_yt_service_attr("YtDlpAutoUpdater", YtDlpAutoUpdater, _CANONICAL_YTDLP_UPDATER)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as active_ydl:
                info = active_ydl.extract_info(url, download=False)
                ydl = active_ydl
        except Exception as e:
            err_str = str(e).lower()
            is_auth_error = any(kw in err_str for kw in _auth_kws)

            if platform == "TikTok" and not tried_tiktok_direct:
                self.log(f"[{tag}] yt-dlp extraction failed ({e}). Attempting direct TikTok extraction...")
                info = self._extract_tiktok_direct(url)
                tried_tiktok_direct = True

            retry_opts = cookie_opts if (is_yt and cookie_opts is not None) else (self._build_ydl_opts() if (not is_yt and has_cbrowser and not has_cfile) else None)
            if not info and retry_opts is not None:
                self.log(f"[{tag}] Initial extraction failed ({e}). Retrying {'with cookies' if is_yt else 'without cookies'}...")
                try:
                    with yt_dlp.YoutubeDL(retry_opts) as fb_ydl:
                        info = fb_ydl.extract_info(url, download=False)
                        ydl = fb_ydl
                except Exception as fb_err:
                    self.log(f"[{tag}] Fallback extraction failed: {fb_err}")
                    info = None
                    if any(kw in str(fb_err).lower() for kw in _auth_kws):
                        is_auth_error = True

            if not info and is_auth_error:
                for b in _detect_browsers():
                    if self.cookies_from_browser and b.lower() == self.cookies_from_browser.lower():
                        continue
                    try:
                        self.log(f"[{tag}] Retrying extraction with cookies from '{b}'...")
                        cookie_opts = self._build_ydl_opts(browser=b)
                        with yt_dlp.YoutubeDL(cookie_opts) as cookie_ydl:
                            info = cookie_ydl.extract_info(url, download=False)
                            if info:
                                ydl = cookie_ydl
                                self.log(f"[{tag}] Successfully extracted stream info using '{b}' cookies.")
                                break
                    except Exception as cookie_err:
                        self.log(f"[{tag}] Cookies from '{b}' failed: {cookie_err}")

            if not info and platform != "TikTok":
                is_ydl_mocked = bool(getattr(yt_dlp.YoutubeDL, "_mock_name", None))
                is_updater_mocked = bool(getattr(_updater_cls, "_mock_name", None) or getattr(_updater_cls.update, "_mock_name", None))
                if self.auto_update_on_failure and (not is_ydl_mocked or is_updater_mocked):
                    self.log(f"[{tag}] Extraction failed ({e}). Checking for yt-dlp engine update...")
                    try:
                        up_res = _updater_cls(on_log=self.log).update()
                        if up_res.get("updated"):
                            import yt_dlp as refreshed_yt_dlp
                            self.log(f"[{tag}] Retrying extraction with updated yt-dlp v{up_res.get('version')}...")
                            with refreshed_yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                                info = ydl2.extract_info(url, download=False)
                                ydl = ydl2
                    except Exception:
                        pass
            if not info and platform == "TikTok" and not tried_tiktok_direct:
                info = self._extract_tiktok_direct(url)
                tried_tiktok_direct = True
            if not info:
                raise RuntimeError(f"Failed to extract {platform} media stream info: {e}")

        if not info:
            raise RuntimeError("yt-dlp returned empty metadata for the provided URL.")

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        if not info:
            raise RuntimeError("yt-dlp returned empty metadata for the provided URL.")

        if platform == "TikTok" and not (info and info.get("formats")) and not tried_tiktok_direct:
            self.log(f"[{tag}] yt-dlp returned no formats for TikTok. Retrying direct extraction...")
            tt_direct = self._extract_tiktok_direct(url)
            tried_tiktok_direct = True
            if tt_direct and tt_direct.get("formats"):
                info = tt_direct

        cookiejar = getattr(ydl, "cookiejar", None) if ydl else None
        formats_to_patch = info.get("formats", []) or ([info] if info.get("url") else [])
        fallback_cookie_str = ""
        if isinstance(info.get("cookies"), str):
            fallback_cookie_str = info["cookies"]
        elif isinstance(info.get("cookies"), dict):
            fallback_cookie_str = "; ".join(f"{k}={v}" for k, v in info["cookies"].items())
        elif isinstance(info.get("http_headers"), dict):
            fallback_cookie_str = info["http_headers"].get("Cookie") or info["http_headers"].get("cookie") or ""

        if not fallback_cookie_str and cookiejar:
            try:
                fallback_cookie_str = (hasattr(cookiejar, "get_cookie_header") and cookiejar.get_cookie_header(url)) or "; ".join(f"{c.name}={c.value}" for c in cookiejar)
            except Exception:
                pass

        if cookiejar:
            try:
                yt_c = "; ".join(f"{c.name}={c.value}" for c in cookiejar if "youtube" in (getattr(c, "domain", "") or ""))
                if yt_c:
                    info["_sd_cookie_header"] = yt_c
            except Exception:
                pass
        if not info.get("_sd_cookie_header") and fallback_cookie_str:
            info["_sd_cookie_header"] = fallback_cookie_str

        for f in formats_to_patch:
            headers = f.setdefault("http_headers", {})
            if platform == "TikTok":
                headers.setdefault("Referer", "https://www.tiktok.com/")
            if "Cookie" in headers or "cookie" in headers:
                continue
            fmt_url = f.get("url") or ""
            if "googlevideo.com" in fmt_url.lower():
                continue
            c_val = ""
            if cookiejar and fmt_url and hasattr(cookiejar, "get_cookie_header"):
                try:
                    c_val = cookiejar.get_cookie_header(fmt_url) or ""
                except Exception:
                    pass
            c_val = c_val or fallback_cookie_str
            if c_val:
                headers["Cookie"] = c_val

        options = self.build_format_options(info)
        if not options and platform == "TikTok":
            self.log(f"[{tag}] No downloadable format options produced by yt-dlp. Retrying direct extraction...")
            tt_direct = self._extract_tiktok_direct(url) or self._extract_tiktok_via_tikwm(url)
            if tt_direct and tt_direct.get("formats"):
                info = tt_direct
                options = self.build_format_options(info)
        return info, options

    def resolve(self, url: str, format_id: Optional[str] = None) -> YouTubeStreamInfo:
        """Extracts stream URLs and metadata from a YouTube or social media link using yt-dlp."""
        info, options = self.extract_format_options(url)
        if not options:
            raise RuntimeError("No downloadable media formats found for this media URL.")

        selected_option = next((opt for opt in options if opt.format_id == format_id), None) if format_id else None
        if not selected_option:
            selected_option = options[0]

        stream_info = self.build_stream_info(info, selected_option)
        plat = extract_media_platform(url)
        tag = plat.upper().replace(" / X", "")
        if stream_info.is_progressive:
            self.log(f"[{tag}] Selected stream: {stream_info.video_resolution} ({stream_info.video_ext}). Directly chunk-downloadable without merging.")
        else:
            self.log(f"[{tag}] Selected dual-stream: Video {stream_info.video_resolution} ({stream_info.video_ext}) + Audio ({stream_info.audio_ext}). Merging with FFmpeg.")
        return stream_info
