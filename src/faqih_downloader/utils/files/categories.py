"""
File category classifications, extension icons, and path categorization for Faqih Downloader.
"""
import os
from typing import Tuple, Dict

CATEGORY_SUBFOLDERS: Dict[str, str] = {
    "Video": "Video",
    "Audio": "Music",
    "Programs": "Programs",
    "Compressed": "Compressed",
    "Documents": "Documents",
    "Images": "Images",
    "General": "General",
}

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}


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
