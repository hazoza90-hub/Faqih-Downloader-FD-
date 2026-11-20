"""
clipper_css.py: CSS styles for the live clipper bar, subtitle editor modal, and dual subtitles.
"""
from __future__ import annotations


def get_clipper_css() -> str:
    """Returns CSS rules for the live clipper bar, text editor modal, and dual subtitles."""
    return """
.clipper-bar {
    display: flex; flex-wrap: wrap; align-items: center; background: #131d31;
    border: 1px solid #1e293b; border-radius: 6px; padding: 4px 10px; gap: 8px; font-size: 11px;
}
.clipper-group { display: flex; align-items: center; gap: 5px; }
.clipper-group label { font-weight: 600; color: #94a3b8; white-space: nowrap; }
.clipper-input {
    width: 58px; background: #17233c; color: #38bdf8; border: 1px solid #334155;
    padding: 2px 4px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; outline: none;
}
.clipper-input:focus { border-color: #38bdf8; box-shadow: 0 0 0 1px #38bdf8; }
.sub-edit-modal {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.85); padding: 12px 14px; z-index: 9999;
    width: 88%; max-width: 460px; display: flex; flex-direction: column; gap: 8px;
    box-sizing: border-box;
}
.sub-edit-header { display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 700; color: #38bdf8; }
.sub-edit-textarea {
    width: 100%; min-height: 60px; background: #17233c; color: #f8fafc;
    border: 1px solid #334155; border-radius: 5px; padding: 6px 8px; font-size: 13px;
    line-height: 1.4; outline: none; resize: vertical; box-sizing: border-box; font-family: inherit;
}
.sub-edit-textarea:focus { border-color: #38bdf8; }
.sub-edit-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dual-sub-secondary {
    display: block; font-size: 0.78em; color: #e2e8f0; opacity: 0.92;
    margin-top: 3px; font-weight: 500; letter-spacing: 0.2px; text-shadow: 0 1px 2px rgba(0,0,0,0.8);
    direction: ltr; unicode-bidi: plaintext; text-align: center;
}
.primary-sub-line { display: block; unicode-bidi: plaintext; text-align: center; }
""".strip()


__all__ = ["get_clipper_css"]
