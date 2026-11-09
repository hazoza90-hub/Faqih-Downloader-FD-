"""
Clipboard sniffer and URL interception controller mixin for Smart Download (SD).
"""
import os
import sys
import threading
import ctypes
from typing import Optional, Callable, Dict, Any

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

from faqih_downloader.i18n import tr
from faqih_downloader.config import get_setting, set_setting, get_base_downloads_dir, DEFAULT_SNIFFER_PLATFORMS
from faqih_downloader.utils import (
    get_clipboard_text,
    is_downloadable_url,
    is_potential_html_url,
    resolve_categorized_path,
    derive_download_filename,
)
from faqih_downloader.core import resolve_real_download_url
from faqih_downloader.services import is_media_url, extract_media_platform
from faqih_downloader.ui.modals.confirm_modal import DownloadConfirmationModal
from faqih_downloader.ui.components.base_modal import SafeModalDialog
from .clipboard_dialog_mixin import ClipboardDialogMixin

IS_WINDOWS = sys.platform == "win32"


def get_url_sniffer_platform_key(url: str) -> str:
    """Resolves the sniffer platform key for a URL (e.g. 'youtube', 'tiktok', 'direct_files')."""
    if not url or not isinstance(url, str):
        return "direct_files"
    clean_url = url.strip()
    if not clean_url:
        return "direct_files"
    try:
        from faqih_downloader.services.youtube_models import is_youtube_url, SOCIAL_MEDIA_PATTERNS
        import re
        if is_youtube_url(clean_url) or re.search(r'^(?:https?://)?(?:[a-zA-Z0-9-]+\.)?(?:youtube\.com|youtu\.be)(?:/|$)', clean_url, re.IGNORECASE):
            return "youtube"
        for name, pat in SOCIAL_MEDIA_PATTERNS.items():
            if pat.search(clean_url):
                return name.lower()
    except Exception:
        pass
    try:
        from faqih_downloader.services import is_media_url
        if is_media_url(clean_url):
            return "other_media"
    except Exception:
        pass
    return "direct_files"


class ClipboardControllerMixin(ClipboardDialogMixin):
    """Provides automatic clipboard monitoring and candidate download URL interception."""

    def is_clipboard_url_allowed(self, url: str) -> bool:
        """Determines whether automatic clipboard interception is allowed for this URL's platform."""
        plat_map = getattr(self, "sniffer_platforms", None)
        if plat_map is None:
            plat_map = get_setting("sniffer_platforms", DEFAULT_SNIFFER_PLATFORMS)
        key = get_url_sniffer_platform_key(url)
        if isinstance(plat_map, dict):
            if key in plat_map:
                return bool(plat_map[key])
            if key in ("snapchat", "rumble") and "threads" in plat_map:
                return bool(plat_map["threads"])
        return True

    def _init_clipboard_sniffer(self):
        """Initializes clipboard monitor state to current clipboard content so existing text doesn't trigger."""
        if not hasattr(self, "sniffer_platforms") or self.sniffer_platforms is None:
            self.sniffer_platforms = dict(get_setting("sniffer_platforms", DEFAULT_SNIFFER_PLATFORMS) or DEFAULT_SNIFFER_PLATFORMS)
        if IS_WINDOWS:
            try: self._last_clipboard_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
            except Exception: self._last_clipboard_seq = None
        try:
            cur = get_clipboard_text(self.root)
            if cur:
                from faqih_downloader.config import is_test_environment
                if is_test_environment() or not is_downloadable_url(cur.strip()):
                    self._last_clipboard_url = cur.strip()
        except Exception: pass

        self._fetch_cancel_event = threading.Event()
        self._update_sniffer_btn()
        if hasattr(self, "root") and self.root:
            try:
                self._clipboard_job = self.root.after(self._clipboard_poll_interval, self._check_clipboard_tick)
            except Exception:
                pass

    def _check_clipboard_tick(self):
        """Periodic timer polling system clipboard for downloadable URLs."""
        if getattr(self, "_closing", False) or not hasattr(self, "root") or not self.root:
            return
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        if getattr(self, "_clipboard_sniffer_active", True):
            try:
                self._check_clipboard_now()
            except Exception:
                pass

        if not getattr(self, "_closing", False):
            try:
                if self.root.winfo_exists():
                    self._clipboard_job = self.root.after(self._clipboard_poll_interval, self._check_clipboard_tick)
            except Exception:
                pass

    def _check_clipboard_now(self, force: bool = False):
        """Checks if current clipboard contains a new downloadable URL and processes it."""
        if not force:
            for m in (getattr(self, "_fetching_toast", None), getattr(self, "_confirm_modal", None), getattr(self, "_candidates_modal", None)):
                if m is not None:
                    try:
                        if m.winfo_exists() and not getattr(m, "is_completed", False) and not getattr(m, "is_closed", False):
                            return
                    except Exception:
                        pass

        seq = None
        if IS_WINDOWS:
            try:
                seq = ctypes.windll.user32.GetClipboardSequenceNumber()
            except Exception:
                seq = None
            if not force and seq is not None and getattr(self, "_last_clipboard_seq", None) is not None:
                if seq == self._last_clipboard_seq:
                    return

        text = get_clipboard_text(self.root)
        if not text or not isinstance(text, str):
            return
        url = text.strip()
        if not url:
            return

        seq_changed = (seq is not None and getattr(self, "_last_clipboard_seq", None) is not None and seq != self._last_clipboard_seq)
        if seq is not None:
            self._last_clipboard_seq = seq

        if not force and not seq_changed and (url == getattr(self, "_last_clipboard_url", None)):
            return
        if not seq_changed and (url == getattr(self, "_last_detected_url", None)):
            return
        self._last_clipboard_url = url
        self._last_detected_url = url
        if is_downloadable_url(url):
            if not self.is_clipboard_url_allowed(url):
                plat = extract_media_platform(url) if is_media_url(url) else 'Direct'
                msg = f"[CLIPBOARD] Ignored {plat} link (disabled in Clipboard Sniffer settings): {url}"
                if hasattr(self, "log") and callable(self.log):
                    self.log(msg)
                return
            self._on_clipboard_url_detected(url)

    def clear_last_clipboard_url(self, url: Optional[str] = None):
        """Marks current clipboard content as already processed so it won't re-trigger unless re-copied."""
        if IS_WINDOWS:
            try: self._last_clipboard_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
            except Exception: pass
        self._last_detected_url = None
        try:
            if url: self._last_clipboard_url = url.strip()
            else:
                cur = get_clipboard_text(getattr(self, "root", None))
                if cur and isinstance(cur, str): self._last_clipboard_url = cur.strip()
                elif getattr(self, "_last_clipboard_url", None) is None: self._last_clipboard_url = ""
        except Exception: pass

    def _resolve_real_url_async(
        self,
        url: str,
        on_resolved: Callable[[Dict[str, Any]], None],
        show_toast: bool = True,
        modal_to_close: Optional[Any] = None
    ):
        """Asynchronously probes and resolves a candidate download URL, handling HTML landing pages."""
        if hasattr(self, "_fetch_cancel_event") and self._fetch_cancel_event:
            try:
                self._fetch_cancel_event.set()
            except Exception:
                pass
        cancel_ev = threading.Event()
        self._fetch_cancel_event = cancel_ev

        if show_toast:
            try:
                def _on_toast_cancel():
                    cancel_ev.set()
                    if hasattr(self, "_yt_cancel_event") and self._yt_cancel_event:
                        try:
                            self._yt_cancel_event.set()
                        except Exception:
                            pass
                    self._is_resolving_start = False
                    try:
                        self.btn_start.configure(state="normal")
                    except Exception:
                        pass
                self._show_fetching_toast(url, on_cancel=_on_toast_cancel)
            except Exception:
                pass

        def _worker():
            if cancel_ev.is_set():
                return
            try:
                info = resolve_real_download_url(url, ssl_context=getattr(self, "ssl_context", None))
            except Exception as e:
                info = {"url": url, "error": str(e), "resolved": False}
            if cancel_ev.is_set():
                return

            def _dispatch():
                if cancel_ev.is_set():
                    return
                try:
                    self._close_fetching_toast()
                except Exception:
                    pass
                if cancel_ev.is_set():
                    return

                def _cleanup_modal():
                    if modal_to_close:
                        try:
                            modal_to_close.destroy()
                        except Exception:
                            pass
                        if getattr(self, "_confirm_modal", None) is modal_to_close:
                            self._confirm_modal = None

                candidates = info.get("candidates") or []

                if len(candidates) > 1:
                    if cancel_ev.is_set():
                        return
                    self._is_resolving_start = False
                    try:
                        self.btn_start.configure(state="normal")
                    except Exception:
                        pass
                    self.clear_last_clipboard_url()
                    _cleanup_modal()
                    self.log(f"[LINK RESOLVER] Multiple download candidates ({len(candidates)}) detected on page: {url}")
                    self._show_multiple_candidates_dialog(url, candidates, page_title=info.get("page_title", ""))
                    return

                if info.get("is_html") and not info.get("resolved"):
                    if cancel_ev.is_set():
                        return
                    self._is_resolving_start = False
                    self.clear_last_clipboard_url()
                    _cleanup_modal()
                    try:
                        self.btn_start.configure(state="normal")
                        self.btn_pause.configure(state="disabled")
                        self.btn_cancel.configure(state="disabled")
                    except Exception:
                        pass
                    self.log(f"[LINK RESOLVER] Web page detected (not a download link): {url}")
                    SafeModalDialog(
                        self.root,
                        title=tr("dialog_not_download_title"),
                        message=tr("dialog_not_download_msg"),
                        dialog_type="warning",
                        theme=self._theme_dict()
                    )
                    return

                if len(candidates) == 1 and info.get("is_html"):
                    cand = candidates[0]
                    info["url"] = cand["url"]
                    if cand.get("filename"):
                        info["filename"] = cand["filename"]
                    info["resolved"] = True
                    info["is_html"] = False

                if cancel_ev.is_set():
                    return
                on_resolved(info)

            self.dispatch_to_main_thread(_dispatch)

        t = threading.Thread(target=_worker, daemon=True, name="LinkResolverThread")
        t.start()

    def _on_clipboard_url_detected(self, url: str):
        super()._on_clipboard_url_detected(url)


__all__ = [
    "ClipboardControllerMixin",
    "ClipboardDialogMixin",
    "get_url_sniffer_platform_key",
]

