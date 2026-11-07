"""
YouTube audio dubbing and subtitle tracks extraction, WebVTT-to-SRT conversion,
subtitle soft-embedding via FFmpeg, and UI selector helpers.
"""
import os
import re
import sys
from typing import Dict, List, Optional, Tuple, Callable, Any



try:
    from ...locales.i18n import tr
except Exception:
    def tr(key: str, default: str = "") -> str:  # type: ignore
        return default

try:
    from ..config import get_setting, set_setting
except Exception:
    def get_setting(k: str, d: Any = None) -> Any: return d  # type: ignore
    def set_setting(k: str, v: Any) -> bool: return True  # type: ignore

from .youtube_models import find_ffmpeg_bin
from .subtitle_processor import (
    ISO_639_2,
    _format_srt_timestamp,
    convert_vtt_to_srt,
    download_subtitle_as_srt,
    embed_subtitle_into_mp4,
    burn_subtitle_into_video,
    handle_subtitles_post_download,
)

LANG_NAMES: Dict[str, Tuple[str, str]] = {
    "en": ("English", "الإنجليزية"), "ar": ("Arabic", "العربية"), "es": ("Spanish", "الإسبانية"),
    "fr": ("French", "الفرنسية"), "de": ("German", "الألمانية"), "it": ("Italian", "الإيطالية"),
    "pt": ("Portuguese", "البرتغالية"), "ru": ("Russian", "الروسية"), "ja": ("Japanese", "اليابانية"),
    "ko": ("Korean", "الكورية"), "zh": ("Chinese", "الصينية"), "zh-hans": ("Chinese (Simplified)", "الصينية المبسطة"),
    "zh-hant": ("Chinese (Traditional)", "الصينية التقليدية"), "hi": ("Hindi", "الهندية"),
    "tr": ("Turkish", "التركية"), "id": ("Indonesian", "الإندونيسية"), "nl": ("Dutch", "الهولندية"),
    "pl": ("Polish", "البولندية"), "vi": ("Vietnamese", "الفيتنامية"), "th": ("Thai", "التايلاندية"),
}

POPULAR_AUTO_LANGS = (
    "en", "ar", "es", "fr", "de", "tr", "ru", "hi", "ja", "ko", "zh-Hans", "zh-Hant", "zh"
)


def extract_audio_tracks(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Groups audio-only formats by language/dub: Original first, then en, ar, others. Always >=1 item."""
    formats = info.get("formats", []) or []
    audio_formats = [
        f for f in formats
        if str(f.get("vcodec") or "none").lower() in ("none", "")
        and str(f.get("acodec") or "none").lower() not in ("none", "")
        and (f.get("url") or "").startswith("http")
    ]
    if not audio_formats:
        top_lang = str(info.get("language") or "und").strip().lower()
        return [{
            "track_id": "original", "language": top_lang, "label": tr("audio_original_default", "Original (Default)"),
            "format_id": "", "url": "", "ext": "m4a", "acodec": "aac", "abr": 0.0,
            "filesize": None, "is_original": True, "http_headers": {},
        }]

    max_pref = max((f.get("language_preference") for f in audio_formats if f.get("language_preference") is not None), default=-1)
    orig_lang = None
    for f in audio_formats:
        fn = str(f.get("format_note") or "").lower()
        at_id = ""
        lang = str(f.get("language") or "").strip().lower()
        if isinstance(f.get("audio_track"), dict):
            at = f["audio_track"]
            if not lang:
                lang = str(at.get("language") or "").strip().lower()
            at_id = str(at.get("id") or "").lower()
            if not lang and at_id:
                lang = at_id.split(".")[0].strip().lower()
        pref = f.get("language_preference")
        is_f_orig = (
            "original" in fn or "default" in fn
            or "original" in at_id or "default" in at_id
            or (max_pref > 0 and pref == max_pref)
        )
        if is_f_orig and lang:
            orig_lang = lang
            break
    if not orig_lang:
        top_lang = str(info.get("language") or "").strip().lower()
        first_lang = ""
        if audio_formats:
            first_f = audio_formats[0]
            first_lang = str(first_f.get("language") or "").strip().lower()
            if not first_lang and isinstance(first_f.get("audio_track"), dict):
                first_lang = str(first_f["audio_track"].get("language") or "").strip().lower()
        orig_lang = top_lang or first_lang

    def _is_manifest_f(f_dict: Dict[str, Any]) -> bool:
        proto = str(f_dict.get("protocol") or "").lower()
        u = str(f_dict.get("url") or "").lower()
        return "m3u8" in proto or "dash" in proto or ".m3u8" in u or ".mpd" in u or "/manifest/" in u

    groups: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
    for f in audio_formats:
        lang = str(f.get("language") or "").strip().lower()
        fn = str(f.get("format_note") or "").strip().lower()
        disp_name = ""
        at_id = ""
        if isinstance(f.get("audio_track"), dict):
            at = f["audio_track"]
            at_id = str(at.get("id") or "").lower()
            if not lang:
                lang = str(at.get("language") or "").strip().lower()
                if not lang and at_id:
                    lang = at_id.split(".")[0].strip().lower()
            disp_name = str(at.get("display_name") or at.get("name") or "").strip()

        pref = f.get("language_preference")
        is_orig = (
            "original" in fn or "default" in fn
            or "original" in at_id or "default" in at_id
            or (max_pref > 0 and pref == max_pref)
            or (orig_lang and lang == orig_lang and not any(tag in fn or tag in at_id for tag in ("dub", "dubbed", "descriptive")))
            or (not lang and not orig_lang)
        )
        key = "original" if is_orig else (lang or next((c for c in LANG_NAMES if c in fn), "und"))
        groups.setdefault(key, []).append((f, disp_name))

    if "original" not in groups and groups:
        groups["original"] = groups.pop(next(iter(groups.keys())))

    result: List[Dict[str, Any]] = []
    for key, f_tuples in groups.items():
        direct_cand = [t for t in f_tuples if not _is_manifest_f(t[0])]
        active_tuples = direct_cand if direct_cand else f_tuples
        best_f, best_disp = max(
            active_tuples,
            key=lambda t: (1 if str(t[0].get("ext") or "").lower() == "m4a" else 0, float(t[0].get("abr") or t[0].get("tbr") or 0.0))
        )
        abr = float(best_f.get("abr") or best_f.get("tbr") or 0.0)
        is_orig = (key == "original")
        lang_code = str(best_f.get("language") or (orig_lang if is_orig and orig_lang else key)).lower()

        if is_orig:
            label = tr("audio_original_default", "Original (Default)")
        elif best_disp:
            label = f"{best_disp} ({lang_code}) - {int(abr)}kbps" if abr > 0 else f"{best_disp} ({lang_code})"
        elif lang_code == "ar":
            label = f"العربية (ar) - {int(abr)}kbps" if abr > 0 else "العربية (ar)"
        elif lang_code == "en":
            label = f"English (en) - {int(abr)}kbps" if abr > 0 else "English (en)"
        elif lang_code in LANG_NAMES:
            name_en = LANG_NAMES[lang_code][0]
            label = f"{name_en} ({lang_code}) - {int(abr)}kbps" if abr > 0 else f"{name_en} ({lang_code})"
        else:
            label = f"{lang_code.upper()} - {int(abr)}kbps" if abr > 0 else lang_code.upper()

        fs = best_f.get("filesize") or best_f.get("filesize_approx")
        if not fs:
            dur = float(info.get("duration") or 0)
            fs = int((abr * 1000.0 / 8.0) * dur) if (abr > 0 and dur > 0) else None

        result.append({
            "track_id": key, "language": lang_code, "label": label,
            "format_id": str(best_f.get("format_id") or ""), "url": str(best_f.get("url") or ""),
            "ext": str(best_f.get("ext") or "m4a"), "acodec": str(best_f.get("acodec") or ""),
            "abr": abr, "filesize": fs,
            "is_original": is_orig, "http_headers": dict(best_f.get("http_headers") or {}),
        })

    def _sort_key(t: Dict[str, Any]) -> Tuple[int, str]:
        if t["is_original"] or t["track_id"] == "original": return (0, "")
        if t["language"] == "en": return (1, "")
        if t["language"] == "ar": return (2, "")
        return (3, t["language"])

    res = sorted(result, key=_sort_key)
    if not res:
        res = [{
            "track_id": "original", "language": str(info.get("language") or "und").strip().lower(),
            "label": tr("audio_original_default", "Original (Default)"),
            "format_id": "", "url": "", "ext": "m4a", "acodec": "aac", "abr": 0.0,
            "filesize": None, "is_original": True, "http_headers": {},
        }]
    return res


def _normalize_sub_url_and_ext(url: str, ext: str) -> Tuple[str, str]:
    """Rewrites timedtext URLs with srv3/ttml/json3/srv1 to fmt=vtt for standard WebVTT delivery."""
    if not url:
        return url, ext
    if "fmt=" in url:
        url = re.sub(r'([?&]fmt=)(?:srv3|ttml|json3|srv1)\b', r'\g<1>vtt', url)
        if "fmt=vtt" in url:
            ext = "vtt"
    elif "timedtext" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}fmt=vtt"
        ext = "vtt"
    return url, ext


def _pick_best_sub_url(sub_formats: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """Selects the best subtitle URL and extension preferring srt > vtt > ttml > srv3."""
    order = {"srt": 5, "vtt": 4, "ttml": 3, "srv3": 2, "srv1": 1, "json3": 0}
    candidates = [f for f in sub_formats if f.get("url")]
    if not candidates:
        return None
    best = max(candidates, key=lambda f: order.get(str(f.get("ext") or "").lower(), 0))
    url = best["url"]
    ext = str(best.get("ext") or "vtt").lower()
    return _normalize_sub_url_and_ext(url, ext)


def extract_subtitle_tracks(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts manual and auto-translated subtitle tracks: None first, en, ar, manual, auto."""
    webpage_url = str(info.get("webpage_url") or info.get("original_url") or "").strip()
    tracks: List[Dict[str, Any]] = [{
        "sub_id": "none", "language": "none", "label": "None / بدون ترجمة",
        "url": "", "ext": "", "is_auto": False, "fallback_urls": [], "http_headers": {},
        "webpage_url": webpage_url, "base_url": "",
    }]
    manual_subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    popular_lower = [x.lower() for x in POPULAR_AUTO_LANGS]
    base_headers = dict(info.get("http_headers") or {})
    if "Cookie" not in base_headers and "cookie" not in base_headers:
        cookie_val = info.get("_sd_cookie_header") or info.get("cookies")
        if isinstance(cookie_val, dict):
            base_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_val.items())
        elif isinstance(cookie_val, str) and cookie_val.strip():
            base_headers["Cookie"] = cookie_val.strip()

    for is_auto, sub_dict in ((False, manual_subs), (True, auto_subs)):
        for lang, flist in sub_dict.items():
            lang_norm = lang.lower()
            if "live_chat" in lang_norm or "rechat" in lang_norm:
                continue
            base_lang = lang_norm.split("-")[0].split("_")[0]
            if is_auto and lang_norm not in popular_lower and base_lang not in popular_lower and lang not in manual_subs:
                continue
            res = _pick_best_sub_url(flist)
            if not res:
                continue
            url, ext = res

            base_url = ""
            if "tlang=" in url:
                base_url = re.sub(r'([?&])tlang=[^&]*(&|$)', r'\1', url).replace("?&", "?").rstrip("?&")
            elif not is_auto:
                base_url = url
            if not base_url and is_auto:
                for orig_cand in (str(info.get("language") or "en").lower(), "en"):
                    if orig_cand in manual_subs:
                        m_res = _pick_best_sub_url(manual_subs[orig_cand])
                        if m_res and m_res[0]:
                            base_url = m_res[0]
                            break
                    if not base_url and orig_cand in auto_subs:
                        a_res = _pick_best_sub_url(auto_subs[orig_cand])
                        if a_res and a_res[0]:
                            base_url = a_res[0]
                            break

            fallback_urls: List[str] = []
            sub_headers = dict(base_headers)
            for f in flist:
                f_url = f.get("url")
                if f_url and f_url not in fallback_urls:
                    fallback_urls.append(f_url)
                if isinstance(f.get("http_headers"), dict):
                    sub_headers.update(f["http_headers"])

            if is_auto:
                suffix = "ترجمة تلقائية" if base_lang == "ar" else "Auto-Translated"
            else:
                suffix = "Official"
            name = "العربية" if base_lang == "ar" else ("English" if base_lang == "en" else LANG_NAMES.get(lang_norm, LANG_NAMES.get(base_lang, (lang.upper(), "")))[0])
            label = f"{name} ({suffix})" if base_lang != "ar" or not is_auto else f"العربية ({suffix})"
            tracks.append({
                "sub_id": f"{lang}-auto" if is_auto else lang,
                "language": lang, "label": label, "url": url, "ext": ext, "is_auto": is_auto,
                "fallback_urls": fallback_urls,
                "http_headers": sub_headers,
                "webpage_url": webpage_url,
                "base_url": base_url,
            })

    if not any(t.get("language", "").lower().startswith("ar") for t in tracks):
        base_track = next((t for t in tracks if t.get("sub_id") != "none" and (t.get("base_url") or t.get("url"))), None)
        if base_track:
            b_url = base_track.get("base_url") or base_track.get("url") or ""
            if b_url:
                sep = "&" if "?" in b_url else "?"
                ar_url = f"{b_url}{sep}tlang=ar"
                tracks.append({
                    "sub_id": "ar_auto",
                    "language": "ar",
                    "label": "العربية (ترجمة تلقائية)",
                    "url": ar_url,
                    "ext": base_track.get("ext", "vtt"),
                    "is_auto": True,
                    "fallback_urls": [ar_url],
                    "http_headers": dict(base_track.get("http_headers") or {}),
                    "webpage_url": webpage_url,
                    "base_url": b_url,
                })

    def _sub_sort_key(t: Dict[str, Any]) -> Tuple[int, int, str]:
        if t["sub_id"] == "none": return (0, 0, "")
        lang = t["language"].lower()
        sub_order = 0 if lang.startswith("ar") else (1 if lang.startswith("en") else 2)
        return (2 if t["is_auto"] else 1, sub_order, lang)

    return sorted(tracks, key=_sub_sort_key)


def build_audio_subtitle_row(*args, **kwargs):
    """Lazy wrapper to avoid circular dependency between services and ui."""
    from faqih_downloader.ui.modals.quality_tracks_ui import build_audio_subtitle_row as _impl
    return _impl(*args, **kwargs)


__all__ = [
    "LANG_NAMES",
    "POPULAR_AUTO_LANGS",
    "ISO_639_2",
    "extract_audio_tracks",
    "extract_subtitle_tracks",
    "convert_vtt_to_srt",
    "download_subtitle_as_srt",
    "embed_subtitle_into_mp4",
    "burn_subtitle_into_video",
    "handle_subtitles_post_download",
    "find_ffmpeg_bin",
    "build_audio_subtitle_row",
]
