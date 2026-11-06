"""
Data models, regular expressions, and URL/platform detection helpers
for YouTube and streaming media services.
"""
import os
import re
import sys
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any

try:
    from .updater_service import YtDlpAutoUpdater
except ImportError:
    try:
        from faqih_downloader.services.updater_service import YtDlpAutoUpdater
    except ImportError:
        from updater import YtDlpAutoUpdater

try:
    from ..config import is_test_environment
except ImportError:
    try:
        from faqih_downloader.config import is_test_environment
    except ImportError:
        def is_test_environment() -> bool:
            return bool("unittest" in sys.modules or "pytest" in sys.modules or os.environ.get("SD_TESTING") == "1")


# Regex matching various forms of YouTube URLs
YOUTUBE_URL_REGEX = re.compile(
    r'^(?:https?://)?(?:www\.|m\.|music\.)?'
    r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|v/|live/)|youtu\.be/)'
    r'([a-zA-Z0-9_-]{11})',
    re.IGNORECASE
)

# Robust regex patterns for major social media platforms
SOCIAL_MEDIA_PATTERNS = {
    "tiktok": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?tiktok\.com/(?:@[^/?#]+/(?:video|photo)/\d+|t/[a-zA-Z0-9_-]+|v/\d+)|^(?:https?://)?(?:vt|vm)\.tiktok\.com/[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "instagram": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|reels|stories|tv)/[a-zA-Z0-9_.-]+',
        re.IGNORECASE
    ),
    "facebook": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?fb\.watch/[a-zA-Z0-9_.-]+/?|^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?facebook\.com/(?:watch/?(?:\?|$)|reel/\d+|reels/\d+|share/[vr]/[a-zA-Z0-9_-]+|[^/?#]+/videos/\d+|video\.php\?(?:.*&)?v=\d+)',
        re.IGNORECASE
    ),
    "twitter": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:twitter\.com|x\.com)/[^/?#]+/status/\d+',
        re.IGNORECASE
    ),
    "reddit": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:reddit\.com/r/[^/?#]+/comments/[a-zA-Z0-9]+|redd\.it/[a-zA-Z0-9]+|v\.redd\.it/[a-zA-Z0-9]+)',
        re.IGNORECASE
    ),
    "vimeo": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?vimeo\.com/(?:channels/[a-zA-Z0-9_-]+/|groups/[a-zA-Z0-9_-]+/videos/|album/\d+/video/|video/)?\d+',
        re.IGNORECASE
    ),
    "dailymotion": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:dailymotion\.com/(?:video|embed/video)/|dai\.ly/)[a-zA-Z0-9]+',
        re.IGNORECASE
    ),
    "pinterest": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:pinterest\.(?:com|[a-z]{2}(?:\.[a-z]{2})?)/pin/|pin\.it/)[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "threads": re.compile(
        r'^(?:https?://)?(?:www\.)?threads\.net/@?[^/?#]+/post/[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "snapchat": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?snapchat\.com/(?:spotlight|story|t)/[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "twitch": re.compile(
        r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?twitch\.tv/(?:videos/\d+|clips/[a-zA-Z0-9_-]+)',
        re.IGNORECASE
    ),
    "rumble": re.compile(
        r'^(?:https?://)?(?:www\.)?rumble\.com/v[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
}

# Reserved filename characters for Windows / Linux cross-compatibility
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Supported browser sources for session cookies extraction
SUPPORTED_COOKIE_BROWSERS = ("auto", "none", "edge", "chrome", "firefox", "brave", "opera", "vivaldi")

from .media_env_helpers import (
    detect_installed_cookie_browsers,
    is_ytdlp_available,
    get_ytdlp_version,
    update_ytdlp_engine,
    find_ffmpeg_bin,
    has_ffmpeg,
)


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


_CACHED_YTDLP_EXTRACTORS: Optional[Tuple[Any, ...]] = None
_YTDLP_EXTRACTORS_CACHE: Optional[Tuple[Any, ...]] = None


def _is_direct_download_url(url: str) -> bool:
    """Fast-path check for direct downloadable files without touching yt_dlp extractors."""
    try:
        from ..utils.url_utils import COMMON_DOWNLOAD_EXTENSIONS
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
        return is_ytdlp_extractor_supported(u)
    return False


PLATFORM_DISPLAY_NAMES = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "Twitter / X",
    "reddit": "Reddit",
    "vimeo": "Vimeo",
    "dailymotion": "Dailymotion",
    "pinterest": "Pinterest",
    "threads": "Threads",
    "snapchat": "Snapchat",
    "twitch": "Twitch",
    "rumble": "Rumble",
}


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


def extract_youtube_id(url: str) -> Optional[str]:
    """Extracts the 11-character YouTube video ID from a URL, or None if invalid."""
    if not url or not isinstance(url, str):
        return None
    match = YOUTUBE_URL_REGEX.search(url.strip())
    return match.group(1) if match else None


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """
    Sanitizes a string to make it safe for use as a filesystem filename across OSes.
    Removes reserved characters and trims leading/trailing dots and spaces.
    """
    if not name:
        return "youtube_download"
    name = "".join(c for c in name if ord(c) <= 0xFFFF and c != "\ufffd")
    cleaned = INVALID_FILENAME_CHARS.sub("_", name)
    cleaned = re.sub(r'[\s_]+', ' ', cleaned).strip(" .")
    if not cleaned:
        cleaned = "youtube_download"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned


@dataclass
class VideoFormatOption:
    """
    Structured representation of a selectable download quality/format option
    for presentation in the quality selection modal and execution by the downloader.
    """
    format_id: str                      # Identifier e.g. '137+140', '22', '140'
    resolution_label: str               # e.g. '4K (2160p)', '1080p (Full HD)', '720p (HD)', 'Audio Only (M4A)'
    height: int                         # Vertical height in pixels (0 for audio-only)
    ext: str                            # Target container extension e.g. 'mp4', 'm4a', 'webm'
    filesize_approx: int                # Total estimated bytes (video + audio if merged)
    fps: int = 30                       # Framerate if video
    vcodec: str = ""                    # Video codec name
    acodec: str = ""                    # Audio codec name
    is_progressive: bool = False        # True if single stream with multiplexed audio
    is_audio_only: bool = False         # True if stream contains audio only
    video_url: str = ""                 # URL for video stream (or audio stream if audio-only)
    video_headers: Dict[str, str] = field(default_factory=dict)
    audio_url: Optional[str] = None     # Paired audio stream URL if split/adaptive
    audio_headers: Dict[str, str] = field(default_factory=dict)
    audio_ext: str = "m4a"
    audio_size: int = 0
    note: str = ""                      # Human-readable note e.g. "60 FPS • Lossless Merge (FFmpeg)"
    selected_audio_track: Optional[Dict[str, Any]] = None
    selected_subtitle_track: Optional[Dict[str, Any]] = None
    subtitle_embed_mode: str = "soft_embed"
    subtitle_position: str = "bottom"


def format_filesize(num_bytes: int) -> str:
    """Formats raw byte count into human-readable units (e.g., '142.5 MB')."""
    if not num_bytes or num_bytes <= 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_idx]}"


@dataclass
class YouTubeStreamInfo:
    """
    Resolved metadata and stream URLs for YouTube and social media streams.
    """
    video_id: str
    title: str
    clean_filename: str
    is_progressive: bool  # True if audio and video are already multiplexed in a single stream
    video_url: str
    video_headers: Dict[str, str] = field(default_factory=dict)
    video_ext: str = "mp4"
    video_resolution: str = "720p"
    video_size: int = 0
    audio_url: Optional[str] = None
    audio_headers: Dict[str, str] = field(default_factory=dict)
    audio_ext: str = "m4a"
    audio_size: int = 0
    duration: int = 0
    thumbnail_url: str = ""
    is_audio_only: bool = False
    platform: str = "YouTube"
    subtitle_track: Optional[Dict[str, Any]] = None
    audio_language: Optional[str] = None
    subtitle_embed_mode: str = "soft_embed"
    subtitle_position: str = "bottom"
    webpage_url: str = ""


# Clean alias
MediaStreamInfo = YouTubeStreamInfo


def resolve_preferred_option_index(options: List[Any]) -> int:
    """Helper resolving preferred format index using user settings."""
    try:
        from ..ui.modals.quality_modal_helpers import resolve_preferred_option_index as _res
        return _res(options)
    except Exception:
        try:
            from faqih_downloader.ui.modals.quality_modal_helpers import resolve_preferred_option_index as _res
            return _res(options)
        except Exception:
            return 0
