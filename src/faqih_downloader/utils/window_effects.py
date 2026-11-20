"""
Backward-compatibility shim for window effects.
Re-exports functionality from faqih_downloader.utils.effects.*
"""
from .effects import (
    enable_dark_titlebar,
    apply_acrylic_or_mica_effect,
    apply_window_opacity,
    draw_rounded_rect,
    draw_glow_border,
    _BaseCanvas,
    RoundedGlassCard,
)

__all__ = [
    "enable_dark_titlebar",
    "apply_acrylic_or_mica_effect",
    "apply_window_opacity",
    "draw_rounded_rect",
    "draw_glow_border",
    "_BaseCanvas",
    "RoundedGlassCard",
]
