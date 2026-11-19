"""
browser_cookies.py: Browser cookie installation detection and yt-dlp cookie source resolution.
"""
import os
from typing import List, Optional


def detect_installed_cookie_browsers() -> List[str]:
    """
    Detects installed web browsers capable of supplying session cookies to yt-dlp.
    Checks standard Windows user data paths under %LOCALAPPDATA% and %APPDATA%:
    - 'firefox': %APPDATA%\\Mozilla\\Firefox\\Profiles
    - 'edge': %LOCALAPPDATA%\\Microsoft\\Edge\\User Data
    - 'chrome': %LOCALAPPDATA%\\Google\\Chrome\\User Data
    - 'brave': %LOCALAPPDATA%\\BraveSoftware\\Brave-Browser\\User Data
    - 'opera': %APPDATA%\\Opera Software\\Opera Stable
    - 'vivaldi': %LOCALAPPDATA%\\Vivaldi\\User Data
    Returns list of detected browser names; falls back to ['edge', 'chrome', 'firefox'] if none found on disk.
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    home = os.path.expanduser("~")

    browser_checks = [
        ("firefox", [
            os.path.join(appdata, "Mozilla", "Firefox", "Profiles") if appdata else "",
            os.path.join(userprofile, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles") if userprofile else "",
            os.path.join(home, ".mozilla", "firefox"),
        ]),
        ("edge", [
            os.path.join(local_appdata, "Microsoft", "Edge", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Microsoft", "Edge", "User Data") if userprofile else "",
            os.path.join(home, ".config", "microsoft-edge"),
        ]),
        ("chrome", [
            os.path.join(local_appdata, "Google", "Chrome", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Google", "Chrome", "User Data") if userprofile else "",
            os.path.join(home, ".config", "google-chrome"),
        ]),
        ("brave", [
            os.path.join(local_appdata, "BraveSoftware", "Brave-Browser", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data") if userprofile else "",
            os.path.join(home, ".config", "BraveSoftware", "Brave-Browser"),
        ]),
        ("opera", [
            os.path.join(appdata, "Opera Software", "Opera Stable") if appdata else "",
            os.path.join(userprofile, "AppData", "Roaming", "Opera Software", "Opera Stable") if userprofile else "",
            os.path.join(home, ".config", "opera"),
        ]),
        ("vivaldi", [
            os.path.join(local_appdata, "Vivaldi", "User Data") if local_appdata else "",
            os.path.join(userprofile, "AppData", "Local", "Vivaldi", "User Data") if userprofile else "",
            os.path.join(home, ".config", "vivaldi"),
        ]),
    ]

    detected: List[str] = []
    for name, candidate_paths in browser_checks:
        for p in candidate_paths:
            if p and os.path.isdir(p):
                detected.append(name)
                break

    return detected if detected else ["edge", "chrome", "firefox"]


def _resolve_cookie_browser(cb: Optional[str]) -> Optional[str]:
    """Resolves 'auto' or browser names to a concrete installed browser for yt-dlp."""
    if not cb:
        return None
    val = str(cb).strip().lower()
    if val in ("none", "off", "disabled", "file", ""):
        return None
    if val == "auto":
        detected = detect_installed_cookie_browsers()
        return detected[0] if detected else None
    if val in ("chrome", "edge", "firefox", "brave", "opera", "vivaldi", "safari", "chromium"):
        return val
    return val


__all__ = [
    "detect_installed_cookie_browsers",
    "_resolve_cookie_browser",
]
