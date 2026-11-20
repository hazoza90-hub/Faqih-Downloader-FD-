"""
YouTube format client throttling tier ranking for Faqih Downloader.
"""
import re
from typing import Dict, Any


def get_format_client_tier(f: Dict[str, Any]) -> int:
    """Ranks yt-dlp format URLs by client throttling tier (2=Android/iOS, 1=other, 0=WEB/MWEB/TV, -1=throttled)."""
    if not isinstance(f, dict):
        return 1
    try:
        if float(f.get("preference") or 0.0) <= -1000:
            return -1
    except Exception:
        pass
    if "throttled" in str(f.get("format_note") or "").lower():
        return -1
    m_c = re.search(r'[?&]c=([^&]+)', str(f.get("url") or ""), re.IGNORECASE)
    if not m_c:
        return 1
    cv = m_c.group(1).upper()
    if cv.startswith("ANDROID") or cv.startswith("IOS"):
        return 2
    if cv.startswith("WEB") or cv.startswith("MWEB") or cv.startswith("TV"):
        return 0
    return 1
