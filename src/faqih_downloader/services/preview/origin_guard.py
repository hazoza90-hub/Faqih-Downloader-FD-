"""
origin_guard.py: Safe integer parsing and localhost origin CSRF validation for preview bridge.
"""
from typing import Any


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely converts value to int, returning default on ValueError or TypeError."""
    try:
        if val is None:
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _is_preview_origin_allowed(origin: str) -> bool:
    """Validates that origin is empty (non-browser) or local (127.0.0.1 or localhost)."""
    if not origin:
        return True
    origin = origin.strip().lower()
    if origin.startswith(("http://", "https://")):
        return (
            origin.startswith("http://127.0.0.1")
            or origin.startswith("https://127.0.0.1")
            or origin.startswith("http://localhost")
            or origin.startswith("https://localhost")
        )
    return False


__all__ = [
    "_safe_int",
    "_is_preview_origin_allowed",
]
