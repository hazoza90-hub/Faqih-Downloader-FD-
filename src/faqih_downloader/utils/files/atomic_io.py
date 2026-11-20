"""
Atomic file replacement and retry utilities for Faqih Downloader.
"""
import os
import time
import shutil


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
                    shutil.copyfile(src_path, dst_path)
                    os.unlink(src_path)
                    return
                except Exception:
                    raise e
            time.sleep(retry_delay)
