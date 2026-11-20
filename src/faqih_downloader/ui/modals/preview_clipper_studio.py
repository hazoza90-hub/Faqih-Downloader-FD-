"""
preview_clipper_studio.py: Thin backward-compatibility shim re-exporting symbols from ui.modals.preview.
"""
from .preview.clipper_css import get_clipper_css
from .preview.clipper_html import get_clipper_toolbar_html
from .preview.clipper_js import get_clipper_js

__all__ = [
    "get_clipper_css",
    "get_clipper_toolbar_html",
    "get_clipper_js",
]
