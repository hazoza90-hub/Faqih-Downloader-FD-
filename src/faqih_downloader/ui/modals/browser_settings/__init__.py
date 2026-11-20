"""
browser_settings package: Browser integration dialog, status indicators, and extension installation sections.
"""
from .status_section import build_status_section
from .capture_settings_section import build_capture_settings_section
from .extension_section import build_extension_section
from .modal import BrowserSettingsModalMixin

__all__ = [
    "build_status_section",
    "build_capture_settings_section",
    "build_extension_section",
    "BrowserSettingsModalMixin",
]
