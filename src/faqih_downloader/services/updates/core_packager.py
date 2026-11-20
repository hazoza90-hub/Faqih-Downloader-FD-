"""
Core Hot-Patch Packager: builds lightweight CorePatch.zip bundles in <0.5s.
"""
import os
import json
import time
import zipfile
import tempfile
import threading
from typing import Optional

from .constants import APP_NAME, APP_ID, APP_VERSION


def build_core_patch_zip(
    output_path: Optional[str] = None,
    src_dir: Optional[str] = None,
    version: Optional[str] = None
) -> str:
    """Packages src/faqih_downloader into lightweight CorePatch.zip in <0.5s."""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(), "FaqihDownloader-CorePatch.zip")
    out_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    if not src_dir:
        cur_file = os.path.abspath(__file__)
        # updates/core_packager.py -> services -> faqih_downloader (3 parents up)
        candidates = [
            os.path.dirname(os.path.dirname(os.path.dirname(cur_file))),
            os.path.dirname(os.path.dirname(cur_file)),
        ]
        src_pkg = next(
            (c for c in candidates if os.path.basename(c) in ("faqih_downloader", "smart_download")),
            None,
        )
        if not src_pkg:
            src_pkg = os.path.join(os.getcwd(), "src", "faqih_downloader")
            if not os.path.isdir(src_pkg):
                src_pkg = os.path.join(os.getcwd(), "src", "smart_download")
    else:
        src_dir_abs = os.path.abspath(src_dir)
        if os.path.basename(src_dir_abs) in ("faqih_downloader", "smart_download"):
            src_pkg = src_dir_abs
        else:
            src_pkg = os.path.join(src_dir_abs, "faqih_downloader")
            if not os.path.isdir(src_pkg):
                src_pkg = os.path.join(src_dir_abs, "smart_download")

    if not os.path.isdir(src_pkg):
        raise FileNotFoundError(f"Core package directory not found at: {src_pkg}")

    ver_raw = str(version or APP_VERSION).strip()
    ver_clean = ver_raw.lstrip("vV").strip() or APP_VERSION
    manifest_data = {
        "version": ver_clean,
        "app_name": APP_NAME,
        "app_id": APP_ID,
        "created_at": int(time.time()),
        "release_tag": f"v{ver_clean}"
    }
    manifest_json = json.dumps(manifest_data, indent=2).encode("utf-8")

    part_out = f"{out_abs}.part_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}"
    with zipfile.ZipFile(part_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("core_version.json", manifest_json)
        zf.writestr("faqih_downloader/core_version.json", manifest_json)
        zf.writestr("smart_download/core_version.json", manifest_json)

        for root, dirs, files in os.walk(src_pkg):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".pytest_cache")]
            for f in sorted(files):
                if f.endswith((".py", ".json")):
                    full_p = os.path.join(root, f)
                    rel_to_pkg = os.path.relpath(full_p, src_pkg)
                    zf.write(full_p, os.path.join("faqih_downloader", rel_to_pkg).replace("\\", "/"))
        zf.writestr("smart_download/__init__.py", b"from faqih_downloader import *\n")

    os.replace(part_out, out_abs)
    return out_abs
