"""
Application data/plugin directory resolvers, trusted update URL validation,
and SSL context factories.
"""
import os
import sys
import ssl
import urllib.parse
from typing import Optional

from .constants import APP_ID


def get_app_data_dir() -> str:
    """Returns persistent application data directory (%APPDATA%\\SmartDownload on Windows)."""
    cfg_override = os.environ.get("SD_CONFIG_DIR")
    if cfg_override:
        try:
            os.makedirs(cfg_override, exist_ok=True)
        except Exception:
            pass
        return cfg_override
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            cfg = os.path.join(appdata, APP_ID)
        else:
            cfg = os.path.join(os.path.expanduser("~"), ".smartdownload")
    else:
        cfg = os.path.join(os.path.expanduser("~"), ".smartdownload")
    try:
        os.makedirs(cfg, exist_ok=True)
    except Exception:
        pass
    return cfg


def get_ytdlp_plugin_dir(base_dir: Optional[str] = None) -> str:
    """Returns directory where external updated yt_dlp package is extracted."""
    root = base_dir if base_dir else get_app_data_dir()
    return os.path.join(root, "yt_dlp_plugin")


def get_core_plugin_dir(base_dir: Optional[str] = None) -> str:
    """Returns directory where external core patch package is installed."""
    root = base_dir if base_dir else get_app_data_dir()
    return os.path.join(root, "core_plugin")


def _is_trusted_update_url(url: str) -> bool:
    """Verifies that an update or patch URL originates from an authorized HTTPS repository domain."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() != "https":
            return False
        host = (parsed.hostname or "").lower()
        trusted_hosts = {
            "github.com",
            "api.github.com",
            "objects.githubusercontent.com",
            "raw.githubusercontent.com",
            "release-assets.githubusercontent.com",
            "codeload.github.com",
            "files.pythonhosted.org",
            "pypi.org",
        }
        if host in trusted_hosts or host.endswith(".githubusercontent.com") or host.endswith(".github.com"):
            return True
        return False
    except Exception:
        return False


def _get_ssl_context() -> ssl.SSLContext:
    """Creates an SSL context for HTTPS update checks with fallback if certs are missing."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _get_verified_ssl_context() -> ssl.SSLContext:
    """Creates a strictly verified SSL context for secure application updates."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    except Exception:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            return ctx
        except Exception:
            return ssl.create_default_context()
