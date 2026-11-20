"""
Regular expressions, platform identifiers, and static configuration constants
for YouTube and universal streaming media detection.
"""
import re

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
