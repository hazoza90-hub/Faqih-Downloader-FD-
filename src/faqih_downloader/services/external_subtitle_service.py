"""
Independent multi-language external .SRT subtitle helpers for Faqih Downloader (FD).
"""

import os
from typing import Any, Callable, Dict, List, Set, Tuple


def get_valid_ext_tracks(stream_info: Any) -> List[Dict[str, Any]]:
    """Returns deduplicated valid external subtitle track dicts from stream_info."""
    raw = getattr(stream_info, "external_subtitle_tracks", None) or []
    valid: List[Dict[str, Any]] = []
    seen_langs: Set[str] = set()
    for trk in raw:
        if not isinstance(trk, dict):
            continue
        sub_id = str(trk.get("sub_id") or "").strip().lower()
        lang = str(trk.get("language") or trk.get("sub_id") or "").strip().lower()
        if sub_id == "none" or lang in ("", "none"):
            continue
        if not (trk.get("url") or trk.get("base_url") or trk.get("language") or trk.get("sub_id")):
            continue
        if lang in seen_langs:
            continue
        seen_langs.add(lang)
        valid.append(trk)
    return valid


def get_protected_ext_langs(stream_info: Any) -> Set[str]:
    """Returns lowercase language codes protected from post-mux SRT cleanup."""
    langs: Set[str] = set()
    for trk in get_valid_ext_tracks(stream_info):
        for k in ("language", "sub_id"):
            val = str(trk.get(k) or "").strip()
            if val and val.lower() != "none":
                langs.add(val.lower())
    return langs


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)) if path else ""


def is_protected_external_srt(
    path: str,
    orig_stem: str,
    cur_stem: str,
    protected_langs: Set[str],
    protected_paths: Set[str],
) -> bool:
    """Returns True if path corresponds to an explicitly requested external .srt file."""
    if not path:
        return False
    norm_p = _norm_path(path)
    if norm_p in protected_paths:
        return True
    if not protected_langs:
        return False
    fname_lower = os.path.basename(norm_p)
    for stem in (orig_stem, cur_stem):
        if not stem:
            continue
        stem_base = os.path.basename(os.path.normcase(stem))
        for lang in protected_langs:
            if fname_lower in (f"{stem_base}.{lang}.srt", f"{stem_base}.{lang}.sec.srt"):
                return True
    return False


def submit_external_prefetches(
    executor: Any,
    stream_info: Any,
    output_path: str,
    download_fn: Callable[[Dict[str, Any], str], Any],
) -> Dict[str, Any]:
    """Submits parallel downloads for all valid external subtitle tracks."""
    futures: Dict[str, Any] = {}
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    primary_lang = ""
    if isinstance(sub, dict) and sub.get("sub_id") not in (None, "none"):
        primary_lang = str(sub.get("language") or sub.get("sub_id") or "").strip().lower()
    for trk in get_valid_ext_tracks(stream_info):
        lang = str(trk.get("language") or trk.get("sub_id") or "sub").strip().lower()
        if primary_lang and lang == primary_lang:
            continue
        futures[lang] = executor.submit(download_fn, trk, output_path)
    return futures


def prepare_srt_once(stream_info: Any, srt_path: str, orig_stem: str, prepare_fn: Callable[[Any, str, str], Any]) -> None:
    """Runs prepare_fn at most once per normalized SRT path."""
    if not srt_path or not prepare_fn:
        return
    prepared_paths: Set[str] = getattr(stream_info, "_prepared_srt_paths", None) or set()
    stream_info._prepared_srt_paths = prepared_paths
    norm_p = _norm_path(srt_path)
    if norm_p not in prepared_paths:
        prepare_fn(stream_info, srt_path, orig_stem)
        prepared_paths.add(norm_p)


def process_external_subtitle_tracks(
    stream_info: Any,
    output_path: str,
    orig_stem: str,
    on_log: Any = None,
    cancel_event: Any = None,
    download_fn: Callable[[Dict[str, Any], str], Any] = None,
    prepare_fn: Callable[[Any, str, str], Any] = None,
    defer_prepare_langs: Optional[Set[str]] = None,
) -> Tuple[Dict[str, str], Set[str]]:
    """Downloads (or reuses prefetched) external .srt tracks and prepares cues/clips."""
    ext_paths: Dict[str, str] = {}
    protected_norm_paths: Set[str] = set()
    prepared_paths: Set[str] = getattr(stream_info, "_prepared_srt_paths", None) or set()
    stream_info._prepared_srt_paths = prepared_paths
    defer_set = {x.lower() for x in (defer_prepare_langs or set())}

    ext_tracks = get_valid_ext_tracks(stream_info)
    if not ext_tracks:
        return ext_paths, protected_norm_paths

    prefetched_map = getattr(stream_info, "_prefetched_external_srts", None) or {}
    primary_pref = getattr(stream_info, "_prefetched_srt_path", None)
    sub = getattr(stream_info, "subtitle_track", None) or getattr(stream_info, "selected_subtitle_track", None)
    primary_lang = str(sub.get("language") or sub.get("sub_id") or "").strip().lower() if isinstance(sub, dict) else ""

    for trk in ext_tracks:
        if cancel_event and cancel_event.is_set():
            break
        lang_raw = str(trk.get("language") or trk.get("sub_id") or "sub").strip()
        lang_key = lang_raw.lower()

        srt_p = prefetched_map.get(lang_key)
        if (not srt_p or not os.path.isfile(srt_p) or os.path.getsize(srt_p) == 0) and lang_key == primary_lang:
            if primary_pref and os.path.isfile(primary_pref) and os.path.getsize(primary_pref) > 0:
                srt_p = primary_pref

        if not srt_p or not os.path.isfile(srt_p) or os.path.getsize(srt_p) == 0:
            if on_log:
                on_log(f"Downloading external subtitle ({lang_raw})...")
            srt_p = download_fn(trk, output_path) if download_fn else None

        if srt_p and os.path.isfile(srt_p) and os.path.getsize(srt_p) > 0:
            norm_p = _norm_path(srt_p)
            if prepare_fn and lang_key not in defer_set and norm_p not in prepared_paths:
                prepare_fn(stream_info, srt_p, orig_stem)
                prepared_paths.add(norm_p)
            ext_paths[lang_key] = srt_p
            protected_norm_paths.add(norm_p)
        elif on_log:
            on_log(f"External subtitle ({lang_raw}) unavailable or empty.")

    return ext_paths, protected_norm_paths


def rename_sidecar_srts_on_video_rename(
    d_dir: str, old_stem: str, new_stem: str, only_langs: Optional[Set[str]] = None
) -> None:
    """Renames matching {old_stem}*.srt files when video filename stem changes."""
    if not d_dir or not old_stem or not new_stem or old_stem == new_stem or not os.path.isdir(d_dir):
        return
    if only_langs is not None and not only_langs:
        return
    prefix = f"{old_stem}."
    try:
        entries = list(os.listdir(d_dir))
    except Exception:
        return
    for fname in entries:
        if not fname.lower().endswith(".srt"):
            continue
        if only_langs is not None:
            matched = any(fname.lower() in (f"{old_stem.lower()}.{l}.srt", f"{old_stem.lower()}.{l}.sec.srt") for l in only_langs)
            if not matched:
                continue
        if fname == f"{old_stem}.srt":
            new_fname = f"{new_stem}.srt"
        elif fname.startswith(prefix):
            new_fname = f"{new_stem}{fname[len(old_stem):]}"
        else:
            continue
        old_p = os.path.join(d_dir, fname)
        new_p = os.path.join(d_dir, new_fname)
        if old_p != new_p and os.path.isfile(old_p):
            try:
                os.replace(old_p, new_p)
            except Exception:
                pass


def _normalize_ext_sub_key(track: Dict[str, Any]) -> str:
    return str(track.get("sub_id") or track.get("language") or "").strip().lower()


def sync_preview_external_subtitles(
    session: Any,
    body: Dict[str, Any],
    target_opts: List[Any],
) -> List[Dict[str, Any]]:
    """Resolve and sync external .SRT tracks from a preview API payload onto session and target options."""
    sub_trks = getattr(session, "subtitle_tracks", None) or []
    has_idx = "ext_sub_indices" in body
    has_langs = "ext_sub_langs" in body

    if has_idx or has_langs:
        raw_indices = body.get("ext_sub_indices")
        raw_langs = body.get("ext_sub_langs")
        picked: List[Dict[str, Any]] = []
        seen: set = set()

        if isinstance(raw_indices, list):
            for raw_idx in raw_indices:
                try:
                    idx = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(sub_trks):
                    trk = sub_trks[idx]
                    if isinstance(trk, dict) and str(trk.get("sub_id") or "").lower() != "none":
                        key = _normalize_ext_sub_key(trk) or str(idx)
                        if key not in seen:
                            seen.add(key)
                            picked.append(dict(trk))

        if isinstance(raw_langs, list):
            wanted = [
                str(x).strip().lower()
                for x in raw_langs
                if str(x or "").strip() and str(x).strip().lower() != "none"
            ]
            for w in wanted:
                w_base = w.split("-")[0].split("_")[0]
                matched_idx = None
                for pass_num in (1, 2):
                    for idx, trk in enumerate(sub_trks):
                        if not isinstance(trk, dict):
                            continue
                        sub_id = str(trk.get("sub_id") or "").strip().lower()
                        lang = str(trk.get("language") or "").strip().lower()
                        if sub_id == "none" or lang == "none":
                            continue
                        if pass_num == 1 and w in (sub_id, lang):
                            matched_idx = idx
                            break
                        if pass_num == 2:
                            lang_base = lang.split("-")[0].split("_")[0]
                            sub_base = sub_id.split("-")[0].split("_")[0]
                            if w in (lang_base, sub_base) or (w_base and w_base in (lang_base, sub_base)):
                                matched_idx = idx
                                break
                    if matched_idx is not None:
                        break
                if matched_idx is not None:
                    trk = sub_trks[matched_idx]
                    key = _normalize_ext_sub_key(trk) or str(matched_idx)
                    if key not in seen:
                        seen.add(key)
                        picked.append(dict(trk))

        session.external_subtitle_tracks = picked

    resolved_ext = get_valid_ext_tracks(session)
    session.external_subtitle_tracks = list(resolved_ext)

    for t_opt in (target_opts or []):
        try:
            t_opt.external_subtitle_tracks = list(resolved_ext)
        except Exception:
            pass
    return list(resolved_ext)
