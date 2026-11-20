"""
Backward-compatibility shim for preview_html_builder.
Re-exports _CSS, _JS_TEMPLATE, and generate_preview_html from ui.modals.preview.
"""
from .preview.player_css import _CSS
from .preview.player_js import _JS_TEMPLATE
from .preview.player_html import generate_preview_html

__all__ = [
    "_CSS",
    "_JS_TEMPLATE",
    "generate_preview_html",
]
