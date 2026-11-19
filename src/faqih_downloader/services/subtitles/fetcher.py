"""
fetcher.py: Multi-phase subtitle network fetching (direct HTTP, browser cookies, and yt-dlp).
"""
import os
import sys
import ssl
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Callable

try:
    from ...config import get_setting
except Exception:
    try:
        from faqih_downloader.config import get_setting
    except Exception:
        def get_setting(k: str, d: Any = None) -> Any: return d  # type: ignore

try:
    from ..media_env.browser_cookies import _resolve_cookie_browser, detect_installed_cookie_browsers
except Exception:
    try:
        from faqih_downloader.services.media_env.browser_cookies import (
            _resolve_cookie_browser,
            detect_installed_cookie_browsers,
        )
    except Exception:
        def _resolve_cookie_browser(b: Any) -> Optional[str]: return None
        def detect_installed_cookie_browsers() -> List[str]: return ["edge", "chrome", "firefox"]  # type: ignore

try:
    import requests
except ImportError:
    requests = None


def _fetch_url_direct(url: str, headers: Dict[str, str], timeout: int = 15) -> Optional[str]:
    """Performs direct HTTP GET via requests or urllib."""
    if requests is not None:
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.content.decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        req = urllib.request.Request(url, headers=headers)
        try:
            default_ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=default_ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (ssl.SSLError, urllib.error.URLError, Exception):
            ctx = ssl._create_unverified_context() if hasattr(ssl, "_create_unverified_context") else None
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _resolve_detect_browsers(detect_browsers_fn: Optional[Callable[[], List[str]]] = None) -> Callable[[], List[str]]:
    """Resolves cookie browser detector preserving monkeypatches on legacy shims."""
    if detect_browsers_fn is not None:
        return detect_browsers_fn
    default_detect = detect_installed_cookie_browsers
    for mod_name in (
        "faqih_downloader.services.subtitle_processor",
        "faqih_downloader.services.subtitle_downloader",
        "faqih_downloader.services.media_env_helpers",
    ):
        mod = sys.modules.get(mod_name)
        cand = getattr(mod, "detect_installed_cookie_browsers", None) if mod else None
        if cand is not None and cand is not default_detect:
            return cand
    return default_detect


def _fetch_urls_with_cookies(
    cand_urls: List[str],
    headers: Dict[str, str],
    parse_fn: Callable[[str], Any],
    timeout: int = 15,
    detect_browsers_fn: Optional[Callable[[], List[str]]] = None,
) -> Any:
    """Attempts fetching candidate URLs using locally installed browser cookies."""
    detect_fn = _resolve_detect_browsers(detect_browsers_fn)
    try:
        import yt_dlp.cookies
        for b in detect_fn():
            try: cj = yt_dlp.cookies.extract_cookies_from_browser(b)
            except Exception: cj = None
            if not cj: continue
            hdr = dict(headers)
            try:
                cstr = "; ".join(f"{c.name}={c.value}" for c in cj)
                if cstr: hdr["Cookie"] = cstr
            except Exception: pass
            for u in cand_urls:
                if requests is not None:
                    try:
                        r = requests.get(u, headers=hdr, cookies=cj, timeout=timeout)
                        if r.status_code == 200:
                            res = parse_fn(r.content.decode("utf-8", errors="replace"))
                            if res: return res
                    except Exception: pass
                try:
                    req = urllib.request.Request(u, headers=hdr)
                    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                    with opener.open(req, timeout=timeout) as resp:
                        res = parse_fn(resp.read().decode("utf-8", errors="replace"))
                        if res: return res
                except Exception: pass
    except Exception: pass
    return None


def _fetch_via_ytdlp(webpage_url: str, lang: str, http_headers: Any, parse_fn: Callable[[str], Any]) -> Any:
    """Extracts and parses subtitles via yt_dlp into a temporary directory."""
    try:
        import tempfile, yt_dlp
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts: Dict[str, Any] = {
                "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": [lang], "subtitlesformat": "srt/vtt/ttml/srv3/json3/best",
                "skip_download": True, "quiet": True, "no_warnings": True,
                "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
            }
            cb = _resolve_cookie_browser(get_setting("cookies_browser", "none"))
            if cb: ydl_opts["cookiesfrombrowser"] = (cb,)
            if isinstance(http_headers, dict) and http_headers:
                ydl_opts["http_headers"] = http_headers
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try: ydl.download([webpage_url])
                except Exception: pass
            for fn in os.listdir(tmp_dir):
                fp = os.path.join(tmp_dir, fn)
                if os.path.isfile(fp) and any(fp.endswith(e) for e in (".srt", ".vtt", ".ttml", ".srv3", ".xml", ".json3")):
                    try:
                        with open(fp, "r", encoding="utf-8-sig", errors="replace") as sf:
                            res = parse_fn(sf.read())
                            if res: return res
                    except Exception: pass
    except Exception: pass
    return None


__all__ = [
    "_fetch_url_direct",
    "_fetch_urls_with_cookies",
    "_fetch_via_ytdlp",
]
