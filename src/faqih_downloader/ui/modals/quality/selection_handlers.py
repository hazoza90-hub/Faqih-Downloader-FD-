"""
QualityModalSelectionMixin: Handlers for Treeview selection, destination browsing, track attaching, and initial options.
"""
from __future__ import annotations
import os
import sys
from typing import List, Dict, Any

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = filedialog = None  # type: ignore

from faqih_downloader.config import get_base_downloads_dir
from faqih_downloader.utils.file_ops import CATEGORY_SUBFOLDERS, resolve_categorized_path, apply_media_filename_tags
from faqih_downloader.ui.modals.quality_modal_helpers import (
    attach_selected_tracks_to_option,
    resolve_final_dest,
    resolve_preferred_option_index,
    sync_modal_selection_to_staged,
)


class QualityModalSelectionMixin:
    """Provides selection event callbacks and track attachment logic for QualitySelectionModal."""

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item and item in self._row_to_opt:
            self.tree.selection_set(item)
            self.selected_option = self._row_to_opt[item]
            self._on_tree_select(None)
        self._on_preview_video()

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        opt = self._row_to_opt.get(iid)
        if not opt:
            return
        self.selected_option = opt
        if event is not None and opt:
            try:
                from faqih_downloader.config import set_setting
                val_h = -1 if getattr(opt, "is_audio_only", False) else getattr(opt, "height", 0)
                set_setting("preferred_video_height", val_h)
            except Exception: pass

        cur_path = self.entry_dest.get().strip()
        target_path = cur_path or self.dest_path
        if target_path:
            sub_mode = "soft_embed"
            if hasattr(self, "cb_sub") and self.cb_sub:
                mode_fn = getattr(self.cb_sub, "get_selected_mode", None)
                sub_mode = mode_fn() if callable(mode_fn) else getattr(self.cb_sub, "_selected_mode", "soft_embed")
            has_sub = bool(getattr(opt, "selected_subtitle_track", None))
            updated_dest = apply_media_filename_tags(
                target_path,
                quality_label=opt.resolution_label,
                is_sub_burned=(sub_mode == "hard_burn") and has_sub,
                ext=opt.ext.lower()
            )
            parent_dir = os.path.dirname(updated_dest)
            parent_base = os.path.basename(os.path.normpath(parent_dir)) if parent_dir else ""
            subfolders_lower = {v.lower() for v in CATEGORY_SUBFOLDERS.values()}
            if parent_base in CATEGORY_SUBFOLDERS.values() or parent_base.lower() in subfolders_lower:
                updated_dest = resolve_categorized_path(parent_dir, os.path.basename(updated_dest), auto_categorize=True, create_dir=False)
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, updated_dest)
            if self.dest_path:
                self.dest_path = updated_dest
        sync_modal_selection_to_staged(self)

    def _on_browse(self):
        if not filedialog:
            return
        cur = self.entry_dest.get().strip()
        mod = sys.modules.get("faqih_downloader.ui.modals.quality_modal_helpers")
        base_getter = getattr(mod, "get_base_downloads_dir", get_base_downloads_dir)
        init_dir = os.path.dirname(cur) if cur else (getattr(self.parent_app, "_get_base_downloads_dir", base_getter)())
        init_file = os.path.basename(cur) if cur else "download.mp4"
        chosen = filedialog.asksaveasfilename(parent=self, title="Save Video As", initialdir=init_dir, initialfile=init_file)
        if chosen:
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, chosen)
            self.dest_path = chosen
            try:
                from faqih_downloader.config import set_setting
                cd = os.path.dirname(os.path.abspath(chosen))
                if getattr(self.parent_app, "auto_categorize_folders", True) and os.path.basename(cd).lower() in {s.lower() for s in CATEGORY_SUBFOLDERS.values()}:
                    cd = os.path.dirname(cd)
                set_setting("last_download_dir", cd)
            except Exception: pass

    def _resolve_initial_index(self) -> int:
        if getattr(self, "_initial_option", None) is not None and self.options:
            for idx, opt in enumerate(self.options):
                if opt is self._initial_option: return idx
            pk = (getattr(self._initial_option, "format_id", ""), getattr(self._initial_option, "resolution_label", ""), getattr(self._initial_option, "ext", ""))
            for idx, opt in enumerate(self.options):
                if (getattr(opt, "format_id", ""), getattr(opt, "resolution_label", ""), getattr(opt, "ext", "")) == pk:
                    return idx
        return resolve_preferred_option_index(self.options)

    def _resolve_initial_ext_subs(self) -> List[Dict[str, Any]]:
        sources = [getattr(self.selected_option, "external_subtitle_tracks", None)]
        for o in (self.options or []):
            sources.append(getattr(o, "external_subtitle_tracks", None))
        p_app = self.parent_app
        if p_app is not None:
            p_ctx = getattr(p_app, "_pending_media_context", None)
            if p_ctx is None or not self.video_url or (isinstance(p_ctx, dict) and p_ctx.get("url") == self.video_url):
                if isinstance(p_ctx, dict): sources.append(p_ctx.get("external_subtitle_tracks"))
                sources.append(getattr(p_app, "_main_external_subtitle_tracks", None))
        for src in sources:
            if isinstance(src, list) and src:
                return [dict(t) for t in src if isinstance(t, dict)]
        return []

    def _attach_selected_tracks(self):
        attach_selected_tracks_to_option(
            self.selected_option, self.audio_tracks, self.cb_audio, self.subtitle_tracks, self.cb_sub, all_options=getattr(self, "options", None)
        )

    def _resolve_final_dest(self) -> str:
        return resolve_final_dest(self.entry_dest, self.dest_path, self.video_title, self.selected_option, self.parent_app, self.master)
