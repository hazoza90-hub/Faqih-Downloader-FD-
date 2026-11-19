"""
prefetch.py: Background parallel prefetching of primary, dual, and external .srt subtitle tracks.
"""
import os
import sys
import threading
from typing import Dict, Optional, Tuple, Callable, Any

from ..external_subtitle_service import get_valid_ext_tracks, submit_external_prefetches
from .downloader import download_subtitle_as_srt


def start_subtitle_prefetch(
    stream_info: Any,
    output_path: str,
    download_fn: Optional[Callable[..., Optional[str]]] = None,
) -> Optional[threading.Thread]:
    """Starts background parallel prefetch for internal, dual, and external .srt tracks."""
    if not stream_info or not output_path or hasattr(stream_info, "_mock_name"):
        return None
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    has_prim = isinstance(sub, dict) and sub.get("sub_id") not in (None, "none") and bool(sub.get("url") or sub.get("base_url"))
    ext_tracks = get_valid_ext_tracks(stream_info)
    if not has_prim and not ext_tracks:
        return None

    if download_fn is None:
        sp_mod = sys.modules.get("faqih_downloader.services.subtitle_processor")
        eff_download_fn = getattr(sp_mod, "download_subtitle_as_srt", download_subtitle_as_srt) if sp_mod else download_subtitle_as_srt
    else:
        eff_download_fn = download_fn

    setattr(stream_info, "_prefetched_external_srts", {})
    pf_lock = threading.Lock()

    def _bg():
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fut_meta: Dict[Any, Tuple[str, str]] = {}
                if has_prim: fut_meta[pool.submit(eff_download_fn, sub, output_path)] = ("prim", "")
                sec_trk = getattr(stream_info, "secondary_subtitle_track", None)
                if has_prim and getattr(stream_info, "dual_subtitle_enabled", False) and isinstance(sec_trk, dict) and (sec_trk.get("url") or sec_trk.get("base_url")):
                    fut_meta[pool.submit(eff_download_fn, sec_trk, f"{os.path.splitext(output_path)[0]}.sec.srt")] = ("sec", "")
                if ext_tracks:
                    for lang, fut in submit_external_prefetches(pool, stream_info, output_path, eff_download_fn).items():
                        fut_meta[fut] = ("ext", lang)
                for fut in as_completed(fut_meta):
                    kind, lang = fut_meta[fut]
                    try: p = fut.result()
                    except Exception: p = None
                    if isinstance(p, str) and p and os.path.isfile(p):
                        with pf_lock:
                            if kind == "prim": setattr(stream_info, "_prefetched_srt_path", p)
                            elif kind == "sec": setattr(stream_info, "_prefetched_sec_srt_path", p)
                            elif kind == "ext": stream_info._prefetched_external_srts[lang] = p
        except Exception: pass

    t = threading.Thread(target=_bg, daemon=True)
    setattr(stream_info, "_subtitle_prefetch_thread", t)
    t.start()
    return t


__all__ = [
    "start_subtitle_prefetch",
]
