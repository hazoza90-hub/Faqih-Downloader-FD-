"""
translator.py: Google Translate GTX endpoint batch subtitle cue translation.
"""
import re
import time
import json
import ssl
import concurrent.futures
import urllib.request
import urllib.parse
from typing import Dict, List, Tuple


def _query_gtx(post_url: str, post_headers: Dict[str, str], text_chunk: str) -> str:
    """Sends a single batch query to the Google GTX endpoint with SSL fallback."""
    if not text_chunk or not text_chunk.strip():
        return ""
    post_data = urllib.parse.urlencode({"q": text_chunk}).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request(post_url, data=post_data, headers=post_headers)
            default_ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=12, context=default_ctx) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                if isinstance(data, list) and data and isinstance(data[0], list):
                    return "".join(part[0] for part in data[0] if part and len(part) > 0 and part[0])
                return ""
        except Exception:
            if attempt < 2:
                time.sleep(0.2 * (attempt + 1))
                continue
            try:
                ctx = ssl._create_unverified_context() if hasattr(ssl, "_create_unverified_context") else None
                req = urllib.request.Request(post_url, data=post_data, headers=post_headers)
                with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(raw)
                    if isinstance(data, list) and data and isinstance(data[0], list):
                        return "".join(part[0] for part in data[0] if part and len(part) > 0 and part[0])
            except Exception:
                pass
            return ""
    return ""


def _translate_sub_batch(
    post_url: str,
    post_headers: Dict[str, str],
    sep: str,
    sub_items: List[Tuple[float, float, str]],
) -> List[Tuple[float, float, str]]:
    """Translates a sub-batch of cues, splitting recursively on delimiter mismatch."""
    if not sub_items:
        return []
    chunk = sep.join(str(c[2]) for c in sub_items)
    try:
        full_trans = _query_gtx(post_url, post_headers, chunk)
        parts = re.split(r'\s*\|\|\|\s*', full_trans) if full_trans else []
        if len(parts) == len(sub_items):
            return [(c[0], c[1], parts[i].strip()) for i, c in enumerate(sub_items)]
    except Exception:
        pass

    # Split mismatch batch into smaller sub-batches of 5 sentences
    if len(sub_items) > 5:
        res: List[Tuple[float, float, str]] = []
        for i in range(0, len(sub_items), 5):
            res.extend(_translate_sub_batch(post_url, post_headers, sep, sub_items[i:i + 5]))
        return res

    res = []
    for c in sub_items:
        single_trans = _query_gtx(post_url, post_headers, str(c[2]))
        res.append((c[0], c[1], single_trans.strip() if single_trans else c[2]))
    return res


def _translate_srt_cues_via_gtx(
    cues: List[Tuple[float, float, str]],
    target_lang: str = "ar"
) -> List[Tuple[float, float, str]]:
    """
    Translates cue texts into target_lang using Google Translate GTX endpoint.
    Batches cues up to ~2500 characters joined by '\\n ||| \\n'.
    """
    if not cues:
        return []

    t_lang = str(target_lang or "ar").strip().lower().split("-")[0].split("_")[0] or "ar"
    sep = "\n ||| \n"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}

    batches: List[List[Tuple[float, float, str]]] = []
    cur_batch: List[Tuple[float, float, str]] = []
    cur_len = 0
    for cue in cues:
        cue_text = str(cue[2] if len(cue) >= 3 else "")
        added_len = len(cue_text) + len(sep)
        if cur_batch and (cur_len + added_len > 2500 or len(cur_batch) >= 40):
            batches.append(cur_batch)
            cur_batch = [cue]
            cur_len = added_len
        else:
            cur_batch.append(cue)
            cur_len += added_len
    if cur_batch:
        batches.append(cur_batch)

    translated_cues: List[Tuple[float, float, str]] = []
    post_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={t_lang}&dt=t"
    post_headers = dict(headers)
    post_headers["Content-Type"] = "application/x-www-form-urlencoded;charset=utf-8"

    if len(batches) <= 1:
        for batch in batches:
            translated_cues.extend(_translate_sub_batch(post_url, post_headers, sep, batch))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for batch_res in pool.map(lambda b: _translate_sub_batch(post_url, post_headers, sep, b), batches):
                translated_cues.extend(batch_res)

    return translated_cues


__all__ = [
    "_translate_srt_cues_via_gtx",
]
