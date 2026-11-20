"""
URL matching, platform identification, media ID extraction, and yt-dlp extractor probing.
"""
import re
import sys
from typing import Optional, Tuple, Any

from .constants import (
    YOUTUBE_URL_REGEX,
    SOCIAL_MEDIA_PATTERNS,
    PLATFORM_DISPLAY_NAMES,
)
from ..media_env.ytdlp_env import is_ytdlp_available
from ..updates.ytdlp_manager import YtDlpAutoUpdater

_CACHED_YTDLP_EXTRACTORS: Optional[Tuple[Any, ...]] = None
_YTDLP_EXTRACTORS_CACHE: Optional[Tuple[Any, ...]] = None


def is_youtube_url(url: str) -> bool:
    """Returns True if the given URL is a recognized YouTube video or shorts URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(YOUTUBE_URL_REGEX.search(url.strip()))


def is_social_media_url(url: str) -> bool:
    """
    Returns True if the given URL is a recognized social media post/video URL
    (Instagram, Facebook, X/Twitter, TikTok, Reddit, Vimeo, Dailymotion, Pinterest, etc.).
    """
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    for pat in SOCIAL_MEDIA_PATTERNS.values():
        if pat.search(u):
            return True
    return False


def _is_direct_download_url(url: str) -> bool:
    """Fast-path check for direct downloadable files without touching yt_dlp extractors."""
    try:
        from ...utils.url_utils import COMMON_DOWNLOAD_EXTENSIONS
    except Exception:
        COMMON_DOWNLOAD_EXTENSIONS = {
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz",
            ".exe", ".msi", ".iso", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
            ".bin", ".pdf", ".docx", ".xlsx", ".pptx", ".epub", ".txt",
            ".mp4", ".mp3", ".mkv", ".webm", ".avi", ".mov", ".flv"
        }
    clean_url = url.split("?")[0].split("#")[0].lower()
    path_part = clean_url.split("://", 1)[-1].partition("/")[2]
    if any(clean_url.endswith(ext) or path_part.endswith(ext) for ext in COMMON_DOWNLOAD_EXTENSIONS):
        return True
    return clean_url.endswith((".tar.gz", ".tar.bz2", ".tar.xz"))


def is_ytdlp_extractor_supported(url: str) -> bool:
    """
    Checks whether yt-dlp has a dedicated extractor matching the URL (excluding generic).
    Cached lazily for fast subsequent checks.
    """
    global _CACHED_YTDLP_EXTRACTORS, _YTDLP_EXTRACTORS_CACHE
    if not is_ytdlp_available() or not url:
        return False
    if _is_direct_download_url(url):
        return False
    try:
        with YtDlpAutoUpdater._lock:
            import yt_dlp
            if _CACHED_YTDLP_EXTRACTORS is None and _YTDLP_EXTRACTORS_CACHE is None:
                _CACHED_YTDLP_EXTRACTORS = tuple(yt_dlp.extractor.gen_extractors())
                _YTDLP_EXTRACTORS_CACHE = _CACHED_YTDLP_EXTRACTORS
            extractors = _CACHED_YTDLP_EXTRACTORS or _YTDLP_EXTRACTORS_CACHE
        for ie in extractors:
            if ie.suitable(url) and ie.IE_NAME != 'generic':
                return True
    except Exception:
        pass
    return False


_CANONICAL_IS_YTDLP_EXTRACTOR_SUPPORTED = is_ytdlp_extractor_supported


def is_media_url(url: str, check_ytdlp_extractors: bool = False) -> bool:
    """
    Returns True if the URL is recognized as YouTube or any supported social media platform.
    If check_ytdlp_extractors=True, falls back to querying yt-dlp extractor catalog.
    """
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if is_youtube_url(u) or is_social_media_url(u):
        return True
    if _is_direct_download_url(u):
        return False
    if check_ytdlp_extractors:
        legacy_mod = sys.modules.get("faqih_downloader.services.youtube_models")
        legacy_fn = getattr(legacy_mod, "is_ytdlp_extractor_supported", None) if legacy_mod is not None else None
        if legacy_fn is not None and legacy_fn is not _CANONICAL_IS_YTDLP_EXTRACTOR_SUPPORTED:
            return legacy_fn(u)
        return is_ytdlp_extractor_supported(u)
    return False


def extract_media_platform(url: str) -> str:
    """
    Identifies the platform name for a given URL (e.g. 'YouTube', 'TikTok', 'Instagram',
    'Facebook', 'Twitter / X', 'Reddit', 'Vimeo', 'Dailymotion', 'Pinterest', etc.).
    """
    if not url or not isinstance(url, str):
        return "Media"
    u = url.strip()
    if is_youtube_url(u):
        return "YouTube"
    for name, pat in SOCIAL_MEDIA_PATTERNS.items():
        if pat.search(u):
            return PLATFORM_DISPLAY_NAMES.get(name, name.capitalize())
    return "Media"


def extract_youtube_id(url: str) -> Optional[str]:
    """Extracts the 11-character YouTube video ID from a URL, or None if invalid."""
    if not url or not isinstance(url, str):
        return None
    match = YOUTUBE_URL_REGEX.search(url.strip())
    return match.group(1) if match else None


def extract_media_id(url: str) -> Optional[str]:
    """
    Extracts an identifier from a media URL if detectable, otherwise None.
    """
    if not url or not isinstance(url, str):
        return None
    yt_id = extract_youtube_id(url)
    if yt_id:
        return yt_id
    u = url.strip()
    m = re.search(r'/(?:video|reel|reels|status|pin|comments|videos|p)/([a-zA-Z0-9_-]+)', u)
    if m:
        return m.group(1)
    m2 = re.search(r'/(?:vt|vm)\.tiktok\.com/([a-zA-Z0-9_-]+)', u)
    if m2:
        return m2.group(1)
    m3 = re.search(r'/fb\.watch/([a-zA-Z0-9_.-]+)', u)
    if m3:
        return m3.group(1)
    return None
