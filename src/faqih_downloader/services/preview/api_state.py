"""
api_state.py: Preview HTTP API mixin synchronizing live web player selections back to Tkinter modal.
"""
import sys
from typing import Dict, Any

from .origin_guard import _safe_int
from .session_store import PreviewSession, _apply_session_sub_styles
from .tk_dispatch import _schedule_on_tk


class PreviewStateApiMixin:
    """Handles /api/sync_state endpoint."""

    def _handle_api_sync_state(self, session: PreviewSession, body: Dict[str, Any]) -> None:
        """Synchronizes format, dubbed audio, subtitle, and mode selections live to Tkinter modal."""
        q_idx, a_idx, s_idx = _safe_int(body.get("q_idx", 0)), _safe_int(body.get("a_idx", 0)), _safe_int(body.get("s_idx", 0))
        sub_mode, sub_pos = str(body.get("sub_mode", "hard_burn")), str(body.get("sub_pos", "bottom"))
        dest_path = str(body.get("dest_path", "")).strip()
        max_conn = _safe_int(body.get("max_connections", 0))
        if max_conn in (1, 2, 4, 8, 16, 24, 32): session.max_connections = max_conn

        session.selected_q_idx, session.subtitle_position, session.subtitle_embed_mode = q_idx, sub_pos, sub_mode
        session.subtitle_preset, session.subtitle_font_scale = str(body.get("sub_preset", session.subtitle_preset or "youtube")), float(body.get("sub_scale", session.subtitle_font_scale or 1.0))
        session.subtitle_text_color, session.subtitle_bg_mode, session.subtitle_pos_x, session.subtitle_pos_y = str(body.get("sub_color", session.subtitle_text_color or "#FFFFFF")), str(body.get("sub_bg_mode", session.subtitle_bg_mode or "box")), float(body.get("sub_pos_x", session.subtitle_pos_x or 50.0)), float(body.get("sub_pos_y", session.subtitle_pos_y or 86.0))
        if dest_path: session.default_dest_path = dest_path

        if session.audio_tracks and 0 <= a_idx < len(session.audio_tracks): session.selected_audio_track = session.audio_tracks[a_idx]
        session.selected_sub_track = session.subtitle_tracks[s_idx] if (session.subtitle_tracks and 0 < s_idx < len(session.subtitle_tracks)) else None

        cur_opt = session.options[q_idx] if (session.options and 0 <= q_idx < len(session.options)) else None
        if cur_opt:
            cur_opt.selected_audio_track, cur_opt.selected_subtitle_track = session.selected_audio_track, session.selected_sub_track
            cur_opt.subtitle_embed_mode, cur_opt.subtitle_position = session.subtitle_embed_mode, session.subtitle_position
            _apply_session_sub_styles(cur_opt, session)
        from ..media_clipper_engine import sync_clipper_state_from_body
        sync_clipper_state_from_body(session, body, cur_opt)
        if cur_opt: session.selected_sub_track = cur_opt.selected_subtitle_track

        try:
            from ...config import set_setting
            set_setting("subtitle_embed_mode", sub_mode); set_setting("subtitle_position", sub_pos)
            if getattr(session, "max_connections", 0) > 0:
                set_setting("max_connections", session.max_connections)
                if cur_opt: cur_opt.max_connections = session.max_connections
            if cur_opt: set_setting("preferred_video_height", -1 if getattr(cur_opt, "is_audio_only", False) else getattr(cur_opt, "height", 0))
            if session.selected_audio_track: set_setting("preferred_audio_lang", session.selected_audio_track.get("language") or "original")
            if session.selected_sub_track: set_setting("preferred_subtitle_lang", session.selected_sub_track.get("language") or "none")
        except Exception: pass

        def _sync_tk():
            if session.parent_app and hasattr(session.parent_app, "set_main_external_subtitles"):
                try: session.parent_app.set_main_external_subtitles(getattr(session, "external_subtitle_tracks", []) or [], sync_state=True)
                except Exception: pass
            m = session.modal_ref
            if not m or (hasattr(m, "winfo_exists") and not m.winfo_exists()): return
            try:
                iid = f"opt_{q_idx}"
                if hasattr(m, "tree") and m.tree: m.tree.selection_set(iid); m.tree.focus(iid); m.tree.see(iid)
                if hasattr(m, "options") and 0 <= q_idx < len(m.options):
                    so = m.selected_option = m.options[q_idx]
                    so.selected_audio_track, so.selected_subtitle_track = session.selected_audio_track, session.selected_sub_track
                    so.subtitle_embed_mode, so.subtitle_position, so.subtitle_preset, so.subtitle_font_scale = session.subtitle_embed_mode, session.subtitle_position, session.subtitle_preset, session.subtitle_font_scale
                    so.subtitle_text_color, so.subtitle_bg_mode, so.subtitle_pos_x, so.subtitle_pos_y = session.subtitle_text_color, session.subtitle_bg_mode, session.subtitle_pos_x, session.subtitle_pos_y
                    so.external_subtitle_tracks = list(getattr(session, "external_subtitle_tracks", []) or [])
                    if getattr(session, "max_connections", 0) > 0: so.max_connections = session.max_connections
                if hasattr(m, "cb_audio") and m.cb_audio: m.cb_audio.current(a_idx)
                if hasattr(m, "cb_sub") and m.cb_sub:
                    m.cb_sub.current(s_idx); m.cb_sub._selected_mode, m.cb_sub._user_touched_mode, m.cb_sub._selected_pos = sub_mode, True, sub_pos
                    if hasattr(m.cb_sub, "set_external_subtitle_tracks"): m.cb_sub.set_external_subtitle_tracks(getattr(session, "external_subtitle_tracks", []) or [], notify=False)
                    if hasattr(m.cb_sub, "_mode_var"): m.cb_sub._mode_var.set(sub_mode)
                    mode_cb = getattr(m.cb_sub, "_mode_combobox", None)
                    if mode_cb and hasattr(mode_cb, "current"):
                        codes = getattr(m.cb_sub, "_mode_codes", ["soft_embed", "hard_burn"])
                        if sub_mode in codes: mode_cb.current(codes.index(sub_mode))
                        if hasattr(mode_cb, "configure"): mode_cb.configure(state="readonly" if s_idx > 0 else "disabled")
                    conn_cb = getattr(m.cb_sub, "_conn_combobox", None) or getattr(m.cb_sub, "_pos_combobox", None)
                    smc = str(getattr(session, "max_connections", "")).strip()
                    if smc.isdigit() and int(smc) > 0:
                        m.cb_sub._selected_connections = int(smc)
                        if conn_cb and hasattr(conn_cb, "set"): conn_cb.set(smc)
                    elif conn_cb and hasattr(conn_cb, "current") and sub_pos in ["bottom", "middle", "top"]:
                        vals = getattr(conn_cb, "cget", lambda k: [])("values") if hasattr(conn_cb, "cget") else []
                        if any("bottom" in str(v).lower() or "أسفل" in str(v) for v in vals):
                            conn_cb.current(["bottom", "middle", "top"].index(sub_pos))
                if dest_path and hasattr(m, "entry_dest") and m.entry_dest:
                    m.entry_dest.delete(0, "end"); m.entry_dest.insert(0, dest_path)
                    if hasattr(m, "dest_path"): m.dest_path = dest_path
                if session.parent_app and getattr(session, "max_connections", 0) > 0:
                    if hasattr(session.parent_app, "conn_var"):
                        try: session.parent_app.conn_var.set(str(session.max_connections))
                        except Exception: pass
                    if hasattr(session.parent_app, "cb_main_sub_pos") and session.parent_app.cb_main_sub_pos:
                        try:
                            session.parent_app.cb_main_sub_pos.set(str(session.max_connections))
                            if hasattr(session.parent_app, "_sync_media_bar_state"): session.parent_app._sync_media_bar_state()
                        except Exception: pass
            except Exception: pass

        bridge_mod = sys.modules.get("faqih_downloader.services.preview_stream_bridge")
        sched_fn = getattr(bridge_mod, "_schedule_on_tk", _schedule_on_tk) if bridge_mod else _schedule_on_tk
        sched_fn(session, _sync_tk, 0)
        self._send_json({"status": "ok"})


__all__ = ["PreviewStateApiMixin"]
