"""
HTML document assembly for HTML5 preview player.
"""
from __future__ import annotations
import html
import json
from typing import Dict, List, Optional, Any
from ....config import get_setting
from ....services.youtube_models import extract_media_platform, format_filesize
from .player_css import _CSS
from .player_js import _JS_TEMPLATE
from .subtitle_studio_css import get_studio_css
from .subtitle_studio_html import get_studio_toolbar_html
from .subtitle_studio_js import get_studio_js
from .clipper_css import get_clipper_css
from .clipper_html import get_clipper_toolbar_html
from .clipper_js import get_clipper_js


def generate_preview_html(
    url: str, video_title: str, stream_url: Optional[str] = None, vtt_data_uri: Optional[str] = None,
    video_id: Optional[str] = None, sub_label: Optional[str] = None, quality_label: Optional[str] = None, sub_lang: str = "ar",
    dub_audio_url: Optional[str] = None, audio_label: Optional[str] = None, selected_audio_track: Optional[Dict[str, Any]] = None,
    audio_tracks: Optional[List[Dict[str, Any]]] = None, options: Optional[List[Any]] = None, subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
    default_dest_path: Optional[str] = None, sid: Optional[str] = None, bridge_port: Optional[int] = None, platform_name: Optional[str] = None,
    selected_sub_track: Optional[Dict[str, Any]] = None, subtitle_embed_mode: str = "hard_burn", selected_q_idx: int = 0,
    subtitle_position: str = "bottom", subtitle_preset: str = "youtube", subtitle_font_scale: float = 1.0,
    subtitle_text_color: str = "#FFFFFF", subtitle_bg_mode: str = "box", subtitle_pos_x: float = 50.0, subtitle_pos_y: float = 86.0,
    clip_start: float = 0.0, clip_end: float = 0.0, dual_sub: bool = False, **kwargs
) -> str:
    """Generates modern dark-themed HTML5 preview player with synchronized dubbing and controls."""
    safe_title = html.escape(video_title or "Video Preview")
    safe_stream = html.escape(stream_url or "")
    if options and 0 <= selected_q_idx < len(options):
        safe_quality = html.escape(getattr(options[selected_q_idx], "resolution_label", "") or "MP4 Stream")
    else:
        safe_quality = html.escape(quality_label or ("MP4 Stream" if stream_url else "Web Player"))

    platform = platform_name or extract_media_platform(url)
    safe_platform = html.escape(platform)

    sel_a_idx = 0
    if selected_audio_track and audio_tracks:
        for idx, trk in enumerate(audio_tracks):
            if trk == selected_audio_track or (trk.get("track_id") and trk.get("track_id") == selected_audio_track.get("track_id")):
                sel_a_idx = idx; break

    eff_dub = dub_audio_url
    eff_audio_lbl = audio_label
    if selected_audio_track and selected_audio_track.get("track_id") != "original":
        if not eff_dub: eff_dub = selected_audio_track.get("url")
        if not eff_audio_lbl: eff_audio_lbl = selected_audio_track.get("label") or selected_audio_track.get("language")
    if not eff_audio_lbl: eff_audio_lbl = "Original Audio"
    safe_audio_label = html.escape(eff_audio_lbl)

    sel_s_idx = 0
    if selected_sub_track and subtitle_tracks:
        for idx, trk in enumerate(subtitle_tracks):
            if trk == selected_sub_track or (trk.get("sub_id") and trk.get("sub_id") == selected_sub_track.get("sub_id")):
                sel_s_idx = idx; break

    safe_sub_label = html.escape(sub_label or "Subtitles")
    safe_sub_lang = html.escape((sub_lang or "ar").split("-")[0].split("_")[0])
    embed_src = f"https://www.youtube.com/embed/{video_id}?autoplay=1&cc_load_policy=1&cc_lang_pref={safe_sub_lang}&hl={safe_sub_lang}" if video_id else url
    bridge_base = f"http://127.0.0.1:{bridge_port}" if bridge_port else ""

    track_html = ""
    if vtt_data_uri:
        track_html = f'<track label="{safe_sub_label}" kind="subtitles" srclang="{safe_sub_lang}" src="{vtt_data_uri}" default id="vttTrack">'
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {safe_sub_label}</span>'
    elif sid and subtitle_tracks and 0 < sel_s_idx < len(subtitle_tracks):
        st = subtitle_tracks[sel_s_idx]
        lbl = html.escape(st.get("label") or st.get("language") or "Subtitles")
        sc = html.escape((st.get("language") or "ar").split("-")[0].split("_")[0])
        track_html = f'<track label="{lbl}" kind="subtitles" srclang="{sc}" src="{bridge_base}/subtitle.vtt?sid={sid}&s_idx={sel_s_idx}" default id="vttTrack">'
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {lbl}</span>'
    elif subtitle_tracks and len(subtitle_tracks) > 1 and sel_s_idx > 0:
        sub_badge = f'<span id="badgeSub" class="badge badge-sub">💬 {safe_sub_label}</span>'
    else:
        sub_badge = '<span id="badgeSub" class="badge badge-dim">💬 No Subtitles</span>'
    is_dub_audio = bool(eff_dub and safe_audio_label != "Original Audio")
    audio_badge = f'<span id="badgeAudio" class="badge {"badge-audio" if is_dub_audio else "badge-dim"}">🔊 {safe_audio_label}</span>'

    plat_low = platform.lower()
    plat_cls = "plat-generic"
    if "youtube" in plat_low: plat_cls = "plat-yt"
    elif "tiktok" in plat_low: plat_cls = "plat-tt"
    elif "instagram" in plat_low: plat_cls = "plat-ig"
    elif "twitter" in plat_low or "x" in plat_low: plat_cls = "plat-tw"
    elif "facebook" in plat_low: plat_cls = "plat-fb"

    settings_html = ""
    if options:
        rows = []
        for idx, opt in enumerate(options):
            r_l, r_e = html.escape(getattr(opt, "resolution_label", "Unknown")), html.escape(str(getattr(opt, "ext", "mp4")).upper())
            fps_val = getattr(opt, "fps", 0)
            r_f = str(fps_val) if isinstance(fps_val, (int, float)) and fps_val > 0 else "—"
            r_s, r_n = html.escape(format_filesize(getattr(opt, "filesize_approx", 0))), html.escape(getattr(opt, "note", ""))
            s_cls = "opt-row selected" if idx == selected_q_idx else "opt-row"
            rows.append(f'<tr class="{s_cls}" data-idx="{idx}" data-raw-size="{int(getattr(opt, "filesize_approx", 0) or 0)}" onclick="selectQualityRow({idx})"><td class="col-res"><strong>{r_l}</strong></td><td class="col-center">{r_e}</td><td class="col-right col-size">{r_s}</td><td class="col-center">{r_f}</td><td class="col-note">{r_n}</td></tr>')
        a_opts = [f'<option value="{i}"{" selected" if i == sel_a_idx else ""}>{html.escape(t.get("label") or t.get("language") or f"Audio #{i}")}</option>' for i, t in enumerate(audio_tracks or [])] or ['<option value="0">Original Audio (Default)</option>']
        s_opts = [f'<option value="{i}"{" selected" if i == sel_s_idx else ""}>{html.escape(t.get("label") or t.get("language") or f"Subtitle #{i}")}</option>' for i, t in enumerate(subtitle_tracks or [])] or ['<option value="0">No Subtitles</option>']
        m_opts = [f'<option value="soft_embed"{" selected" if subtitle_embed_mode == "soft_embed" else ""}>دمج ناعم (Soft Embed)</option>', f'<option value="hard_burn"{" selected" if subtitle_embed_mode == "hard_burn" else ""}>حرق دائم (Burn-in)</option>']
        max_conn = int(kwargs.get("max_connections") or get_setting("max_connections", 8))
        c_opts = [f'<option value="{c}"{" selected" if max_conn == c else ""}>{c} {"Track (مسار)" if c == 1 else "Tracks (مسارات)"}</option>' for c in [1, 2, 4, 8, 16, 32]]
        safe_dst = html.escape(default_dest_path or "")
        raw_ext = kwargs.get("external_subtitle_tracks")
        if raw_ext is None and options and 0 <= selected_q_idx < len(options):
            raw_ext = getattr(options[selected_q_idx], "external_subtitle_tracks", None)
        sel_ext_ids = {str(t.get("sub_id")).strip().lower() for t in (raw_ext or []) if isinstance(t, dict) and t.get("sub_id") and str(t.get("sub_id")).lower() != "none"}
        sel_ext_langs = {str(t.get("language")).strip().lower() for t in (raw_ext or []) if isinstance(t, dict) and not t.get("sub_id") and t.get("language") and str(t.get("language")).lower() != "none"}
        ext_items = ['<div class="ext-srt-clear" onclick="clearExtSrt(event)">✕ بدون ملفات خارجية (مسح الكل / Clear All)</div>']
        init_codes, init_cnt = [], 0
        for i, t in enumerate(subtitle_tracks or []):
            if not isinstance(t, dict): continue
            sid_val = str(t.get("sub_id") or "").strip()
            lng_val = str(t.get("language") or "").strip()
            if sid_val.lower() == "none" or lng_val.lower() == "none" or (i == 0 and not t.get("url") and not sid_val): continue
            eff_id = sid_val or lng_val or f"s{i}"
            code = (lng_val or eff_id).split("-")[0].split("_")[0].upper() or f"S{i}"
            is_chk = (eff_id.lower() in sel_ext_ids) or (lng_val.lower() in sel_ext_langs)
            if is_chk:
                init_cnt += 1
                if code not in init_codes: init_codes.append(code)
            ext_items.append(f'<label class="ext-srt-item" onclick="event.stopPropagation()"><input type="checkbox" class="ext-srt-cb" value="{i}" data-lang="{html.escape(code)}" data-subid="{html.escape(eff_id)}"{" checked" if is_chk else ""} onchange="onExtSrtChange(event)"><span>{html.escape(t.get("label") or lng_val or f"Subtitle #{i}")}</span></label>')
        init_ext_lbl = (f"{', '.join(init_codes[:3])}{'..' if len(init_codes) > 3 else ''} ({init_cnt})" if init_cnt > 0 else "بدون (0)")
        mode_dis = " disabled" if sel_s_idx <= 0 else ""
        ext_srt_ctrl = f'<div class="ctrl-group ext-srt-wrap"><label>📄 Ext SRT / ملفات خارجية</label><button type="button" id="extSrtBtn" class="{"has-sel" if init_cnt > 0 else ""}" onclick="toggleExtSrtDropdown(event)"><span id="extSrtBtnText">{html.escape(init_ext_lbl)}</span><span>▾</span></button><div id="extSrtDropdown" onclick="event.stopPropagation()">{"".join(ext_items)}</div></div>'
        clipper_toolbar = get_clipper_toolbar_html(clip_start=clip_start, clip_end=clip_end, dual_sub=dual_sub, audio_boost=bool(kwargs.get("audio_boost", False)), chapters=kwargs.get("chapters", None))
        studio_toolbar = get_studio_toolbar_html(preset=subtitle_preset, scale=subtitle_font_scale, color=subtitle_text_color, bg_mode=subtitle_bg_mode, pos_x=subtitle_pos_x, pos_y=subtitle_pos_y)
        settings_html = f"""<div class="settings-panel"><div class="settings-header"><span class="settings-title">⚡ Download Quality &amp; Controls</span><span class="settings-count">{len(options)} Formats Detected</span></div><div class="table-container"><table class="format-table"><thead><tr><th>Resolution / Quality</th><th class="col-center">Format</th><th class="col-right">Est. Size</th><th class="col-center">FPS</th><th>Stream Details</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="controls-row"><div class="ctrl-group"><label>🔊 Audio / الدبلجة</label><select id="audioSelect" onchange="onAudioChange()">{"".join(a_opts)}</select></div><div class="ctrl-group"><label>💬 Subtitles / الترجمة</label><select id="subSelect" onchange="onSubChange()">{"".join(s_opts)}</select></div><div class="ctrl-group"><label>⚙️ Mode / الطريقة</label><select id="modeSelect" onchange="onModeChange()"{mode_dis}>{"".join(m_opts)}</select></div>{ext_srt_ctrl}<div class="ctrl-group"><label>⚡ Threads / المسارات</label><select id="connSelect" onchange="onConnChange()">{"".join(c_opts)}</select></div></div>{clipper_toolbar}{studio_toolbar}<div class="dest-card"><label>📁 Save As / مسار الحفظ:</label><input type="text" id="destInput" value="{safe_dst}" /><button type="button" class="btn" style="padding:4px 8px;font-size:11px;" onclick="browseDestination()">📁 Browse...</button></div><div class="action-bar"><button class="btn btn-download" onclick="doAction('download')">⚡ Download Selected Quality</button><button class="btn btn-secondary" onclick="doAction('open_in_main')">🖥️ Open in Main Window</button><button class="btn btn-cancel" onclick="doAction('cancel')">✕ Cancel</button></div></div>"""

    opt_needs_audio = [bool(not getattr(o, "is_progressive", False) and not getattr(o, "is_audio_only", False) and getattr(o, "audio_url", None)) for o in (options or [])]
    safe_tracks = [{k: v for k, v in t.items() if (isinstance(v, (str, int, float, bool)) or v is None) and k not in ("style_config", "secondary_track")} for t in (subtitle_tracks or []) if isinstance(t, dict)]
    _j = lambda v: json.dumps(v).replace("</", "<\\/")
    safe_embed_src = html.escape(embed_src or "", quote=True)
    js_code = _JS_TEMPLATE
    for tok, val in (
        ("__HAS_STREAM__", "true" if stream_url else "false"), ("__EMBED_SRC__", _j(embed_src)), ("__DUB_URL__", _j(eff_dub or "")),
        ("__SID__", _j(sid or "")), ("__AUDIO_TRACKS__", _j(audio_tracks or [])), ("__SUBTITLE_TRACKS__", _j(safe_tracks)),
        ("__EFFECTIVE_AUDIO_LABEL__", _j(eff_audio_lbl)), ("__BRIDGE_BASE__", _j(bridge_base)), ("__SELECTED_Q_IDX__", _j(selected_q_idx)),
        ("__OPT_NEEDS_AUDIO__", _j(opt_needs_audio)), ("__SUB_PRESET__", _j(subtitle_preset or "youtube")),
        ("__SUB_SCALE__", str(float(subtitle_font_scale or 1.0))), ("__SUB_COLOR__", _j(subtitle_text_color or "#FFFFFF")),
        ("__SUB_BG__", _j(subtitle_bg_mode or "box")), ("__SUB_PX__", str(float(subtitle_pos_x or 50.0))),
        ("__SUB_PY__", str(float(subtitle_pos_y or 86.0))), ("__SEL_S_IDX__", str(sel_s_idx)), ("__VTT_URI__", _j(vtt_data_uri or "")),
        ("__STUDIO_JS__", get_studio_js()), ("__CLIPPER_JS__", get_clipper_js()), ("__CLIP_START__", str(float(clip_start or 0.0))),
        ("__CLIP_END__", str(float(clip_end or 0.0))), ("__DUAL_SUB__", "true" if dual_sub else "false"),
        ("__AUDIO_BOOST__", "true" if kwargs.get("audio_boost") else "false"), ("__CHAPTER_TITLE__", _j(str(kwargs.get("chapter_title", "") or ""))),
    ):
        js_code = js_code.replace(tok, val)
    player_flex = "52 1 0" if options else "1"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{safe_title} — Faqih Downloader Preview</title><style>
{_CSS}
{get_studio_css()}
{get_clipper_css()}
    .player-container {{ flex: {player_flex}; }}
    </style></head><body>
    <div class="header"><div class="title-group"><span class="badge {plat_cls}">📺 {safe_platform}</span><span id="badgeRes" class="badge badge-res">🎞️ {safe_quality}</span>{audio_badge}{sub_badge}<span class="title" title="{safe_title}">🎬 {safe_title}</span></div>
        <div class="actions"><div style="display:flex;align-items:center;gap:6px;"><button id="muteBtn" class="btn" style="padding:4px 8px;" title="Mute / Unmute">🔊</button><input type="range" id="volSlider" min="0" max="1" step="0.05" value="1" style="width:65px;accent-color:#38bdf8;cursor:pointer;" title="Volume"></div><button id="toggleBtn" class="btn" onclick="togglePlayer()">🌐 Switch to Web Player</button></div></div>
    <div class="player-container" id="playerContainer"><video id="videoEl" src="{safe_stream}" controls autoplay playsinline style="display: {'block' if stream_url else 'none'};">{track_html}</video><div id="liveSubOverlay" class="live-sub-overlay"></div><div id="centerGuideLine" class="center-guide-line"></div><audio id="dubAudioEl" preload="auto" style="display: none;"></audio><iframe id="iframeEl" src="{'about:blank' if stream_url else safe_embed_src}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen style="display: {'none' if stream_url else 'block'};"></iframe></div>
    {settings_html}<script>
{js_code}
    </script></body></html>"""

__all__ = ["generate_preview_html"]
