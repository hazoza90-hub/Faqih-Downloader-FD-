"""
api_actions.py: Preview HTTP API mixin handling download, open-in-main, and cancel actions.
"""
import sys
from typing import Dict, Any

from ...utils.file_ops import apply_media_filename_tags, generate_unique_destination_path
from .origin_guard import _safe_int
from .session_store import PreviewSession, _apply_session_sub_styles, unregister_preview_session
from .tk_dispatch import _schedule_on_tk


class PreviewActionApiMixin:
    """Handles /api/action endpoint and dispatches confirmed preview actions to Tkinter."""

    def _handle_api_action(self, session: PreviewSession, body: Dict[str, Any]) -> None:
        """Processes download, open in main window, or cancel actions and dispatches safely to Tkinter."""
        action = str(body.get("action", "download"))
        q_idx, a_idx, s_idx = _safe_int(body.get("q_idx", 0)), _safe_int(body.get("a_idx", 0)), _safe_int(body.get("s_idx", 0))
        sub_mode, sub_pos = str(body.get("sub_mode", "hard_burn")), str(body.get("sub_pos", "bottom"))
        dest_path = str(body.get("dest_path", "")).strip()
        max_conn = _safe_int(body.get("max_connections", 0))
        if max_conn in (1, 2, 4, 8, 16, 24, 32): session.max_connections = max_conn

        session.selected_q_idx, session.subtitle_position, session.subtitle_embed_mode = q_idx, sub_pos, sub_mode
        session.subtitle_preset, session.subtitle_font_scale = str(body.get("sub_preset", session.subtitle_preset or "youtube")), float(body.get("sub_scale", session.subtitle_font_scale or 1.0))
        session.subtitle_text_color, session.subtitle_bg_mode, session.subtitle_pos_x, session.subtitle_pos_y = str(body.get("sub_color", session.subtitle_text_color or "#FFFFFF")), str(body.get("sub_bg_mode", session.subtitle_bg_mode or "box")), float(body.get("sub_pos_x", session.subtitle_pos_x or 50.0)), float(body.get("sub_pos_y", session.subtitle_pos_y or 86.0))

        selected_opt = session.options[q_idx] if 0 <= q_idx < len(session.options) else (session.options[0] if session.options else None)
        if selected_opt:
            if session.audio_tracks and 0 <= a_idx < len(session.audio_tracks):
                selected_opt.selected_audio_track = session.audio_tracks[a_idx]
            selected_opt.subtitle_embed_mode, selected_opt.subtitle_position = sub_mode or "hard_burn", sub_pos or "bottom"
            selected_opt.selected_subtitle_track = session.subtitle_tracks[s_idx] if (session.subtitle_tracks and 0 < s_idx < len(session.subtitle_tracks)) else None
            _apply_session_sub_styles(selected_opt, session)
        from ..media_clipper_engine import sync_clipper_state_from_body
        sync_clipper_state_from_body(session, body, selected_opt)

        final_dest = dest_path or session.default_dest_path
        if selected_opt:
            has_sub = bool(getattr(selected_opt, "selected_subtitle_track", None))
            is_burned = (getattr(selected_opt, "subtitle_embed_mode", "") == "hard_burn") and has_sub
            final_dest = apply_media_filename_tags(final_dest, quality_label=getattr(selected_opt, "resolution_label", ""), is_sub_burned=is_burned, ext=getattr(selected_opt, "ext", "mp4"))
        hm = getattr(session.parent_app, "history_manager", None)
        reserved = hm.get_active_or_queued_paths() if hm else None
        final_dest = generate_unique_destination_path(final_dest, reserved_paths=reserved)

        try:
            from ...config import set_setting
            set_setting("subtitle_embed_mode", sub_mode); set_setting("subtitle_position", sub_pos)
            if getattr(session, "max_connections", 0) > 0:
                set_setting("max_connections", session.max_connections)
                if selected_opt: selected_opt.max_connections = session.max_connections
            if selected_opt:
                set_setting("preferred_video_height", -1 if getattr(selected_opt, "is_audio_only", False) else getattr(selected_opt, "height", 0))
                if getattr(selected_opt, "selected_audio_track", None): set_setting("preferred_audio_lang", selected_opt.selected_audio_track.get("language") or "original")
                st = getattr(selected_opt, "selected_subtitle_track", None)
                if st: set_setting("preferred_subtitle_lang", st.get("language") or "none")
        except Exception: pass

        bridge_mod = sys.modules.get("faqih_downloader.services.preview_stream_bridge")
        sched_fn = getattr(bridge_mod, "_schedule_on_tk", _schedule_on_tk) if bridge_mod else _schedule_on_tk

        def _dispatch():
            if session.modal_ref:
                try:
                    session.modal_ref._confirmed = True
                    session.modal_ref.destroy()
                except Exception: pass
            if session.parent_app:
                for fn in (lambda: hasattr(session.parent_app, "clear_last_clipboard_url") and session.parent_app.clear_last_clipboard_url(),
                           lambda: hasattr(session.parent_app, "set_main_external_subtitles") and session.parent_app.set_main_external_subtitles(getattr(session, "external_subtitle_tracks", []), sync_state=True)):
                    try: fn()
                    except Exception: pass
                if getattr(session, "max_connections", 0) > 0:
                    if hasattr(session.parent_app, "conn_var"):
                        try: session.parent_app.conn_var.set(str(session.max_connections))
                        except Exception: pass
                    if hasattr(session.parent_app, "cb_main_sub_pos") and session.parent_app.cb_main_sub_pos:
                        try: session.parent_app.cb_main_sub_pos.set(str(session.max_connections))
                        except Exception: pass
            if action == "download" and session.on_confirm:
                session.on_confirm(selected_opt, final_dest)
            elif action == "open_in_main":
                if session.on_open_in_main: session.on_open_in_main(selected_opt, final_dest)
            elif action == "cancel" and session.on_cancel:
                session.on_cancel()
            def _kill_cleanup():
                try:
                    from ...ui.modals.video_preview_modal import terminate_active_preview_proc
                    terminate_active_preview_proc()
                except Exception: pass
                unregister_preview_session(session.sid)
            sched_fn(session, _kill_cleanup, 250)

        sched_fn(session, _dispatch, 0)

        self._send_json({"status": "ok", "action": action, "dest_path": final_dest})


__all__ = ["PreviewActionApiMixin"]
