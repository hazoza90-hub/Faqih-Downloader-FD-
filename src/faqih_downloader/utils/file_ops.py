"""
File categorization, destination path resolving, and OS shell launch utilities for Smart Download (SD).
"""
import os
import sys
import subprocess
from typing import Tuple, Dict, Optional, Iterable, Set

from ..config import IS_WINDOWS, get_base_downloads_dir
from .magic_detector import MagicBytesDetector
from .archive_utils import calculate_file_integrity, auto_unpack_archive


def get_file_category_and_icon(filename_or_url: str) -> Tuple[str, str]:
    """Returns (category_name, icon_symbol) based on file extension."""
    clean = str(filename_or_url or "").split('?')[0].split('#')[0]
    ext = os.path.splitext(clean)[1].lower().lstrip('.')
    if ext in ("zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso", "tgz", "7zip", "z"):
        return ("Compressed", "📦")
    elif ext in ("exe", "msi", "dmg", "pkg", "deb", "rpm", "apk", "bin", "appimage", "bat", "cmd", "ps1"):
        return ("Programs", "⚙️")
    elif ext in ("mp4", "mkv", "webm", "avi", "mov", "wmv", "flv", "m4v", "3gp", "ts"):
        return ("Video", "🎬")
    elif ext in ("mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "mka"):
        return ("Audio", "🎵")
    elif ext in ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf", "epub", "csv", "json", "xml"):
        return ("Documents", "📄")
    elif ext in ("jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "ico", "tiff"):
        return ("Images", "🖼️")
    else:
        return ("General", "📥")


CATEGORY_SUBFOLDERS: Dict[str, str] = {
    "Video": "Video",
    "Audio": "Music",
    "Programs": "Programs",
    "Compressed": "Compressed",
    "Documents": "Documents",
    "Images": "Images",
    "General": "General",
}


def resolve_categorized_path(base_dir: str, filename: str, auto_categorize: bool = True, create_dir: bool = True) -> str:
    """
    Resolves destination path into typed category subfolders (e.g. Video, Music, Programs, Compressed, etc.)
    when auto_categorize is enabled. Prevents recursive/nested subfolders if base_dir already points
    to a category subfolder.
    """
    raw_fn = str(filename or "").strip().split('?')[0].split('#')[0]
    clean_fn = os.path.basename(raw_fn) or "download.bin"
    if not base_dir or not str(base_dir).strip():
        base_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not auto_categorize:
        return os.path.join(base_dir, clean_fn)

    category, _ = get_file_category_and_icon(clean_fn)
    if clean_fn.lower().endswith(".bin"):
        category = "General"
    subfolder = CATEGORY_SUBFOLDERS.get(category, "General")

    base_norm = os.path.normpath(str(base_dir))
    base_name = os.path.basename(base_norm)
    subfolders_lower = {s.lower() for s in CATEGORY_SUBFOLDERS.values()}
    if base_name in CATEGORY_SUBFOLDERS.values() or base_name.lower() in subfolders_lower:
        root_dir = os.path.dirname(base_norm)
    else:
        root_dir = base_norm

    target_dir = os.path.join(root_dir, subfolder)
    if create_dir:
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            pass

    return os.path.join(target_dir, clean_fn)


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}


def _normalize_match_token(s: str) -> str:
    """Normalize string by removing bracketed tags, punctuation and extra spaces."""
    import re
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
    import re
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


def open_downloaded_file(file_path: str):
    """Opens downloaded file with default OS application."""
    if not file_path:
        return
    actual_path = file_path
    if not os.path.isfile(actual_path):
        resolved = resolve_existing_download_path(file_path)
        if resolved:
            actual_path = resolved
    if not os.path.isfile(actual_path):
        open_containing_folder(file_path)
        return
    try:
        if IS_WINDOWS and hasattr(os, "startfile"):
            os.startfile(actual_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", actual_path])
        else:
            subprocess.Popen(["xdg-open", actual_path])
    except Exception:
        pass


def open_containing_folder(file_path: str):
    """Opens folder containing downloaded file and highlights it on Windows."""
    if not file_path:
        return
    norm_path = os.path.normpath(file_path) if file_path else ""
    base_dir = get_base_downloads_dir() if callable(get_base_downloads_dir) else os.path.expanduser("~/Downloads")

    if not os.path.isfile(norm_path):
        resolved = resolve_existing_download_path(file_path, base_dir)
        if resolved and os.path.isfile(resolved):
            norm_path = resolved

    folder = norm_path if os.path.isdir(norm_path) else os.path.dirname(norm_path)
    if not folder or not os.path.isdir(folder):
        ext = os.path.splitext(norm_path)[1].lower()
        vid_dir = os.path.join(base_dir, "Video")
        if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv") and os.path.isdir(vid_dir):
            folder = vid_dir
        elif os.path.isdir(base_dir):
            folder = base_dir
        else:
            folder = os.path.expanduser("~")

    try:
        if IS_WINDOWS:
            if os.path.isfile(norm_path):
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"')
            elif os.path.isdir(folder):
                if hasattr(os, "startfile"):
                    os.startfile(folder)
                else:
                    subprocess.Popen(f'explorer.exe "{folder}"')
            else:
                home = os.path.expanduser("~")
                if hasattr(os, "startfile"):
                    os.startfile(home)
                else:
                    subprocess.Popen(f'explorer.exe "{home}"')
        elif sys.platform == "darwin":
            if os.path.exists(norm_path) and os.path.isfile(norm_path):
                subprocess.Popen(["open", "-R", norm_path])
            else:
                subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass


def generate_unique_destination_path(
    dest_path: str,
    allow_resume_existing_parts: bool = False,
    reserved_paths: Optional[Iterable[str]] = None
) -> str:
    """
    If dest_path already exists on disk, has active parts, or is in reserved_paths,
    generates a non-colliding filename e.g. 'Title (1).mp4', 'Title (2).mp4'.
    """
    if not dest_path:
        return dest_path

    reserved_norm = {os.path.normcase(os.path.abspath(p)) for p in (reserved_paths or []) if p}

    def _is_path_occupied(p: str, is_dest: bool = False) -> bool:
        if not p:
            return False
        try:
            if os.path.normcase(os.path.abspath(p)) in reserved_norm:
                return True
        except Exception:
            pass
        if os.path.exists(p):
            return True
        can_resume = allow_resume_existing_parts and is_dest
        if not can_resume:
            for suffix in (
                ".sd_parts",
                ".tdm_parts",
                ".video.tmp",
                ".audio.tmp",
                ".video.tmp.sd_parts",
                ".audio.tmp.sd_parts",
            ):
                if os.path.exists(p + suffix):
                    return True
        return False

    if not _is_path_occupied(dest_path, is_dest=True):
        return dest_path

    dirname, filename = os.path.split(dest_path)
    base, ext = os.path.splitext(filename)

    import re
    m = re.match(r'^(.*?)\s*\((\d+)\)$', base)
    if m:
        root_base = m.group(1).rstrip()
        counter = int(m.group(2)) + 1
    else:
        root_base = base
        counter = 1

    while True:
        candidate = os.path.join(dirname, f"{root_base} ({counter}){ext}")
        if not _is_path_occupied(candidate, is_dest=False):
            return candidate
        counter += 1


def apply_media_filename_tags(
    dest_path: str,
    quality_label: Optional[str] = None,
    is_sub_burned: bool = False,
    ext: Optional[str] = None
) -> str:
    """
    Formats destination path to include quality tag (e.g. [1080p], [720p], [Audio])
    and subtitle burn-in tag [Sub], stripping any older tags first.
    """
    if not dest_path:
        return dest_path

    import re
    dirname, filename = os.path.split(dest_path)
    base, old_ext = os.path.splitext(filename)

    clean_base = re.sub(r'\s*\[(?:\d{3,4}p|2160p|1440p|1080p|720p|480p|360p|240p|144p|4k|8k|audio|mp3|m4a)\]', '', base, flags=re.IGNORECASE)
    clean_base = re.sub(r'\s*\[sub(?:-burned)?\]', '', clean_base, flags=re.IGNORECASE)
    clean_base = re.sub(r'(\s*\(\d+\))+$', '', clean_base)
    clean_base = clean_base.strip()

    q_tag = ""
    if quality_label:
        ql = str(quality_label).strip()
        qm = re.search(r'(\d{3,4}p|4K|8K)', ql, flags=re.IGNORECASE)
        if qm:
            q_tag = f"[{qm.group(1)}]"
        elif "audio" in ql.lower():
            q_tag = "[Audio]"
        elif ql:
            clean_ql = re.sub(r'[\(\)\[\]]', '', ql).split('—')[0].split('-')[0].strip()
            if clean_ql:
                q_tag = f"[{clean_ql}]"

    sub_tag = "[Sub]" if is_sub_burned else ""

    parts = [clean_base]
    if q_tag:
        parts.append(q_tag)
    if sub_tag:
        parts.append(sub_tag)

    new_base = " ".join(parts).strip()
    target_ext = ext if ext else old_ext
    if target_ext and not target_ext.startswith("."):
        target_ext = "." + target_ext

    return os.path.join(dirname, f"{new_base}{target_ext}")


def atomic_replace_with_retry(src_path: str, dst_path: str, max_retries: int = 5, retry_delay: float = 0.15) -> None:
    """
    Atomically renames/replaces src_path with dst_path, retrying on transient
    Windows Defender or antivirus file locks (PermissionError / OSError).
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source file not found: {src_path}")
    parent_dir = os.path.dirname(dst_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    for attempt in range(max_retries):
        try:
            os.replace(src_path, dst_path)
            return
        except (PermissionError, OSError) as e:
            if attempt == max_retries - 1:
                try:
                    import shutil
                    shutil.copyfile(src_path, dst_path)
                    os.unlink(src_path)
                    return
                except Exception:
                    raise e
            import time
            time.sleep(retry_delay)


__all__ = [
    "MagicBytesDetector",
    "calculate_file_integrity",
    "auto_unpack_archive",
    "get_file_category_and_icon",
    "CATEGORY_SUBFOLDERS",
    "resolve_categorized_path",
    "resolve_existing_download_path",
    "open_downloaded_file",
    "open_containing_folder",
    "generate_unique_destination_path",
    "apply_media_filename_tags",
    "get_base_downloads_dir",
    "atomic_replace_with_retry",
]

