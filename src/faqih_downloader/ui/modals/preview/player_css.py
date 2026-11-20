"""
CSS styles for HTML5 preview player.
"""

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #090d16; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; user-select: none; }
.header { background: #131a29; height: 50px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #1e293b; flex-shrink: 0; gap: 10px; }
.title-group { display: flex; align-items: center; gap: 8px; overflow: hidden; flex: 1; }
.title { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #f8fafc; }
.badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px; white-space: nowrap; }
.badge-res { background: #0284c7; color: #fff; } .badge-sub { background: #059669; color: #fff; } .badge-audio { background: #8b5cf6; color: #fff; } .badge-dim { background: #334155; color: #94a3b8; }
.plat-yt { background: #ef4444; color: #fff; } .plat-tt { background: #ec4899; color: #fff; } .plat-ig { background: #a855f7; color: #fff; } .plat-tw { background: #38bdf8; color: #0f172a; font-weight: bold; } .plat-fb { background: #2563eb; color: #fff; } .plat-generic { background: #475569; color: #fff; }
.actions { display: flex; align-items: center; gap: 8px; }
.btn { background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; white-space: nowrap; }
.btn:hover { background: #0284c7; color: #fff; border-color: #0284c7; }
.player-container { flex: 52 1 0; min-height: 200px; position: relative; background: #000; display: flex; align-items: center; justify-content: center; overflow: hidden; }
video, iframe { width: 100%; height: 100%; border: none; outline: none; background: #000; }
video::cue, ::cue, video::-webkit-media-text-track-container, video::-webkit-media-text-track-display, video::-webkit-media-text-track-region { opacity: 0 !important; display: none !important; color: transparent !important; background: transparent !important; text-shadow: none !important; }
.settings-panel { flex: 48 1 0; min-height: 200px; background: #0f172a; border-top: 1px solid #1e293b; padding: 6px 14px; display: flex; flex-direction: column; overflow-y: auto; gap: 5px; }
.settings-header { display: flex; justify-content: space-between; align-items: center; }
.settings-title { font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; } .settings-count { font-size: 11px; color: #94a3b8; }
.table-container { max-height: 82px; overflow-y: auto; background: #131d31; border: 1px solid #1e293b; border-radius: 6px; }
.format-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
.format-table th { background: #17233c; color: #94a3b8; padding: 5px 10px; font-weight: 600; position: sticky; top: 0; border-bottom: 1px solid #1e293b; }
.format-table td { padding: 4px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
.opt-row { cursor: pointer; transition: background 0.1s ease; } .opt-row:hover { background: #1e293b; } .opt-row.selected { background: #0284c7; color: #fff; } .opt-row.selected td { color: #fff; }
.col-center { text-align: center; } .col-right { text-align: right; } .col-note { color: #94a3b8; font-size: 11px; } .opt-row.selected .col-note { color: #e0f2fe; }
.controls-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
.ctrl-group { display: flex; flex-direction: column; gap: 2px; position: relative; } .ctrl-group label { font-size: 11px; font-weight: 600; color: #94a3b8; }
.ctrl-group select { background: #17233c; color: #f8fafc; border: 1px solid #334155; padding: 4px 8px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; }
.ctrl-group select:disabled { opacity: 0.48; cursor: not-allowed; }
.ext-srt-wrap { position: relative; } #extSrtBtn { background: #17233c; color: #f8fafc; border: 1px solid #334155; padding: 4px 8px; border-radius: 6px; font-size: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 6px; width: 100%; }
#extSrtBtn.has-sel { border-color: #38bdf8; color: #38bdf8; font-weight: 700; }
#extSrtDropdown { display: none; position: absolute; top: 100%; left: 0; min-width: 235px; max-height: 195px; overflow-y: auto; background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; padding: 4px; z-index: 1000; box-shadow: 0 10px 25px rgba(0,0,0,0.65); margin-top: 3px; }
#extSrtDropdown.open { display: block; }
.ext-srt-clear { padding: 5px 8px; font-size: 11px; color: #f87171; cursor: pointer; border-bottom: 1px solid #1e293b; margin-bottom: 3px; border-radius: 4px; font-weight: 600; } .ext-srt-clear:hover { background: #1e293b; }
.ext-srt-item { display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 12px; color: #e2e8f0; cursor: pointer; border-radius: 4px; user-select: none; } .ext-srt-item:hover { background: #1e293b; }
.ext-srt-item input { cursor: pointer; accent-color: #38bdf8; margin: 0; }
.dest-card { display: flex; align-items: center; background: #17233c; border: 1px solid #334155; padding: 4px 10px; border-radius: 6px; gap: 8px; }
.dest-card label { font-size: 11px; font-weight: 600; color: #94a3b8; white-space: nowrap; } .dest-card input { background: transparent; color: #f8fafc; border: none; outline: none; font-size: 12px; flex: 1; }
.action-bar { display: flex; align-items: center; gap: 10px; margin-top: 2px; position: sticky; bottom: 0; background: #0f172a; padding-top: 4px; z-index: 10; }
.btn-download { background: #059669; color: #fff; border: none; padding: 7px 15px; font-size: 12px; font-weight: 700; border-radius: 6px; cursor: pointer; } .btn-download:hover { background: #047857; }
.btn-secondary { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 7px 13px; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; } .btn-secondary:hover { background: #334155; }
.btn-cancel { background: transparent; color: #94a3b8; border: 1px solid #334155; padding: 7px 13px; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; margin-left: auto; } .btn-cancel:hover { background: #334155; color: #fff; }
""".strip()

__all__ = ["_CSS"]
