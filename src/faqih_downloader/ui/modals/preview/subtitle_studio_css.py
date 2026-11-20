"""
subtitle_studio_css.py: CSS rules for the live draggable subtitle overlay and styling studio bar.
"""
from __future__ import annotations


def get_studio_css() -> str:
    """Returns CSS rules for the live draggable subtitle overlay and styling studio bar."""
    return """
video::cue, ::cue,
video::-webkit-media-text-track-container,
video::-webkit-media-text-track-display,
video::-webkit-media-text-track-region {
    opacity: 0 !important; display: none !important; color: transparent !important;
    background: transparent !important; text-shadow: none !important;
}
.live-sub-overlay {
    position: absolute; left: 50%; top: 86%; transform: translate(-50%, -50%);
    z-index: 25; pointer-events: auto; cursor: grab; user-select: none;
    text-align: center; direction: rtl; white-space: pre-line;
    max-width: 90%; max-height: 40%; overflow: hidden; line-height: 1.35;
    box-sizing: border-box; display: none; transition: box-shadow 0.15s ease;
}
.live-sub-overlay:active { cursor: grabbing; }
.live-sub-overlay.dragging { box-shadow: 0 0 0 2px #38bdf8, 0 6px 20px rgba(0,0,0,0.8); opacity: 0.95; }
.center-guide-line {
    position: absolute; top: 0; bottom: 0; left: 50%; width: 1px;
    background: rgba(56, 189, 248, 0.5); z-index: 20; pointer-events: none; display: none;
}
.sub-preset-youtube {
    background: rgba(0, 0, 0, 0.68) !important; color: #ffffff !important;
    font-weight: 700; font-family: Arial, "Segoe UI", Tahoma, sans-serif;
    padding: 6px 14px; border-radius: 6px; text-shadow: none !important;
}
.sub-preset-tiktok {
    background: transparent !important; color: #ffffff !important;
    font-weight: 900; font-family: Arial, "Segoe UI", Tahoma, sans-serif;
    padding: 4px 8px; border-radius: 0;
    text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 3px 6px rgba(0,0,0,0.9) !important;
}
.sub-preset-golden {
    background: rgba(0, 0, 0, 0.68) !important; color: #ffd700 !important;
    font-weight: 700; font-family: Arial, "Segoe UI", Tahoma, sans-serif;
    padding: 6px 14px; border-radius: 6px; text-shadow: 0 1px 3px rgba(0,0,0,0.8) !important;
}
.sub-preset-custom-box {
    background: rgba(0, 0, 0, 0.68) !important; font-weight: 700;
    font-family: Arial, "Segoe UI", Tahoma, sans-serif; padding: 6px 14px; border-radius: 6px; text-shadow: none !important;
}
.sub-preset-custom-outline {
    background: transparent !important; font-weight: 900; font-family: Arial, "Segoe UI", Tahoma, sans-serif;
    padding: 4px 8px; border-radius: 0;
    text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000 !important;
}
.sub-studio-bar {
    display: flex; flex-wrap: wrap; align-items: center; background: #131d31;
    border: 1px solid #1e293b; border-radius: 6px; padding: 4px 10px; gap: 8px; font-size: 11px;
}
.sub-studio-group { display: flex; align-items: center; gap: 5px; }
.sub-studio-group label { font-weight: 600; color: #94a3b8; white-space: nowrap; }
.studio-btn-pill {
    background: #1e293b; color: #cbd5e1; border: 1px solid #334155;
    padding: 2px 7px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 600;
    transition: all 0.1s ease;
}
.studio-btn-pill:hover { background: #334155; color: #fff; }
.studio-btn-pill.active { background: #0284c7; color: #fff; border-color: #38bdf8; }
.color-dot {
    width: 14px; height: 14px; border-radius: 50%; cursor: pointer; border: 1px solid #475569; display: inline-block;
}
.color-dot.active { border-color: #38bdf8; box-shadow: 0 0 0 2px #38bdf8; }
""".strip()


__all__ = ["get_studio_css"]
