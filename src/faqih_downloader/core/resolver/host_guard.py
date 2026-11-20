"""
Host validation and SSRF protection helpers.
"""
import os
import ipaddress
import urllib.parse


def _is_private_or_loopback_host(hostname: str) -> bool:
    """Checks if hostname is loopback, internal, or private IP address to prevent SSRF."""
    h = (hostname or "").strip().lower().strip("[]")
    if not h or h == "localhost" or h.endswith(".local") or h.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return bool(ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)
    except ValueError:
        return False


def _path_filename(u: str) -> str:
    """Extracts decoded filename from URL path if valid."""
    try:
        p = urllib.parse.urlsplit(u).path
        b = os.path.basename(urllib.parse.unquote(p.rstrip("/")))
        return b if b and b not in (".", "..") else ""
    except Exception:
        return ""
