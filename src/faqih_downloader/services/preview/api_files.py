"""
api_files.py: Preview HTTP API mixin for live filename tagging and native save-file browsing.
"""
import os
import re
import sys
import threading
from typing import Dict, List, Optional, Any

from ...utils.file_ops import apply_media_filename_tags, generate_unique_destination_path
from .origin_guard import _safe_int
from .session_store import PreviewSession
from .tk_dispatch import _schedule_on_tk


class PreviewFileApiMixin:
    """Handles /api/update_filename and /api/browse endpoints."""

    def _handle_api_update_filename(self, session: PreviewSession, body: Dict[str, Any]) -> None:
        """Updates the destination filename with quality, chapter, clip, and burn-in tags live."""
        q_idx = _safe_int(body.get("q_idx", 0))
        s_idx = _safe_int(body.get("s_idx", -1))
        sub_mode = str(body.get("sub_mode", "soft_embed"))
        cur_dest = str(body.get("current_dest", "")).strip() or session.default_dest_path

        old_ch = str(getattr(session, "chapter_title", "") or "").strip()
        ch_title = str(body.get("chapter_title") if "chapter_title" in body else old_ch).strip()
        _tf = lambda v, d=0.0: float(v) if (v is not None and str(v).replace('.', '', 1).replace('-', '', 1).isdigit()) else float(d)
        c_start = _tf(body.get("clip_start"), getattr(session, "clip_start", 0.0) or 0.0) if "clip_start" in body else float(getattr(session, "clip_start", 0.0) or 0.0)
        c_end = _tf(body.get("clip_end"), getattr(session, "clip_end", 0.0) or 0.0) if "clip_end" in body else float(getattr(session, "clip_end", 0.0) or 0.0)
        has_clip = (c_end > c_start >= 0.0)

        if "chapter_title" in body: session.chapter_title = ch_title
        if "clip_start" in body or "clip_end" in body: session.clip_start, session.clip_end = c_start, c_end

        # Strip previous [Clip] and chapter tags from cur_dest before applying quality tags
        d_dir, f_name = os.path.split(cur_dest)
        stem, ext = os.path.splitext(f_name)
        stem = re.sub(r'\s*\[Clip\]', '', stem, flags=re.IGNORECASE).strip()
        _cl = lambda t: re.sub(r'^[\[\]\s\-–—:|•~.]+|[\[\]\s\-–—:|•~.]+$', '', re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', str(t or ''))).strip()
        cands = {old_ch, _cl(old_ch), getattr(session, "last_clean_ch", "")}
        for ch in (getattr(session, "chapters", []) or []):
            ct = str(ch.get("title", "")).strip()
            if ct: cands.update((ct, _cl(ct)))
        for c in cands:
            if c: stem = re.sub(r'\s*\[' + re.escape(c) + r'\]', '', stem).strip()
        stem = re.sub(r'\s*\[(?:الجزء\s*\d+[^\]]*|النصف الأول من الفيديو|النصف الثاني من الفيديو)\]', '', stem).strip()
        clean_cur_dest = os.path.join(d_dir, f"{stem}{ext}")

        opt = session.options[q_idx] if 0 <= q_idx < len(session.options) else (session.options[0] if session.options else None)
        if opt:
            has_subs = (s_idx > 0) if s_idx >= 0 else ((bool(session.subtitle_tracks) and len(session.subtitle_tracks) > 1) if session.selected_sub_track is None else (session.selected_sub_track.get("sub_id") not in (None, "none")))
            is_burned = (sub_mode == "hard_burn") and has_subs
            updated = apply_media_filename_tags(clean_cur_dest, quality_label=getattr(opt, "resolution_label", ""), is_sub_burned=is_burned, ext=getattr(opt, "ext", "mp4"))
        else:
            updated = clean_cur_dest

        clean_ch = _cl(ch_title)
        session.last_clean_ch = clean_ch
        d_dir2, f_name2 = os.path.split(updated)
        stem2, ext2 = os.path.splitext(f_name2)
        if clean_ch and f"[{clean_ch}]" not in stem2: stem2 = f"{stem2} [{clean_ch}]"
        if has_clip and "[Clip]" not in stem2: stem2 = f"{stem2} [Clip]"
        updated = os.path.join(d_dir2, f"{stem2}{ext2}")

        hm = getattr(session.parent_app, "history_manager", None)
        final_dest = generate_unique_destination_path(updated, reserved_paths=hm.get_active_or_queued_paths() if hm else None)
        self._send_json({"dest_path": final_dest})

    def _handle_api_browse(self, session: PreviewSession, body: Dict[str, Any], params: Dict[str, List[str]]) -> None:
        """Opens native file picker on Tkinter thread to choose download destination file."""
        current_dest = str(body.get("current_dest") or params.get("current_dest", [""])[0] or session.default_dest_path).strip()
        chosen_holder: List[Optional[str]] = [None]; browse_evt = threading.Event()
        def _ask():
            try:
                from tkinter import filedialog
                parent_w = session.modal_ref if (session.modal_ref and hasattr(session.modal_ref, "winfo_exists") and session.modal_ref.winfo_exists()) else (session.parent_app.root if (session.parent_app and hasattr(session.parent_app, "root")) else None)
                cur_d = current_dest or session.default_dest_path
                init_dir, init_file = (os.path.dirname(os.path.abspath(cur_d)) if cur_d else os.path.expanduser("~")), (os.path.basename(cur_d) if cur_d else "video.mp4")
                res = filedialog.asksaveasfilename(parent=parent_w, title="Save Video As", initialdir=init_dir, initialfile=init_file)
                if res: chosen_holder[0] = str(res)
            except Exception: pass
            finally: browse_evt.set()
        bridge_mod = sys.modules.get("faqih_downloader.services.preview_stream_bridge")
        sched_fn = getattr(bridge_mod, "_schedule_on_tk", _schedule_on_tk) if bridge_mod else _schedule_on_tk
        sched_fn(session, _ask, 0); browse_evt.wait(timeout=60.0)

        chosen = chosen_holder[0]
        if chosen:
            session.default_dest_path = chosen
            try:
                from ...config import set_setting
                from ...utils.file_ops import CATEGORY_SUBFOLDERS
                cd = os.path.dirname(os.path.abspath(chosen))
                auto_cat = getattr(session.parent_app, "auto_categorize_folders", True) if session.parent_app else True
                if auto_cat and os.path.basename(cd).lower() in {s.lower() for s in CATEGORY_SUBFOLDERS.values()}: cd = os.path.dirname(cd)
                set_setting("last_download_dir", cd)
            except Exception: pass
            self._send_json({"ok": True, "dest": chosen})
        else: self._send_json({"ok": False, "dest": ""})


__all__ = ["PreviewFileApiMixin"]
