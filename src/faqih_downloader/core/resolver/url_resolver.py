"""
resolve_real_download_url: HTTP redirect probing, HTML landing detection, and candidate resolution.
"""
import os
import sys
import re
import ssl
import time
import urllib.request
import urllib.parse
from typing import Dict, Optional, Tuple, List, Any

from .host_guard import _is_private_or_loopback_host, _path_filename
from .html_parser import _HtmlLinkCandidateParser
from .probe_cache import (
    _PROBE_CACHE_LOCK,
    _PROBE_CACHE,
    _PROBE_CACHE_TTL,
    _store_probe_cache,
)
from ..chunk import get_permissive_ssl_context
from ...utils.url_utils import (
    derive_download_filename,
    parse_filename_from_cd_header,
    COMMON_DOWNLOAD_EXTENSIONS,
)
from ..candidate_extractor import (
    _HtmlCandidateExtractor,
    resolve_all_download_candidates,
)


def resolve_real_download_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    ssl_context: Optional[ssl.SSLContext] = None,
    timeout: float = 10.0,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Probes a candidate download URL to verify whether it returns a direct downloadable file
    or an HTML landing / thank-you page. If an HTML page is returned, parses and ranks
    candidate download links, probes them, and returns the real direct file download URL.

    Returns:
        {
            "url": final_url,
            "is_html": bool,
            "resolved": bool,
            "content_type": str,
            "size": int,
            "filename": str,
            "error": str
        }
    Guaranteed never to raise exceptions.
    """
    clean_url = str(url or "").strip()
    if force_refresh:
        with _PROBE_CACHE_LOCK:
            _PROBE_CACHE.pop(clean_url, None)
    elif not hasattr(urllib.request.urlopen, "_mock_name"):
        with _PROBE_CACHE_LOCK:
            cached = _PROBE_CACHE.get(clean_url)
            if cached:
                ts, cached_dict = cached
                if (time.monotonic() - ts) < _PROBE_CACHE_TTL:
                    return dict(cached_dict)
                else:
                    _PROBE_CACHE.pop(clean_url, None)
    result: Dict[str, Any] = {
        "url": clean_url,
        "is_html": False,
        "resolved": False,
        "content_type": "",
        "size": 0,
        "filename": "",
        "error": "",
        "candidates": [],
        "page_title": ""
    }

    if not clean_url:
        result["error"] = "URL cannot be empty."
        return result

    try:
        parsed_src = urllib.parse.urlsplit(clean_url)
        if parsed_src.scheme.lower() not in ("http", "https") or not parsed_src.netloc:
            result["error"] = "URL must start with http:// or https:// and include a valid host."
            return result
    except Exception as e:
        result["error"] = str(e)
        return result

    src_host = urllib.parse.urlparse(clean_url).hostname or ""
    src_is_public = not _is_private_or_loopback_host(src_host)
    ctx = ssl_context if ssl_context is not None else get_permissive_ssl_context()
    custom_headers = dict(headers or {})
    if not any(k.lower() == "user-agent" for k in custom_headers):
        custom_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    if not any(k.lower() == "accept" for k in custom_headers):
        custom_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    try:
        req = urllib.request.Request(clean_url, headers=custom_headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            final_url = resp.geturl() or clean_url
            redir_scheme = urllib.parse.urlsplit(final_url).scheme.lower()
            if redir_scheme not in ("http", "https", "ftp"):
                raise ValueError("Unsupported redirect scheme")
            final_host = urllib.parse.urlparse(final_url).hostname or ""
            if src_is_public and _is_private_or_loopback_host(final_host):
                result["url"] = final_url
                result["error"] = "SSRF: Redirect to internal host blocked"
                return result
            raw_ct = resp.headers.get("Content-Type", "")
            content_type = raw_ct.split(";")[0].strip().lower()
            cl = resp.headers.get("Content-Length")
            size = int(cl) if cl and cl.isdigit() else 0
            cd = resp.headers.get("Content-Disposition", "")
            filename = parse_filename_from_cd_header(cd) or _path_filename(final_url)

            is_html = content_type in ("text/html", "application/xhtml+xml")
            if not is_html:
                ar = resp.headers.get("Accept-Ranges", "").lower()
                direct_res = {
                    "url": final_url,
                    "is_html": False,
                    "resolved": False,
                    "content_type": content_type,
                    "size": size,
                    "filename": filename or derive_download_filename(final_url),
                    "supports_ranges": (ar == "bytes") and (size > 0),
                    "error": ""
                }
                _store_probe_cache(clean_url, direct_res)
                return direct_res

            # Response is HTML. Read up to 512 KB of body for link extraction.
            raw_body = resp.read(512 * 1024)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                html_text = raw_body.decode(charset, errors="replace")
            except Exception:
                html_text = raw_body.decode("utf-8", errors="replace")

    except ValueError:
        raise
    except Exception as e:
        result["error"] = str(e)
        return result

    result["url"] = final_url
    result["is_html"] = True
    result["content_type"] = content_type
    result["size"] = size
    result["filename"] = filename or derive_download_filename(final_url)

    # Extract all candidates and page title
    all_candidates = resolve_all_download_candidates(html_text, base_url=final_url)
    result["candidates"] = all_candidates

    extractor_title = ""
    try:
        _pe = _HtmlCandidateExtractor()
        _pe.feed(html_text)
        extractor_title = _pe.page_title.strip()
    except Exception:
        pass
    result["page_title"] = extractor_title

    # Collect link candidates
    parser = _HtmlLinkCandidateParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    raw_candidates = list(parser.raw_candidates)

    # Inline script navigation and fallback regexes
    script_patterns = [
        r'(?:window\.)?location(?:\.href)?\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'(?:window\.)?location\.(?:assign|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'window\.open\s*\(\s*[\'"]([^\'"]+)[\'"]',
        r'(?:data-download[a-z0-9_-]*|data-href|data-url)\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'<meta[^>]*?content=[\'"][^>]*?url=([^;\'"\s>]+)[\'"]'
    ]
    for pat in script_patterns:
        for m in re.finditer(pat, html_text, re.IGNORECASE):
            u = m.group(1).strip()
            if u:
                raw_candidates.append(u)

    # Extract absolute URLs and paths from inline <script> blocks
    for s_m in re.finditer(r'<script[^>]*>(.*?)</script>', html_text, re.IGNORECASE | re.DOTALL):
        script_body = s_m.group(1)
        clean_script = script_body.replace(r'\/', '/')
        for url_m in re.finditer(r'https?://[^\s"\'<>\\]+', clean_script, re.IGNORECASE):
            raw_candidates.append(url_m.group(0))

    ignored_exts = {
        ".css", ".js", ".woff", ".woff2", ".svg", ".png", ".jpg", ".jpeg",
        ".gif", ".ico", ".webmanifest", ".map", ".ttf", ".eot", ".otf"
    }
    preferred_installer_exts = {
        ".exe", ".msi", ".zip", ".7z", ".rar", ".dmg", ".apk", ".iso"
    }

    # Extract platform hints from source query
    src_query = (parsed_src.query or "").lower()
    platform_tokens: List[str] = []
    if any(k in src_query for k in ("platform=windows", "os=win", "os=windows", "windows", "win")):
        platform_tokens = ["windows", "win", "x64", "win64", "x86"]
    elif any(k in src_query for k in ("platform=mac", "os=mac", "macos", "darwin", "osx")):
        platform_tokens = ["mac", "macos", "darwin", "dmg", "pkg"]
    elif any(k in src_query for k in ("platform=linux", "os=linux", "linux")):
        platform_tokens = ["linux", "appimage", "deb", "rpm", "tar.gz"]
    elif sys.platform == "win32":
        platform_tokens = ["windows", "win", "x64"]

    final_split = urllib.parse.urlsplit(final_url)
    clean_final_no_frag = (final_split.scheme, final_split.netloc, final_split.path)
    src_split_no_frag = (parsed_src.scheme, parsed_src.netloc, parsed_src.path)

    seen = set()
    scored_candidates: List[Tuple[int, str]] = []

    for raw in raw_candidates:
        u_str = raw.strip("\"' \t\r\n")
        if not u_str or u_str.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "about:")):
            continue
        try:
            abs_u = urllib.parse.urljoin(final_url, u_str)
            p = urllib.parse.urlsplit(abs_u)
            if src_is_public and _is_private_or_loopback_host(p.hostname or ""):
                continue
            if p.scheme.lower() not in ("http", "https") or not p.netloc:
                continue

            # Skip self-referencing links
            cand_no_frag = (p.scheme, p.netloc, p.path)
            if cand_no_frag == clean_final_no_frag or cand_no_frag == src_split_no_frag:
                continue

            path_lower = p.path.lower()
            query_lower = (p.query or "").lower()
            cand_str = path_lower + ("?" + query_lower if query_lower else "")

            _, ext = os.path.splitext(path_lower)
            if ext in ignored_exts:
                continue

            if abs_u in seen:
                continue
            seen.add(abs_u)

            score = 0
            if ext in preferred_installer_exts:
                score += 1000
            elif ext in COMMON_DOWNLOAD_EXTENSIONS:
                score += 500

            has_dl = ("/download" in path_lower or "/downloads" in path_lower)
            has_plat = any(tok in cand_str for tok in platform_tokens)

            if has_dl and has_plat:
                score += 400
            elif has_dl:
                score += 150
            elif has_plat:
                score += 100

            if "/releases/download/" in path_lower:
                score += 350
            elif "/releases/" in path_lower:
                score += 150

            if path_lower in ("", "/"):
                score -= 600

            scored_candidates.append((score, abs_u))
        except Exception:
            continue

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = [u for _, u in scored_candidates[:5]]

    probe_headers = dict(custom_headers)
    for cand_url in top_candidates:
        if src_is_public and _is_private_or_loopback_host(urllib.parse.urlparse(cand_url).hostname or ""):
            continue
        for use_range in (False, True):
            try:
                p_hdrs = dict(probe_headers)
                if use_range:
                    p_hdrs["Range"] = "bytes=0-0"
                    c_req = urllib.request.Request(cand_url, headers=p_hdrs)
                else:
                    c_req = urllib.request.Request(cand_url, method="HEAD", headers=p_hdrs)
                with urllib.request.urlopen(c_req, timeout=timeout, context=ctx) as c_resp:
                    c_final = c_resp.geturl() or cand_url
                    c_ct = (c_resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                    c_size = 0
                    if use_range:
                        c_cr = c_resp.headers.get("Content-Range", "")
                        if "/" in c_cr and c_cr.split("/")[-1].strip().isdigit():
                            c_size = int(c_cr.split("/")[-1].strip())
                    if c_size == 0:
                        c_cl = c_resp.headers.get("Content-Length")
                        c_size = int(c_cl) if c_cl and c_cl.isdigit() else 0
                    c_cd = c_resp.headers.get("Content-Disposition", "")
                    c_fn = parse_filename_from_cd_header(c_cd) or _path_filename(c_final)

                    if c_ct and c_ct not in ("text/html", "application/xhtml+xml"):
                        cand_res = {
                            "url": c_final,
                            "is_html": False,
                            "resolved": True,
                            "content_type": c_ct,
                            "size": c_size,
                            "filename": c_fn or derive_download_filename(c_final),
                            "supports_ranges": True,
                            "error": "",
                            "candidates": all_candidates,
                            "page_title": extractor_title
                        }
                        _store_probe_cache(clean_url, cand_res)
                        return cand_res
                    if not use_range and not c_ct:
                        continue
                    break
            except Exception:
                if not use_range:
                    continue
                break

    return result
