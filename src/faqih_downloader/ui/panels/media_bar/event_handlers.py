"""
MediaBarEventHandlersMixin: Event callbacks for user dropdown selections and clicks in the media bar.
"""
from typing import List, Dict, Any
from ....config import set_setting


class MediaBarEventHandlersMixin:
    """Provides event handlers for combobox selections, external subtitle pickers, and settings changes."""

    def _on_main_quality_changed(self, event=None):
        """Dynamically updates destination filename extension and quality tag when user picks a different quality."""
        if getattr(self, "_main_media_options", None) and hasattr(self, "cb_main_quality"):
            idx = self.cb_main_quality.current()
            if 0 <= idx < len(self._main_media_options) and event is not None:
                h = getattr(self._main_media_options[idx], "height", 0) or 0
                if h > 0:
                    try: set_setting("preferred_video_height", h)
                    except Exception: pass
        self._sync_media_bar_state(event)

    def _on_main_audio_changed(self, event=None):
        """Persists preferred audio language when user selects a different audio track."""
        if event is not None and getattr(self, "_main_audio_tracks", None):
            idx = self.cb_main_audio.current()
            if 0 <= idx < len(self._main_audio_tracks):
                track = self._main_audio_tracks[idx]
                lang = track.get("language") or ("original" if idx == 0 else "")
                if lang:
                    try: set_setting("preferred_audio_lang", lang)
                    except Exception: pass
        self._sync_media_bar_state(event)

    def _on_main_sub_changed(self, event=None):
        """Enables or disables subtitle mode combobox based on selected subtitle."""
        idx = self.cb_main_sub.current()
        has_s = len(getattr(self, "_main_subtitle_tracks", [])) > 1 and idx > 0
        if hasattr(self, "cb_main_sub_mode"):
            self.cb_main_sub_mode.configure(state="readonly" if has_s else "disabled")
        if hasattr(self, "cb_main_sub_pos"):
            self.cb_main_sub_pos.configure(state="readonly")
        if event is not None and getattr(self, "_main_subtitle_tracks", None):
            lang = self._main_subtitle_tracks[idx].get("language") if (0 < idx < len(self._main_subtitle_tracks)) else "none"
            try: set_setting("preferred_subtitle_lang", lang or "none")
            except Exception: pass
        self._sync_media_bar_state(event)

    def _open_main_ext_srt_menu(self):
        """Opens dark multi-select popup menu for independent external .SRT files."""
        from ...modals.quality_tracks_ui import open_ext_srt_popup_menu
        theme = getattr(self, "_theme_dict", lambda: {})()
        open_ext_srt_popup_menu(
            self.btn_main_ext_srt, getattr(self, "_main_subtitle_tracks", []),
            getattr(self, "_main_external_subtitle_tracks", []),
            lambda picked: self.set_main_external_subtitles(picked, sync_state=True), theme=theme,
        )

    def set_main_external_subtitles(self, tracks: List[Dict[str, Any]], sync_state: bool = True):
        """Updates selected external .SRT tracks and button badge on main media bar."""
        from ...modals.quality_tracks_ui import format_ext_srt_button_text
        self._main_external_subtitle_tracks = [
            dict(t) for t in (tracks or []) if isinstance(t, dict) and str(t.get("sub_id") or "").lower() != "none"
        ]
        if hasattr(self, "btn_main_ext_srt") and self.btn_main_ext_srt and self.btn_main_ext_srt.winfo_exists():
            self.btn_main_ext_srt.configure(text=format_ext_srt_button_text(self._main_external_subtitle_tracks))
        if sync_state:
            self._sync_media_bar_state()

    def _on_main_sub_mode_changed(self, event=None):
        """Saves chosen mode, auto-selects Arabic/first subtitle track if None, and reflects [Sub] tag."""
        cur_idx = self.cb_main_sub_mode.current()
        chosen = "soft_embed"
        if 0 <= cur_idx < len(self._main_sub_mode_codes):
            chosen = self._main_sub_mode_codes[cur_idx]
            try: set_setting("subtitle_embed_mode", chosen)
            except Exception: pass
        if self.cb_main_sub.current() <= 0 and len(self._main_subtitle_tracks) > 1:
            ar_idx = next((i for i, s in enumerate(self._main_subtitle_tracks) if i > 0 and str(s.get("language", "")).lower().startswith("ar")), None)
            target_idx = ar_idx if ar_idx is not None else 1
            self.cb_main_sub.current(target_idx)
            self.cb_main_sub_mode.configure(state="readonly")
            self.cb_main_sub_pos.configure(state="readonly")
        self._sync_media_bar_state(event)

    def _on_main_sub_pos_changed(self, event=None):
        """Persists selected thread/connection count or fallback subtitle position."""
        val = str(self.cb_main_sub_pos.get() if hasattr(self.cb_main_sub_pos, "get") else "").strip()
        if val.isdigit() and int(val) in (1, 2, 4, 8, 16, 24, 32):
            try:
                set_setting("max_connections", int(val))
                if hasattr(self, "conn_var"): self.conn_var.set(val)
            except Exception: pass
        else:
            cur_idx = self.cb_main_sub_pos.current() if hasattr(self.cb_main_sub_pos, "current") else -1
            if 0 <= cur_idx < len(getattr(self, "_main_sub_pos_codes", [])):
                pos = self._main_sub_pos_codes[cur_idx]
                if event is not None:
                    try: set_setting("subtitle_position", pos)
                    except Exception: pass
        self._sync_media_bar_state(event)

__all__ = ["MediaBarEventHandlersMixin"]
