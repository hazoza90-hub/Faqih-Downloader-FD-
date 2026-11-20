"""
File operations subpackage for Faqih Downloader:
- categories: File categorization and extension classification
- path_matcher: On-disk fuzzy search and candidate path resolution
- naming: Non-colliding path generation and filename tags
- shell_open: OS file/directory opening and Explorer highlighting
- atomic_io: Resilient atomic replacement with retry logic
"""
from .categories import (
    CATEGORY_SUBFOLDERS,
    VIDEO_EXTENSIONS,
    get_file_category_and_icon,
    resolve_categorized_path,
)
from .path_matcher import (
    _normalize_match_token,
    resolve_existing_download_path,
)
from .naming import (
    generate_unique_destination_path,
    apply_media_filename_tags,
)
from .shell_open import (
    open_downloaded_file,
    open_containing_folder,
)
from .atomic_io import (
    atomic_replace_with_retry,
)

__all__ = [
    "CATEGORY_SUBFOLDERS",
    "VIDEO_EXTENSIONS",
    "get_file_category_and_icon",
    "resolve_categorized_path",
    "_normalize_match_token",
    "resolve_existing_download_path",
    "generate_unique_destination_path",
    "apply_media_filename_tags",
    "open_downloaded_file",
    "open_containing_folder",
    "atomic_replace_with_retry",
]
