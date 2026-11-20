"""
File destination naming, anti-collision numbering, and media tag formatting for Faqih Downloader.
"""
import os
import re
from typing import Optional, Iterable


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
