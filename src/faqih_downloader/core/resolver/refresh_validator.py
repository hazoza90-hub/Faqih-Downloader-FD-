"""
validate_refresh_url: expired-link refresh URL validation via HEAD and GET Range requests.
"""
import ssl
import sys
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Tuple, Any

from .host_guard import _is_private_or_loopback_host
from ..chunk import get_permissive_ssl_context


def _get_resolve_real_download_url():
    legacy_mod = sys.modules.get("faqih_downloader.core.html_resolver")
    if legacy_mod is not None and hasattr(legacy_mod, "resolve_real_download_url"):
        fn = getattr(legacy_mod, "resolve_real_download_url")
        from .url_resolver import resolve_real_download_url as canonical_fn
        if fn is not canonical_fn:
            return fn
    from .url_resolver import resolve_real_download_url
    return resolve_real_download_url


def validate_refresh_url(
    new_url: str,
    expected_size: int = 0,
    check_range: bool = True,
    timeout: float = 12.0,
    ssl_context: Optional[ssl.SSLContext] = None,
    headers: Optional[Dict[str, str]] = None
) -> Tuple[bool, str, int, bool]:
    """
    Validates a candidate refresh URL via HTTP HEAD and GET Range requests.
    Verifies that the new URL is accessible, points to the same file size (if expected_size > 0),
    and accepts HTTP Range byte requests (if check_range is True).
    Returns: (is_valid: bool, status_message: str, resolved_total_size: int, supports_ranges: bool)
    """
    clean_url = str(new_url or "").strip()
    if not clean_url:
        return False, "URL cannot be empty.", 0, False

    try:
        parsed = urllib.parse.urlsplit(clean_url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            return False, "URL must start with http:// or https:// and include a valid domain.", 0, False
    except Exception as e:
        return False, f"Malformed URL: {e}", 0, False

    src_host = urllib.parse.urlparse(clean_url).hostname or ""
    src_is_public = not _is_private_or_loopback_host(src_host)
    ctx = ssl_context if ssl_context is not None else get_permissive_ssl_context()
    custom_headers = dict(headers or {})
    if not any(k.lower() == "user-agent" for k in custom_headers):
        custom_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"

    resolved_size = 0
    supports_ranges = False
    head_ok = False
    head_error_code = None
    head_error_reason = ""

    # 1. Attempt HTTP HEAD probe
    try:
        head_req = urllib.request.Request(clean_url, method="HEAD", headers=custom_headers)
        with urllib.request.urlopen(head_req, timeout=timeout, context=ctx) as resp:
            head_ok = True
            cl = resp.headers.get("Content-Length")
            ar = resp.headers.get("Accept-Ranges", "").lower()
            if cl and cl.isdigit():
                resolved_size = int(cl)
            if ar == "bytes":
                supports_ranges = True
    except urllib.error.HTTPError as e:
        e.close()
        head_error_code = e.code
        head_error_reason = str(getattr(e, "reason", e))
        # Note: Do not abort immediately on HEAD 401/403/405/501!
        # Many S3 pre-signed URLs, Cloudflare tokens, and media CDNs only sign GET,
        # rejecting HEAD with 403 or 405. We fall through to verify with GET Range probe.
    except urllib.error.URLError as e:
        return False, f"Failed to connect to host: {e.reason}", 0, False
    except Exception as e:
        return False, f"Connection error: {e}", 0, False

    # 2. Test Range support with GET Range: bytes=0-0 if check_range requested or HEAD didn't confirm ranges/size
    if check_range or not head_ok or resolved_size == 0 or not supports_ranges:
        try:
            range_req = urllib.request.Request(clean_url, headers=custom_headers)
            range_req.add_header("Range", "bytes=0-0")
            with urllib.request.urlopen(range_req, timeout=timeout, context=ctx) as resp:
                code = resp.getcode()
                cr = resp.headers.get("Content-Range", "")

                try:
                    resp.read(min(1024, resolved_size or 1024))
                except Exception:
                    pass

                if code == 206:
                    supports_ranges = True
                    if "/" in cr:
                        total_part = cr.split("/")[-1].strip()
                        if total_part.isdigit():
                            resolved_size = int(total_part)
                elif code == 200:
                    supports_ranges = False
                    if not resolved_size:
                        cl = resp.headers.get("Content-Length")
                        if cl and cl.isdigit():
                            resolved_size = int(cl)
                else:
                    supports_ranges = False
        except urllib.error.HTTPError as e:
            e.close()
            if e.code in (401, 403, 410):
                return False, f"Server returned HTTP {e.code} ({e.reason}) — the download link is expired or unauthorized.", 0, False
            if e.code == 404:
                return False, f"Server returned HTTP 404: Not Found — file does not exist at this address.", 0, False
            if not head_ok:
                return False, f"Server returned HTTP {e.code} ({e.reason}).", 0, False
        except Exception as e:
            if not head_ok:
                return False, f"Range connection test failed: {e}", 0, False

    # If HEAD failed with 401/403/410 and GET Range was not verified or supported
    if not head_ok and head_error_code in (401, 403, 410) and not supports_ranges and resolved_size == 0:
        return False, f"Server returned HTTP {head_error_code} ({head_error_reason}) — link is expired or unauthorized.", 0, False

    # 3. Size match validation if an expected size was provided
    if expected_size > 0 and resolved_size > 0:
        if resolved_size != expected_size:
            return (
                False,
                f"File size mismatch: New link points to {resolved_size:,} bytes, "
                f"but existing download is {expected_size:,} bytes.",
                resolved_size,
                supports_ranges
            )

    # 4. Range requirement validation if partial chunks exist
    if check_range and not supports_ranges:
        return (
            False,
            "Server does not support HTTP Range requests (HTTP 206), which is required to resume partial chunks without restarting.",
            resolved_size,
            False
        )

    return True, "URL verified successfully.", resolved_size, supports_ranges
