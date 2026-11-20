"""
QualityModalActionsMixin: Action dispatchers for downloading video/MP3, launching preview, and opening in main window.
"""
from __future__ import annotations
import os
import sys
import re
import logging
from typing import Optional

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.config import get_setting
from faqih_downloader.utils.file_ops import CATEGORY_SUBFOLDERS, resolve_categorized_path
from faqih_downloader.ui.modals.quality_modal_helpers import sync_modal_selection_to_staged


class QualityModalActionsMixin:
    """Provides action handlers for downloading selected quality, MP3 audio, in-app preview, and main app dispatch."""

    def _on_download_mp3(self):
        """One-click download as universal MP3 audio."""
        mp3_opt = next((o for o in self.options if o.is_audio_only and o.ext.lower() == "mp3"), None)
        if not mp3_opt:
            mp3_opt = next((o for o in self.options if o.is_audio_only), None)
        if not mp3_opt:
            return

        self.selected_option = mp3_opt
        for iid, opt in self._row_to_opt.items():
            if opt == mp3_opt:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                break

        cur_path = self.entry_dest.get().strip()
        target_path = cur_path or self.dest_path
        if target_path:
            base, _ = os.path.splitext(target_path)
            parent_dir = os.path.dirname(target_path)
            parent_base = os.path.basename(os.path.normpath(parent_dir)) if parent_dir else ""
            new_ext = ".mp3"
            sub_low = {v.lower() for v in CATEGORY_SUBFOLDERS.values()}
            if parent_base in CATEGORY_SUBFOLDERS.values() or parent_base.lower() in sub_low:
                updated_dest = resolve_categorized_path(parent_dir, os.path.basename(base) + new_ext, auto_categorize=True, create_dir=False)
            else:
                updated_dest = base + new_ext
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, updated_dest)
            self.dest_path = updated_dest

        self._on_download()

    def _on_download(self):
        if not self.selected_option:
            return
        self._attach_selected_tracks()
        final_dest = self._resolve_final_dest()
        self._confirmed = True
        try: self.grab_release()
        except Exception: pass
        try: self.destroy()
        except Exception: pass
        self.on_confirm(self.selected_option, final_dest)

    def _on_preview_video(self):
        """Launches in-app VidMate-style preview with live dubbing, subtitles, and control bridge."""
        if not self.selected_option:
            return
        self._attach_selected_tracks()
        sel_sub = getattr(self.selected_option, "selected_subtitle_track", getattr(self.selected_option, "subtitle_track", None))
        if not sel_sub and hasattr(self, "cb_sub") and self.cb_sub and self.subtitle_tracks:
            idx = self.cb_sub.current()
            if 0 <= idx < len(self.subtitle_tracks):
                sel_sub = self.subtitle_tracks[idx]

        sel_audio = getattr(self.selected_option, "selected_audio_track", None)
        if not sel_audio and hasattr(self, "cb_audio") and self.cb_audio and self.audio_tracks:
            idx = self.cb_audio.current()
            if 0 <= idx < len(self.audio_tracks):
                sel_audio = self.audio_tracks[idx]

        q_idx = self.options.index(self.selected_option) if (self.selected_option and self.selected_option in self.options) else 0
        sub_pos = self.cb_sub.get_selected_pos() if (hasattr(self, "cb_sub") and self.cb_sub and hasattr(self.cb_sub, "get_selected_pos")) else "bottom"
        try: self.attributes("-topmost", False)
        except Exception: pass
        try:
            mod = sys.modules.get("faqih_downloader.ui.modals.video_preview_modal")
            if mod and hasattr(mod, "open_video_preview"):
                open_video_preview_fn = getattr(mod, "open_video_preview")
            else:
                from ..video_preview_modal import open_video_preview as open_video_preview_fn

            open_video_preview_fn(
                parent=self, url=self.video_url, video_title=self.video_title,
                stream_info=self.selected_option, info_dict=self.raw_info, selected_sub_track=sel_sub,
                theme=self.theme, selected_audio_track=sel_audio, options=self.options,
                audio_tracks=self.audio_tracks, subtitle_tracks=self.subtitle_tracks,
                default_dest_path=self.entry_dest.get().strip() or self.dest_path,
                on_confirm=self.on_confirm, on_open_in_main=self.on_open_in_main, on_cancel=self.on_cancel,
                parent_app=self.parent_app, modal_ref=self, use_bridge=True,
                subtitle_embed_mode=getattr(self.selected_option, "subtitle_embed_mode", "hard_burn"),
                selected_q_idx=q_idx, subtitle_position=sub_pos,
                max_connections=getattr(self.selected_option, "max_connections", None) or int(get_setting("max_connections", 8)),
            )
            self._confirmed = True
            if self.parent_app and getattr(self.parent_app, "_quality_modal", None) is self:
                self.parent_app._quality_modal = None
            self.destroy()
        except Exception:
            logging.getLogger(__name__).exception("Preview launch error")

    def launch_unified_preview(self):
        """Public helper to launch the unified preview and settings interface directly."""
        self._on_preview_video()

    def _on_open_in_main(self):
        if not self.selected_option:
            return
        self._attach_selected_tracks()
        has_sub = bool(getattr(self.selected_option, "selected_subtitle_track", None))
        is_sub_burned = (getattr(self.selected_option, "subtitle_embed_mode", "") == "hard_burn") and has_sub
        res_lbl = str(getattr(self.selected_option, "resolution_label", "") or "")
        has_tag = bool(re.search(r'(\d{3,4}p|4K|8K|Audio|MP3|M4A)', res_lbl, re.IGNORECASE))
        if has_tag or ("[" in (self.dest_path or "")) or ("[" in (self.entry_dest.get() or "")) or is_sub_burned:
            final_dest = self._resolve_final_dest()
        else:
            final_dest = self.entry_dest.get().strip() or self.dest_path
        self._confirmed = True
        try: self.grab_release(); self.destroy()
        except Exception: pass
        if self.on_open_in_main:
            try: self.on_open_in_main(self.selected_option, final_dest)
            except Exception: pass
        else:
            target = self.parent_app or self.master
            if target and hasattr(target, "restore_window"):
                try: target.restore_window()
                except Exception: pass
            sync_modal_selection_to_staged(self)
