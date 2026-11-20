"""
upstream_streamer.py: Upstream HTTP byte-range streaming and 2MB windowed YouTube proxy streaming.
"""
from __future__ import annotations

import http.server
import re
import urllib.error
import urllib.request
from typing import Any, Dict

from ...core.chunk import get_permissive_ssl_context


def _open_window_stream(target_url: str, headers: Dict[str, str], session: Any = None):
    """
    Opens a single window HTTP range stream.
    Uses requests.Session if provided, or urllib.request fallback if requests is unavailable.
    """
    if session is not None:
        resp = session.get(target_url, headers=headers, stream=True, timeout=15, verify=False)
        status = resp.status_code
        cr = resp.headers.get("Content-Range", "")
        ct = resp.headers.get("Content-Type", "video/mp4")

        def _iter():
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    break
                yield chunk

        return resp, status, cr, ct, _iter
    else:
        req = urllib.request.Request(target_url, headers=headers)
        ctx = get_permissive_ssl_context()
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        status = resp.getcode() or 200
        cr = resp.headers.get("Content-Range", "")
        ct = resp.headers.get("Content-Type", "video/mp4")

        def _iter():
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                yield chunk

        return resp, status, cr, ct, _iter


def stream_upstream_media(
    handler: http.server.BaseHTTPRequestHandler,
    target_url: str,
    custom_headers: Dict[str, str],
    is_head: bool = False,
) -> None:
    """
    Forwards Range requests and essential HTTP headers upstream,
    proxying chunks back to the browser or FFmpeg with 206 Partial Content / 200 OK.
    Uses high-speed 2MB windowed range proxying for googlevideo.com and gvt1.com.
    """
    if not target_url or not target_url.startswith("http"):
        handler.send_response(404)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return

    ua = (
        custom_headers.get("User-Agent")
        or custom_headers.get("user-agent")
        or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    is_google_media = bool("googlevideo.com" in target_url or "gvt1.com" in target_url)
    client_range = handler.headers.get("Range")

    # High-speed windowed streaming for googlevideo to bypass YouTube throttling
    if not is_head and is_google_media:
        start_byte = 0
        end_byte_target = None
        is_open_ended = True
        if client_range:
            m = re.match(r"^bytes=(\d+)-(\d+)?$", client_range.strip())
            if m:
                start_byte = int(m.group(1))
                if m.group(2):
                    end_byte_target = int(m.group(2))
                    is_open_ended = False

        WINDOW_SIZE = 2 * 1024 * 1024  # 2 MB window
        req_len = (end_byte_target - start_byte + 1) if end_byte_target is not None else None
        needs_windowed = is_open_ended or (req_len is not None and req_len > WINDOW_SIZE)

        if needs_windowed:
            session = None
            try:
                import requests
                if hasattr(requests, "Session"):
                    try:
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    except Exception:
                        pass
                    session = requests.Session()
            except Exception:
                session = None

            s_headers = {
                k: str(v) for k, v in (custom_headers or {}).items()
                if k.lower() not in ("host", "range", "content-length", "connection")
            }
            s_headers["User-Agent"] = ua
            first_end = (start_byte + WINDOW_SIZE - 1) if end_byte_target is None else min(start_byte + WINDOW_SIZE - 1, end_byte_target)
            s_headers["Range"] = f"bytes={start_byte}-{first_end}"

            first_resp = None
            try:
                if session is not None:
                    try:
                        first_resp, status_code, cr, ct, chunks = _open_window_stream(target_url, s_headers, session)
                    except Exception:
                        session = None
                if session is None:
                    first_resp, status_code, cr, ct, chunks = _open_window_stream(target_url, s_headers, None)

                cr_match = re.search(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", cr, re.IGNORECASE) if cr else None

                if status_code == 206 and cr_match:
                    c_start = int(cr_match.group(1))
                    c_end = int(cr_match.group(2))
                    tot_str = cr_match.group(3)
                    tot_size = int(tot_str) if tot_str != "*" else None

                    if tot_size is not None and end_byte_target is None:
                        final_end = tot_size - 1
                    elif tot_size is not None and end_byte_target is not None:
                        final_end = min(end_byte_target, tot_size - 1)
                    else:
                        final_end = end_byte_target if end_byte_target is not None else c_end

                    resp_len = final_end - start_byte + 1
                    handler.send_response(206 if client_range else 200)
                    handler.send_header("Content-Type", ct)
                    handler.send_header("Accept-Ranges", "bytes")
                    if client_range:
                        tot_disp = str(tot_size) if tot_size is not None else "*"
                        handler.send_header("Content-Range", f"bytes {start_byte}-{final_end}/{tot_disp}")
                    handler.send_header("Content-Length", str(resp_len))
                    handler.send_header("Access-Control-Allow-Origin", "*")
                    handler.send_header("Access-Control-Allow-Headers", "*")
                    handler.send_header("Cache-Control", "no-cache")
                    handler.end_headers()

                    try:
                        for chunk in chunks():
                            handler.wfile.write(chunk)
                    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
                        first_resp.close()
                        if session:
                            session.close()
                        return
                    first_resp.close()

                    cur_start = c_end + 1
                    while cur_start <= final_end:
                        cur_end = min(cur_start + WINDOW_SIZE - 1, final_end)
                        s_headers["Range"] = f"bytes={cur_start}-{cur_end}"
                        try:
                            try:
                                win_resp, win_code, w_cr, _, win_chunks = _open_window_stream(target_url, s_headers, session)
                            except Exception:
                                if session is not None:
                                    session = None
                                    win_resp, win_code, w_cr, _, win_chunks = _open_window_stream(target_url, s_headers, None)
                                else:
                                    raise
                            try:
                                if win_code not in (200, 206):
                                    break
                                for chunk in win_chunks():
                                    handler.wfile.write(chunk)
                                w_match = re.search(r"bytes\s+(\d+)-(\d+)", w_cr, re.IGNORECASE) if w_cr else None
                                if w_match:
                                    cur_start = max(cur_start + 1, int(w_match.group(2)) + 1)
                                else:
                                    cur_start = cur_end + 1
                            finally:
                                win_resp.close()
                        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
                            break
                        except Exception:
                            break
                    if session:
                        session.close()
                    return
                else:
                    if first_resp:
                        first_resp.close()
                    if session:
                        session.close()
            except Exception:
                if first_resp:
                    try:
                        first_resp.close()
                    except Exception:
                        pass
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass

    # Standard direct streaming fallback
    req = urllib.request.Request(target_url)
    req.add_header("User-Agent", ua)
    for k, v in custom_headers.items():
        if k.lower() not in ("host", "user-agent", "range"):
            req.add_header(k, str(v))

    if client_range:
        req.add_header("Range", client_range)

    ctx = get_permissive_ssl_context()
    try:
        upstream = urllib.request.urlopen(req, timeout=18, context=ctx)
        code = upstream.getcode() or 200
    except urllib.error.HTTPError as err:
        handler.send_response(err.code)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return
    except Exception:
        handler.send_response(502)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return

    try:
        handler.send_response(code)
        headers = [
            ("Content-Type", upstream.headers.get("Content-Type", "video/mp4")),
            ("Content-Length", upstream.headers.get("Content-Length")),
            ("Content-Range", upstream.headers.get("Content-Range")),
            ("Accept-Ranges", "bytes"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "*"),
            ("Cache-Control", "no-cache"),
        ]
        for h, v in headers:
            if v:
                handler.send_header(h, v)
        handler.end_headers()
        if is_head:
            return

        chunk_size = 64 * 1024
        while True:
            chunk = upstream.read(chunk_size)
            if not chunk:
                break
            handler.wfile.write(chunk)
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError):
        pass
    finally:
        try:
            upstream.close()
        except Exception:
            pass


__all__ = [
    "_open_window_stream",
    "stream_upstream_media",
]
