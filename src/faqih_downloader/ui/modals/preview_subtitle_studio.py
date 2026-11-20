"""
preview_subtitle_studio.py: Thin backward-compatibility shim re-exporting symbols from ui.modals.preview.
"""
from .preview.subtitle_studio_css import get_studio_css
from .preview.subtitle_studio_html import get_studio_toolbar_html
from .preview.subtitle_studio_js import get_studio_js

__all__ = [
    "get_studio_css",
    "get_studio_toolbar_html",
    "get_studio_js",
]
