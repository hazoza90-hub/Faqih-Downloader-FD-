"""
cue_ops.py: Subtitle cue editing, clip time-filtering/shifting, bilingual cue merging, clean track cloning, and SRT export.
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional, Tuple, Any


def apply_custom_cue_edits(cues: list, custom_edits: Optional[Dict[str, Any]]) -> list:
    """Applies user-edited subtitle texts from the preview studio to cue items."""
    if not cues or not custom_edits: return cues
    edits = {str(k).strip(): str(v) for k, v in custom_edits.items()}
    updated = []
    for idx, item in enumerate(cues):
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s, e, text = float(item[0]), float(item[1]), str(item[2])
        else: updated.append(item); continue
        matched = None
        for k in (str(idx), f"{s:.2f}", f"{s:.3f}", text.strip()):
            if k in edits: matched = edits[k]; break
        new_text = matched if matched is not None else text
        if is_dict: d = dict(item); d["text"] = new_text; updated.append(d)
        else: updated.append((s, e, new_text))
    return updated


def clone_clean_subtitle_track(trk: Any) -> dict:
    """Clones subtitle track dict while stripping nested style_config and secondary_track to prevent circular references."""
    if not isinstance(trk, dict): return {}
    return {k: v for k, v in trk.items() if k not in ("style_config", "secondary_track")}


def filter_and_shift_cues_for_clip(cues: list, clip_start: float, clip_end: float) -> list:
    """Filters cues overlapping [clip_start, clip_end] and shifts timestamps to start at 00:00."""
    if not cues or clip_end <= clip_start or clip_start < 0: return cues
    shifted = []
    for item in cues:
        s, e, text = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s, e, text = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s, e, text = float(item[0]), float(item[1]), str(item[2])
        else: continue
        if e > clip_start and s < clip_end:
            new_s = max(0.0, round(s - clip_start, 3))
            new_e = min(round(clip_end - clip_start, 3), round(e - clip_start, 3))
            if new_e > new_s + 0.01:
                if is_dict: d = dict(item); d["start"] = new_s; d["end"] = new_e; shifted.append(d)
                else: shifted.append((new_s, new_e, text))
    return shifted


def merge_bilingual_cues(primary_cues: list, secondary_cues: list) -> list:
    """Merges secondary subtitle cues into primary cues with [[DUAL]] separator for bilingual display."""
    if not primary_cues: return []
    if not secondary_cues: return primary_cues
    sec_extracted: List[Tuple[float, float, str]] = []
    for item in secondary_cues:
        if isinstance(item, dict): sec_extracted.append((float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: sec_extracted.append((float(item[0]), float(item[1]), str(item[2])))

    merged = []
    for item in primary_cues:
        s1, e1, t1 = 0.0, 0.0, ""
        is_dict = isinstance(item, dict)
        if is_dict: s1, e1, t1 = float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 3: s1, e1, t1 = float(item[0]), float(item[1]), str(item[2])
        else: merged.append(item); continue

        matching_sec, best_sec, best_ol = [], "", 0.0
        for s2, e2, t2 in sec_extracted:
            overlap = max(0.0, min(e1, e2) - max(s1, s2))
            sec_dur = max(0.1, e2 - s2)
            if (overlap > 0.2 and overlap / sec_dur > 0.25) or (overlap > 0.6):
                t2c = t2.strip()
                if t2c and t2c not in matching_sec: matching_sec.append(t2c)
            if overlap > 0.05 and overlap > best_ol and t2.strip():
                best_ol, best_sec = overlap, t2.strip()
        comb_sec = " ".join(matching_sec).strip() if matching_sec else best_sec
        comb = f"{t1.strip()}\n[[DUAL]]{comb_sec}" if comb_sec else t1.strip()
        if is_dict: d = dict(item); d["text"] = comb; merged.append(d)
        else: merged.append((s1, e1, comb))
    return merged


def export_cues_to_srt(cues: list, output_srt_path: str) -> bool:
    """Exports cues list to UTF-8 SRT file with [[DUAL]] rendered as clean secondary line."""
    if not cues: return False
    try: from ..subtitles.parser import _format_seconds_to_srt
    except Exception:
        try: from ..subtitle_downloader import _format_seconds_to_srt
        except Exception:
            def _format_seconds_to_srt(sec: float) -> str:
                s_i, ms = int(sec), int(round((sec - int(sec)) * 1000))
                if ms >= 1000: s_i += 1; ms = 0
                return f"{s_i // 3600:02d}:{(s_i % 3600) // 60:02d}:{s_i % 60:02d},{ms:03d}"
    lines, idx = [], 1
    for item in cues:
        s, e, text = (float(item.get("start", 0)), float(item.get("end", 0)), str(item.get("text", ""))) if isinstance(item, dict) else ((float(item[0]), float(item[1]), str(item[2])) if isinstance(item, (tuple, list)) and len(item) >= 3 else (0.0, 0.0, ""))
        clean = text.replace("\n[[DUAL]]", "\n").replace("[[DUAL]]", "\n").strip()
        if not clean or e <= s: continue
        lines.append(f"{idx}\n{_format_seconds_to_srt(s)} --> {_format_seconds_to_srt(e)}\n{clean}\n"); idx += 1
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_srt_path)), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f: f.write("\n".join(lines).strip() + "\n")
        return True
    except Exception: return False


__all__ = [
    "apply_custom_cue_edits",
    "clone_clean_subtitle_track",
    "filter_and_shift_cues_for_clip",
    "merge_bilingual_cues",
    "export_cues_to_srt",
]
