"""
Window effects and rounded canvas styling subpackage for Faqih Downloader:
- dwm_effects: Native Windows 10/11 Acrylic, Mica, and dark titlebar integration
- canvas_shapes: Smooth rounded rectangle and glowing border drawing helpers
- glass_card: Rounded frosted glass Canvas card container
"""
from .dwm_effects import (
    enable_dark_titlebar,
    apply_acrylic_or_mica_effect,
    apply_window_opacity,
)
from .canvas_shapes import (
    draw_rounded_rect,
    draw_glow_border,
)
from .glass_card import (
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
