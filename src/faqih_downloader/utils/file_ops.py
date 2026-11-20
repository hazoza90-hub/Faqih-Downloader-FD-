"""
Backward-compatibility shim for file operations.
Re-exports functionality from faqih_downloader.utils.files.*
"""
from ..config import get_base_downloads_dir
from .magic_detector import MagicBytesDetector
from .archive_utils import calculate_file_integrity, auto_unpack_archive

from .files import (
    CATEGORY_SUBFOLDERS,
    VIDEO_EXTENSIONS,
    get_file_category_and_icon,
    resolve_categorized_path,
    _normalize_match_token,
    resolve_existing_download_path,
    generate_unique_destination_path,
    apply_media_filename_tags,
    open_downloaded_file,
    open_containing_folder,
    atomic_replace_with_retry,
)

__all__ = [
    "MagicBytesDetector",
    "calculate_file_integrity",
    "auto_unpack_archive",
    "get_file_category_and_icon",
    "CATEGORY_SUBFOLDERS",
    "VIDEO_EXTENSIONS",
    "resolve_categorized_path",
    "resolve_existing_download_path",
    "open_downloaded_file",
    "open_containing_folder",
    "generate_unique_destination_path",
    "apply_media_filename_tags",
    "get_base_downloads_dir",
    "atomic_replace_with_retry",
]
