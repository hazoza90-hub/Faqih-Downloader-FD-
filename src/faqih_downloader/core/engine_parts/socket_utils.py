"""
Socket configuration and windowed URL construction helpers.
"""
import re
import ssl
import socket
import urllib.request
from typing import Optional, Any

GOOGLEVIDEO_WINDOW_BYTES = 4 * 1024 * 1024  # 4 MB fast window with &range= query param + keep-alive reuse


def _configure_fast_socket(conn: Any) -> None:
    """Applies 1s timeout, TCP_NODELAY, SO_KEEPALIVE, and 1MB SO_RCVBUF for jitter resilience."""
    sock = getattr(conn, "sock", None)
    if sock is None:
        return
    try:
        sock.settimeout(1.0)
    except Exception:
        pass
    for lvl, opt, val in (
        (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        (socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
    ):
        try:
            sock.setsockopt(lvl, opt, val)
        except Exception:
            pass


def _build_window_url(url: str, start_byte: int, end_byte: Optional[int], is_gv: bool, req_num: Optional[int] = None) -> str:
    """Replaces query range=/rn= params for googlevideo.com Initial Burst windowed HTTP 200 GETs."""
    if not is_gv or end_byte is None or not url:
        return url
    cleaned = re.sub(r"&(?:range|rn)=[^&]*", "", url, flags=re.IGNORECASE)
    cleaned = re.sub(r"\?(?:range|rn)=[^&]*&", "?", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\?(?:range|rn)=[^&]*$", "", cleaned, flags=re.IGNORECASE)
    sep = "&" if "?" in cleaned else "?"
    suffix = f"range={start_byte}-{end_byte}"
    if req_num is not None:
        suffix += f"&rn={req_num}"
    return f"{cleaned}{sep}{suffix}"


def _is_urlopen_mocked() -> bool:
    """Checks if urllib.request.urlopen is replaced by a unittest mock."""
    fn = getattr(urllib.request, "urlopen", None)
    return fn is not None and (hasattr(fn, "_mock_name") or "mock" in type(fn).__name__.lower() or hasattr(fn, "side_effect"))


def _is_ssl_socket(conn: Any) -> bool:
    """Returns True if conn or its wrapped _conn owns an active ssl.SSLSocket."""
    sock = getattr(conn, "sock", None) or getattr(getattr(conn, "_conn", None), "sock", None)
    return isinstance(sock, ssl.SSLSocket)
