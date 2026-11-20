"""
On-disk file searching and fuzzy download path resolution for Faqih Downloader.
"""
import os
import re
from typing import Optional

from ...config import get_base_downloads_dir
from .categories import VIDEO_EXTENSIONS


def _normalize_match_token(s: str) -> str:
    """Normalize string by removing bracketed tags, punctuation and extra spaces."""
    # Remove bracketed tags like [1080p], (Official), etc.
    s = re.sub(r'[\(\[\{][^\)\]\}]+[\)\]\}]', ' ', s)
    # Strip punctuation and special chars except alphanumeric, space, and Arabic Unicode range
    s = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', s)
    # Lowercase and collapse consecutive spaces
    return " ".join(s.lower().split())


def resolve_existing_download_path(file_path_or_name: str, base_dir: Optional[str] = None) -> Optional[str]:
    """
    Intelligently searches and resolves the actual on-disk file path for a completed download:
    1. Checks the explicitly registered path directly.
    2. Searches inside category subfolders (Downloads/Video, Music, Audio, Compressed, Documents, Programs)
       and Downloads directly.
    3. Permitting cross-video format matching (.mp4, .mkv, .webm, .avi, .mov, .flv).
    4. Searches by partial matching the base filename root stem even if quality suffixes
       like [1080p], [720p], [Sub], or duplicate counters like (1) were appended, stripping punctuation.
    """
    if not file_path_or_name:
        return None

    try:
        norm_input = os.path.normpath(file_path_or_name)
        if os.path.isfile(norm_input):
            return os.path.abspath(norm_input)
    except Exception:
        pass

    if not base_dir or not os.path.isdir(base_dir):
        base_dir = get_base_downloads_dir() if callable(get_base_downloads_dir) else os.path.expanduser("~/Downloads")

    fname = os.path.basename(file_path_or_name)
    if not fname:
        return None

    candidate_dirs = [
        os.path.join(base_dir, "Video"),
        os.path.join(base_dir, "Music"),
        os.path.join(base_dir, "Audio"),
        os.path.join(base_dir, "Compressed"),
        os.path.join(base_dir, "Documents"),
        os.path.join(base_dir, "Programs"),
        os.path.join(base_dir, "Images"),
        base_dir,
    ]
    dname = os.path.dirname(file_path_or_name)
    if dname and os.path.isdir(dname) and dname not in candidate_dirs:
        candidate_dirs.insert(0, dname)

    # 1. Exact filename match inside candidate directories
    for c_dir in candidate_dirs:
        if os.path.isdir(c_dir):
            candidate_p = os.path.join(c_dir, fname)
            if os.path.isfile(candidate_p):
                return os.path.abspath(candidate_p)

    stem, ext = os.path.splitext(fname)
    target_ext = ext.lower()
    is_video = target_ext in VIDEO_EXTENSIONS

    # 2. Cross-video format exact stem match inside candidate directories
    if is_video:
        for c_dir in candidate_dirs:
            if not os.path.isdir(c_dir):
                continue
            for v_ext in VIDEO_EXTENSIONS:
                if v_ext == target_ext:
                    continue
                v_cand = os.path.join(c_dir, f"{stem}{v_ext}")
                if os.path.isfile(v_cand):
                    return os.path.abspath(v_cand)

    # 3. Partial / root stem matching (handles [1080p], [720p], [360p], [Sub], (1), etc.)
    target_norm = _normalize_match_token(stem)
    clean_stem = re.sub(r'[\(\[\{][^\)\]\}]+[\)\]\}]', '', stem).strip()
    target_root = clean_stem.lower() if len(clean_stem) >= 3 else stem.lower()

    for c_dir in candidate_dirs:
        if not os.path.isdir(c_dir):
            continue
        try:
            for entry in os.listdir(c_dir):
                entry_p = os.path.join(c_dir, entry)
                if not os.path.isfile(entry_p):
                    continue
                e_stem, e_ext = os.path.splitext(entry)
                e_ext_lower = e_ext.lower()

                # Format matching: allow any video container if target is video
                if is_video:
                    if e_ext_lower not in VIDEO_EXTENSIONS:
                        continue
                elif target_ext and e_ext_lower != target_ext:
                    continue

                # A. Normalized title match (stripping punctuation and extra tags)
                e_norm = _normalize_match_token(e_stem)
                if target_norm and e_norm:
                    if target_norm == e_norm:
                        return os.path.abspath(entry_p)
                    if len(target_norm) >= 3 and len(e_norm) >= 3:
                        if target_norm in e_norm or e_norm in target_norm:
                            return os.path.abspath(entry_p)

                # B. Substring fallback match
                e_stem_clean = re.sub(r'[\(\[\{][^\)\]\}]+[\)\]\}]', '', e_stem).strip().lower()
                if (target_root in e_stem.lower() or target_root in e_stem_clean or
                        e_stem_clean in target_root):
                    return os.path.abspath(entry_p)
        except Exception:
            continue

    # 4. Search by first 3 words of sanitized title in candidate directories
    target_words = [w for w in target_norm.split() if len(w) >= 2][:3]
    if target_words:
        for c_dir in candidate_dirs:
            if not os.path.isdir(c_dir):
                continue
            try:
                for entry in os.listdir(c_dir):
                    entry_p = os.path.join(c_dir, entry)
                    if not os.path.isfile(entry_p):
                        continue
                    e_stem, e_ext = os.path.splitext(entry)
                    if is_video and e_ext.lower() not in VIDEO_EXTENSIONS:
                        continue
                    e_norm = _normalize_match_token(e_stem)
                    if all(w in e_norm for w in target_words):
                        return os.path.abspath(entry_p)
            except Exception:
                continue

    return None
