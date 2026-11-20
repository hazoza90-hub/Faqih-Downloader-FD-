"""
session_store.py: PreviewSession dataclass, thread-safe session registry, pruning, and style assignment.
"""
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

_SESSIONS_LOCK = threading.Lock()
_SESSIONS: Dict[str, "PreviewSession"] = {}


@dataclass
class PreviewSession:
    """Stores all context and callbacks for an active media preview and configuration session."""
    sid: str
    url: str
    video_title: str
    info_dict: Dict[str, Any] = field(default_factory=dict); options: List[Any] = field(default_factory=list)
    audio_tracks: List[Dict[str, Any]] = field(default_factory=list); subtitle_tracks: List[Dict[str, Any]] = field(default_factory=list)
    default_dest_path: str = ""; on_confirm: Optional[Callable[[Any, str], None]] = None
    on_open_in_main: Optional[Callable[[Any, str], None]] = None; on_cancel: Optional[Callable[[], None]] = None
    parent_app: Optional[Any] = None; modal_ref: Optional[Any] = None; cached_subtitles: Dict[int, str] = field(default_factory=dict)
    selected_audio_track: Optional[Dict[str, Any]] = None; selected_sub_track: Optional[Dict[str, Any]] = None
    subtitle_embed_mode: str = "soft_embed"; selected_q_idx: int = 0
    subtitle_position: str = "bottom"; max_connections: int = 8; subtitle_preset: str = "youtube"
    subtitle_font_scale: float = 1.0; subtitle_text_color: str = "#FFFFFF"; subtitle_bg_mode: str = "box"
    subtitle_pos_x: float = 50.0; subtitle_pos_y: float = 86.0; clip_start: float = 0.0; clip_end: float = 0.0
    sub_custom_edits: Dict[str, str] = field(default_factory=dict); dual_sub: bool = False; sec_s_idx: int = -1
    audio_boost: bool = False; chapter_title: str = ""; chapters: List[Dict[str, Any]] = field(default_factory=list); external_subtitle_tracks: List[Dict[str, Any]] = field(default_factory=list)


def _prune_preview_sessions(sessions: dict, max_sessions: int = 15) -> None:
    """Prunes oldest preview sessions to keep memory usage strictly bounded."""
    if not isinstance(sessions, dict):
        return
    while len(sessions) > max_sessions:
        try:
            oldest_key = next(iter(sessions))
            del sessions[oldest_key]
        except (StopIteration, KeyError):
            break


def register_preview_session(
    url: str, video_title: str,
    info_dict: Optional[Dict[str, Any]] = None, options: Optional[List[Any]] = None,
    audio_tracks: Optional[List[Dict[str, Any]]] = None, subtitle_tracks: Optional[List[Dict[str, Any]]] = None,
    default_dest_path: str = "", on_confirm: Optional[Callable[[Any, str], None]] = None,
    on_open_in_main: Optional[Callable[[Any, str], None]] = None, on_cancel: Optional[Callable[[], None]] = None,
    parent_app: Optional[Any] = None, modal_ref: Optional[Any] = None, sid: Optional[str] = None,
    selected_audio_track: Optional[Dict[str, Any]] = None, selected_sub_track: Optional[Dict[str, Any]] = None,
    subtitle_embed_mode: str = "hard_burn", selected_q_idx: int = 0, subtitle_position: str = "bottom",
    subtitle_preset: str = "youtube", subtitle_font_scale: float = 1.0, subtitle_text_color: str = "#FFFFFF",
    subtitle_bg_mode: str = "box", subtitle_pos_x: float = 50.0, subtitle_pos_y: float = 86.0,
    **kwargs
) -> str:
    """Registers an active media preview session and returns its unique random session ID token."""
    from .bridge_server import start_preview_bridge
    start_preview_bridge()
    session_id = sid or uuid.uuid4().hex[:16]
    session = PreviewSession(
        sid=session_id, url=str(url or "").strip(), video_title=str(video_title or "Video Preview").strip(),
        info_dict=info_dict or {}, options=options or [], audio_tracks=audio_tracks or [],
        subtitle_tracks=subtitle_tracks or [], default_dest_path=str(default_dest_path or "").strip(),
        on_confirm=on_confirm, on_open_in_main=on_open_in_main, on_cancel=on_cancel, parent_app=parent_app,
        modal_ref=modal_ref, selected_audio_track=selected_audio_track, selected_sub_track=selected_sub_track,
        subtitle_embed_mode=subtitle_embed_mode or "hard_burn", selected_q_idx=selected_q_idx,
        subtitle_position=subtitle_position or "bottom", subtitle_preset=subtitle_preset or "youtube",
        subtitle_font_scale=float(subtitle_font_scale or 1.0), subtitle_text_color=str(subtitle_text_color or "#FFFFFF"),
        subtitle_bg_mode=str(subtitle_bg_mode or "box"), subtitle_pos_x=float(subtitle_pos_x or 50.0),
        subtitle_pos_y=float(subtitle_pos_y or 86.0), max_connections=int(kwargs.get("max_connections") or 8),
    )
    ch_list = kwargs.get("chapters")
    if not ch_list and (isinstance(info_dict, dict) or (info_dict is None and options)):
        try:
            from ..audio_and_chapters_engine import extract_video_chapters
            tot_d = float(info_dict.get("duration") or 0.0) if isinstance(info_dict, dict) else 0.0
            if tot_d <= 0 and options: tot_d = float(getattr(options[0], "duration", 0) or 0.0)
            ch_list = extract_video_chapters(info_dict or {}, tot_d, auto_split_if_empty=True)
        except Exception: ch_list = []
    session.chapters = list(ch_list or [])
    session.audio_boost = bool(kwargs.get("audio_boost", False))
    _init_ext = kwargs.get("external_subtitle_tracks") or (getattr(options[selected_q_idx], "external_subtitle_tracks", []) if (options and 0 <= selected_q_idx < len(options)) else [])
    session.chapter_title, session.external_subtitle_tracks = str(kwargs.get("chapter_title", "") or ""), list(_init_ext or [])
    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = session
        _prune_preview_sessions(_SESSIONS, 15)
    return session_id


def get_preview_session(sid: str) -> Optional[PreviewSession]:
    """Retrieves an active preview session by session ID."""
    with _SESSIONS_LOCK:
        return _SESSIONS.get(sid)


def unregister_preview_session(sid: str) -> None:
    """Removes a finished preview session."""
    with _SESSIONS_LOCK:
        _SESSIONS.pop(sid, None)


def _apply_session_sub_styles(opt: Any, session: PreviewSession) -> None:
    if not opt: return
    opt.subtitle_preset, opt.subtitle_font_scale = session.subtitle_preset, session.subtitle_font_scale
    opt.subtitle_text_color, opt.subtitle_bg_mode = session.subtitle_text_color, session.subtitle_bg_mode
    opt.subtitle_pos_x, opt.subtitle_pos_y = session.subtitle_pos_x, session.subtitle_pos_y
    st = getattr(opt, "selected_subtitle_track", None)
    if st and isinstance(st, dict):
        clean_st = {k: v for k, v in st.items() if k not in ("style_config", "secondary_track")}
        opt.selected_subtitle_track = clean_st
        sec_trk = getattr(session, "secondary_subtitle_track", None) or getattr(opt, "secondary_subtitle_track", None)
        clean_sec = {k: v for k, v in sec_trk.items() if k not in ("style_config", "secondary_track")} if isinstance(sec_trk, dict) else sec_trk
        clean_st["style_config"] = {
            "preset": session.subtitle_preset, "font_scale": session.subtitle_font_scale,
            "text_color": session.subtitle_text_color, "bg_mode": session.subtitle_bg_mode,
            "pos_x": session.subtitle_pos_x, "pos_y": session.subtitle_pos_y,
            "subtitle_position": session.subtitle_position, "secondary_track": clean_sec,
        }
        sub_trks = getattr(session, "subtitle_tracks", None)
        if isinstance(sub_trks, list):
            tid = clean_st.get("sub_id")
            for i, trk in enumerate(sub_trks):
                if isinstance(trk, dict) and tid and trk.get("sub_id") == tid:
                    sub_trks[i] = clean_st; break


__all__ = [
    "PreviewSession",
    "_SESSIONS_LOCK",
    "_SESSIONS",
    "_prune_preview_sessions",
    "register_preview_session",
    "get_preview_session",
    "unregister_preview_session",
    "_apply_session_sub_styles",
]
