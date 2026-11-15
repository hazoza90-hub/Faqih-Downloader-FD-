"""
Subtitle downloading, VTT/XML/JSON parsing, GTX translation, and SRT persistence.
Decomposed component of subtitle_processor (Stage 8.1 & Stage 9 SRP).
"""
import os
import re
import sys
import time
import html
import json
import threading
import concurrent.futures
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any, Callable

try:
    from ..config import get_setting
except Exception:
    def get_setting(k: str, d: Any = None) -> Any: return d  # type: ignore

try:
    from .media_env_helpers import _resolve_cookie_browser
except Exception:
    try:
        from faqih_downloader.services.media_env_helpers import _resolve_cookie_browser
    except Exception:
        def _resolve_cookie_browser(b: Any) -> Optional[str]: return None

try:
    import requests
except ImportError:
    requests = None

try:
    from .youtube_models import detect_installed_cookie_browsers
except Exception:
    def detect_installed_cookie_browsers() -> List[str]: return ["edge", "chrome", "firefox"]  # type: ignore


def _format_srt_timestamp(ts: str) -> str:
    """Converts MM:SS.mmm, MM:SS,mmm, HH:MM:SS.mmm, or HH:MM:SS,mmm into standard SRT HH:MM:SS,mmm."""
    parts = ts.strip().split(":")
    if len(parts) == 2: h, m, s = "00", parts[0].zfill(2), parts[1]
    elif len(parts) == 3: h, m, s = parts[0].zfill(2), parts[1].zfill(2), parts[2]
    else: return ts
    s = s.replace(",", ".")
    if "." in s:
        sec, ms = s.split(".", 1)
        return f"{h}:{m}:{sec.zfill(2)},{ms[:3].ljust(3, '0')}"
    return f"{h}:{m}:{s.zfill(2)},000"


def _format_seconds_to_srt(seconds: float) -> str:
    """Formats float seconds into SRT timestamp HH:MM:SS,mmm."""
    if seconds < 0: seconds = 0.0
    hrs, mins, secs = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000: secs += 1; ms = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def _parse_timestamp_or_seconds(val: str) -> float:
    """Parses seconds string (e.g. '1.5s', '12.4', '1500ms') or HH:MM:SS.mmm into float seconds."""
    s = str(val or "").strip().replace(",", ".")
    if s.lower().endswith("ms"):
        try: return float(s[:-2].strip()) / 1000.0
        except Exception: return 0.0
    s = s.rstrip("sS")
    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            if len(parts) == 4: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) + float(parts[3]) / 30.0
        except Exception: return 0.0
    try: return float(s)
    except Exception: return 0.0


def _parse_xml_subtitles_to_srt(text: str) -> str:
    """Parses YouTube timedtext XML (<transcript>, <tt>, <text>, <p>) into valid SRT."""
    cues = _parse_xml_to_cues(text)
    return _format_cues_to_srt(cues)


def _parse_json_subtitles_to_srt(text: str) -> str:
    """Parses YouTube json3 timedtext into valid SRT."""
    cues = _parse_json_to_cues(text)
    return _format_cues_to_srt(cues)


def _parse_xml_to_cues(text: str) -> List[Tuple[float, float, str]]:
    """Extracts raw (start_sec, end_sec, text) cues from XML timedtext."""
    cues: List[Tuple[float, float, str]] = []
    tag_pat = re.compile(r'<(?:[a-zA-Z0-9_-]+:)?(?:text|p)\b([^>]*?)>(.*?)</(?:[a-zA-Z0-9_-]+:)?(?:text|p)>', re.DOTALL | re.IGNORECASE)
    attr_pat = re.compile(r'([a-zA-Z0-9_:-]+)\s*=\s*(?:[\'"]([^\'"]*)[\'"]|([^\s>]+))')
    for m in tag_pat.finditer(text):
        attrs = {k: v1 if v1 != "" else v2 for k, v1, v2 in attr_pat.findall(m.group(1))}
        t_val, start_val = attrs.get("t"), attrs.get("start") or attrs.get("begin")
        if not start_val and not t_val: continue
        try:
            start = float(t_val) / 1000.0 if t_val else _parse_timestamp_or_seconds(start_val)
            d_val, dur_val, end_val = attrs.get("d"), attrs.get("dur"), attrs.get("end")
            if d_val: end = start + max(0.5, float(d_val) / 1000.0)
            elif dur_val: end = start + max(0.5, _parse_timestamp_or_seconds(dur_val))
            elif end_val: end = _parse_timestamp_or_seconds(end_val)
            else: end = start + 2.0
            body = html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'</?s\b[^>]*>', '', re.sub(r'<br\s*/?>', '\n', m.group(2), flags=re.IGNORECASE), flags=re.IGNORECASE))).strip()
            if body:
                cues.append((start, end, body))
        except Exception: continue
    return cues


def _parse_json_to_cues(text: str) -> List[Tuple[float, float, str]]:
    """Extracts raw (start_sec, end_sec, text) cues from json3 timedtext."""
    try: data = json.loads(text.lstrip("\ufeff"))
    except Exception: return []
    events = data.get("events")
    if not isinstance(events, list): return []
    cues: List[Tuple[float, float, str]] = []
    for ev in events:
        if not isinstance(ev, dict): continue
        start_ms, dur_ms = ev.get("tStartMs"), ev.get("dDurationMs", 2000)
        if start_ms is None: continue
        start = float(start_ms) / 1000.0
        end = start + max(0.5, float(dur_ms or 2000) / 1000.0)
        segs = ev.get("segs", [])
        body = "".join(str(s.get("utf8", "")) for s in segs if isinstance(s, dict)).strip() if isinstance(segs, list) and segs else str(ev.get("text", "")).strip()
        body = html.unescape(re.sub(r'<[^>]+>', '', body)).strip()
        if body:
            cues.append((start, end, body))
    return cues


def _parse_vtt_to_cues(raw: str) -> List[Tuple[float, float, str]]:
    """Extracts raw (start_sec, end_sec, text) cues from WebVTT or SRT text."""
    blocks = re.split(r'\r?\n\r?\n+', raw)
    cues: List[Tuple[float, float, str]] = []
    timestamp_pat = re.compile(r'((?:\d+:)?\d{1,2}:\d{2}[.,]\d+)\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d+)')
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines: continue
        ts_line_idx, ts_match = -1, None
        for idx, line in enumerate(lines):
            m = timestamp_pat.search(line)
            if m:
                ts_line_idx, ts_match = idx, m
                break
        if ts_line_idx == -1 or not ts_match: continue
        start = _parse_timestamp_or_seconds(ts_match.group(1))
        end = _parse_timestamp_or_seconds(ts_match.group(2))
        cue_lines = lines[ts_line_idx + 1:]
        cleaned = [html.unescape(re.sub(r'<[^>]+>', '', cl)).strip() for cl in cue_lines]
        body = "\n".join(l for l in cleaned if l)
        if body:
            cues.append((start, end, body))
    return cues


def _parse_timedtext_to_cues(raw_text: str) -> List[Tuple[float, float, str]]:
    """Parses any timedtext payload (JSON3, XML, WebVTT, SRT) into [(start_sec, end_sec, text), ...]."""
    raw = str(raw_text or "").lstrip("\ufeff").strip()
    if not raw:
        return []
    cues: List[Tuple[float, float, str]] = []
    if ("\"events\"" in raw or "'events'" in raw) and raw.startswith("{"):
        cues = _parse_json_to_cues(raw)
        if not cues:
            cues = _parse_vtt_to_cues(raw)
    elif any(tag in raw for tag in ("<transcript", "<tt", "<text", "<p")):
        cues = _parse_xml_to_cues(raw)
        if not cues:
            cues = _parse_vtt_to_cues(raw)
    else:
        cues = _parse_vtt_to_cues(raw)

    if cues:
        try:
            from .subtitle_style_engine import normalize_and_dedupe_cues
            cues = normalize_and_dedupe_cues(cues)
        except Exception:
            pass
    return cues


def _format_cues_to_srt(cues: List[Tuple[float, float, str]]) -> str:
    """Formats cues into standard SubRip (.srt) text."""
    if not cues:
        return ""
    try:
        from .subtitle_style_engine import normalize_and_dedupe_cues
        cues = normalize_and_dedupe_cues(cues)
    except Exception:
        pass
    out: List[str] = []
    for idx, (start, end, body) in enumerate(cues, 1):
        try:
            from .subtitle_style_engine import sanitize_arabic_subtitle_text
            body = sanitize_arabic_subtitle_text(body, for_ass=False)
        except Exception:
            pass
        s_str = _format_seconds_to_srt(start)
        e_str = _format_seconds_to_srt(end)
        out.append(f"{idx}\n{s_str} --> {e_str}\n{body}")
    return "\n\n".join(out) + ("\n" if out else "")


def convert_vtt_to_srt(vtt_text: str) -> str:
    """Converts WebVTT, YouTube XML (srv1/srv3/transcript/ttml), or JSON3 into standard SubRip (.srt)."""
    cues = _parse_timedtext_to_cues(vtt_text)
    return _format_cues_to_srt(cues)


def _translate_srt_cues_via_gtx(
    cues: List[Tuple[float, float, str]],
    target_lang: str = "ar"
) -> List[Tuple[float, float, str]]:
    """
    Translates cue texts into target_lang using Google Translate GTX endpoint.
    Batches cues up to ~2500 characters joined by '\n ||| \n'.
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

    def _query_gtx(text_chunk: str) -> str:
        if not text_chunk or not text_chunk.strip():
            return ""
        post_data = urllib.parse.urlencode({"q": text_chunk}).encode("utf-8")
        for attempt in range(3):
            try:
                req = urllib.request.Request(post_url, data=post_data, headers=post_headers)
                import ssl
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
                    import ssl
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

    def _translate_sub_batch(sub_items: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
        if not sub_items:
            return []
        chunk = sep.join(str(c[2]) for c in sub_items)
        try:
            full_trans = _query_gtx(chunk)
            parts = re.split(r'\s*\|\|\|\s*', full_trans) if full_trans else []
            if len(parts) == len(sub_items):
                return [(c[0], c[1], parts[i].strip()) for i, c in enumerate(sub_items)]
        except Exception:
            pass

        # Split mismatch batch into smaller sub-batches of 5 sentences
        if len(sub_items) > 5:
            res: List[Tuple[float, float, str]] = []
            for i in range(0, len(sub_items), 5):
                res.extend(_translate_sub_batch(sub_items[i:i + 5]))
            return res

        res = []
        for c in sub_items:
            single_trans = _query_gtx(str(c[2]))
            res.append((c[0], c[1], single_trans.strip() if single_trans else c[2]))
        return res

    if len(batches) <= 1:
        for batch in batches:
            translated_cues.extend(_translate_sub_batch(batch))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for batch_res in pool.map(_translate_sub_batch, batches):
                translated_cues.extend(batch_res)

    return translated_cues


def _strip_tlang_param(url: str) -> str:
    """Removes &tlang=... or ?tlang=... query parameter from URL."""
    if not url:
        return ""
    u = re.sub(r'([?&])tlang=[^&]*(&|$)', r'\1', url)
    return u.replace("?&", "?").rstrip("?&")


def _fetch_url_direct(url: str, headers: Dict[str, str], timeout: int = 15) -> Optional[str]:
    """Performs direct HTTP GET via requests or urllib."""
    if requests is not None:
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.content.decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        req = urllib.request.Request(url, headers=headers)
        try:
            import ssl
            default_ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=default_ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (ssl.SSLError, urllib.error.URLError, Exception):
            import ssl
            ctx = ssl._create_unverified_context() if hasattr(ssl, "_create_unverified_context") else None
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


_BASE_TIMEDTEXT_LOCK = threading.Lock()
_BASE_TIMEDTEXT_INFLIGHT: Dict[str, threading.Lock] = {}
_BASE_TIMEDTEXT_CACHE: Dict[str, List[Tuple[float, float, str]]] = {}


def _fetch_urls_with_cookies(cand_urls: List[str], headers: Dict[str, str], parse_fn: Callable[[str], Any], timeout: int = 15) -> Any:
    """Attempts fetching candidate URLs using locally installed browser cookies."""
    try:
        import yt_dlp.cookies
        for b in detect_installed_cookie_browsers():
            try: cj = yt_dlp.cookies.extract_cookies_from_browser(b)
            except Exception: cj = None
            if not cj: continue
            hdr = dict(headers)
            try:
                cstr = "; ".join(f"{c.name}={c.value}" for c in cj)
                if cstr: hdr["Cookie"] = cstr
            except Exception: pass
            for u in cand_urls:
                if requests is not None:
                    try:
                        r = requests.get(u, headers=hdr, cookies=cj, timeout=timeout)
                        if r.status_code == 200:
                            res = parse_fn(r.content.decode("utf-8", errors="replace"))
                            if res: return res
                    except Exception: pass
                try:
                    req = urllib.request.Request(u, headers=hdr)
                    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                    with opener.open(req, timeout=timeout) as resp:
                        res = parse_fn(resp.read().decode("utf-8", errors="replace"))
                        if res: return res
                except Exception: pass
    except Exception: pass
    return None


def _fetch_via_ytdlp(webpage_url: str, lang: str, http_headers: Any, parse_fn: Callable[[str], Any]) -> Any:
    """Extracts and parses subtitles via yt_dlp into a temporary directory."""
    try:
        import tempfile, yt_dlp
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts: Dict[str, Any] = {
                "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": [lang], "subtitlesformat": "srt/vtt/ttml/srv3/json3/best",
                "skip_download": True, "quiet": True, "no_warnings": True,
                "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
            }
            cb = _resolve_cookie_browser(get_setting("cookies_browser", "none"))
            if cb: ydl_opts["cookiesfrombrowser"] = (cb,)
            if isinstance(http_headers, dict) and http_headers:
                ydl_opts["http_headers"] = http_headers
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try: ydl.download([webpage_url])
                except Exception: pass
            for fn in os.listdir(tmp_dir):
                fp = os.path.join(tmp_dir, fn)
                if os.path.isfile(fp) and any(fp.endswith(e) for e in (".srt", ".vtt", ".ttml", ".srv3", ".xml", ".json3")):
                    try:
                        with open(fp, "r", encoding="utf-8-sig", errors="replace") as sf:
                            res = parse_fn(sf.read())
                            if res: return res
                    except Exception: pass
    except Exception: pass
    return None


def _base_cache_key(url: str) -> str:
    return re.sub(r'([?&])fmt=[^&]*(&|$)', r'\1', url).replace("?&", "?").rstrip("?&")


def _get_cached_base_cues(base_cand_url: str, sub_track: Dict[str, Any], headers: Dict[str, str]) -> List[Tuple[float, float, str]]:
    """Fetches untranslated base timedtext cues once per base URL and shares via thread-safe cache."""
    cache_key = _base_cache_key(base_cand_url)
    with _BASE_TIMEDTEXT_LOCK:
        if cache_key in _BASE_TIMEDTEXT_CACHE:
            return list(_BASE_TIMEDTEXT_CACHE[cache_key])
        key_lock = _BASE_TIMEDTEXT_INFLIGHT.setdefault(cache_key, threading.Lock())
    with key_lock:
        with _BASE_TIMEDTEXT_LOCK:
            if cache_key in _BASE_TIMEDTEXT_CACHE:
                return list(_BASE_TIMEDTEXT_CACHE[cache_key])
        fmt_urls = [
            re.sub(r'([?&]fmt=)[^&]+', rf'\g<1>{fmt}', base_cand_url) if "fmt=" in base_cand_url
            else f"{base_cand_url}{'&' if '?' in base_cand_url else '?'}fmt={fmt}"
            for fmt in ("vtt", "json3", "srv3", "ttml")
        ]
        _parse_ok = lambda txt: _parse_timedtext_to_cues(txt) if (txt and len(txt.strip()) > 10) else []
        clean_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
        parsed_cues: List[Tuple[float, float, str]] = []
        for test_url in fmt_urls:
            parsed_cues = _parse_ok(_fetch_url_direct(test_url, clean_headers, timeout=10) or "")
            if parsed_cues: break
        if not parsed_cues:
            parsed_cues = _fetch_urls_with_cookies(fmt_urls, dict(headers), _parse_ok, timeout=10) or []
        if not parsed_cues and sub_track.get("webpage_url"):
            qs_lang = urllib.parse.parse_qs(urllib.parse.urlparse(base_cand_url).query).get("lang")
            orig_lang = qs_lang[0] if qs_lang else (sub_track.get("orig_language") or "en")
            parsed_cues = _fetch_via_ytdlp(sub_track["webpage_url"], str(orig_lang), sub_track.get("http_headers"), _parse_ok) or []
        if parsed_cues:
            with _BASE_TIMEDTEXT_LOCK:
                if len(_BASE_TIMEDTEXT_CACHE) >= 64:
                    _BASE_TIMEDTEXT_CACHE.clear()
                _BASE_TIMEDTEXT_CACHE[cache_key] = list(parsed_cues)
        return list(parsed_cues)


def download_subtitle_as_srt(sub_track: Dict[str, Any], video_filepath: str) -> Optional[str]:
    """
    Downloads subtitle, converts VTT/XML/JSON to SRT, and saves alongside video in pure UTF-8.
    Tries fallback_urls, browser cookies, and deterministic base timedtext URL with GTX translation.
    Never writes .srt if srt_content is empty or lacks '-->' timing.
    """
    if not sub_track or sub_track.get("sub_id") in (None, "none"):
        return None

    primary_url = sub_track.get("url") or ""
    fallbacks = sub_track.get("fallback_urls") or []
    cand_urls = [u for u in [primary_url] + fallbacks if u]
    if not cand_urls and not sub_track.get("base_url"):
        return None

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
    if isinstance(sub_track.get("http_headers"), dict):
        headers.update(sub_track["http_headers"])

    def _convert(txt: Optional[str]) -> str:
        if not txt or not txt.strip(): return ""
        c = convert_vtt_to_srt(txt)
        return c if c and "-->" in c else (txt if "-->" in txt else "")

    # Phase 1: Try candidate URLs directly (share base cache when URL matches base_url)
    base_ref_key = _base_cache_key(sub_track["base_url"]) if sub_track.get("base_url") else ""
    srt_content = ""
    for u in cand_urls:
        if base_ref_key and "tlang=" not in u and _base_cache_key(u) == base_ref_key:
            cached_cues = _get_cached_base_cues(u, sub_track, headers)
            if cached_cues:
                srt_content = _format_cues_to_srt(cached_cues)
                break
        srt_content = _convert(_fetch_url_direct(u, headers))
        if srt_content: break

    has_tlang = any("tlang=" in u for u in cand_urls) or bool(sub_track.get("base_url") and sub_track.get("base_url") != primary_url)

    # Phase 2: Try browser cookies if available (skip for &tlang= to jump straight to Phase 4 GTX)
    if not srt_content and not has_tlang:
        srt_content = _fetch_urls_with_cookies(cand_urls, headers, _convert, timeout=15) or ""

    # Phase 3: Try yt_dlp subprocess/temporary directory if webpage_url exists (skip for &tlang=)
    if not srt_content and not has_tlang and sub_track.get("webpage_url"):
        srt_content = _fetch_via_ytdlp(sub_track["webpage_url"], sub_track.get("language") or "en", sub_track.get("http_headers"), _convert) or ""

    # Phase 4: Deterministic fallback for YouTube &tlang= HTTP 429 rate-limiting
    if not srt_content:
        base_cand_url = sub_track.get("base_url") or next((_strip_tlang_param(u) for u in cand_urls if "tlang=" in u), "")
        if base_cand_url:
            parsed_cues = _get_cached_base_cues(base_cand_url, sub_track, headers)
            if parsed_cues:
                target_lang = str(sub_track.get("language") or "ar").lower().split("-")[0].split("_")[0] or "ar"
                base_qs = urllib.parse.parse_qs(urllib.parse.urlparse(base_cand_url).query)
                base_src_lang = str((base_qs.get("lang") or [""])[0]).lower().split("-")[0].split("_")[0]
                if base_src_lang and target_lang == base_src_lang:
                    srt_content = _format_cues_to_srt(parsed_cues)
                else:
                    translated_cues = _translate_srt_cues_via_gtx(parsed_cues, target_lang=target_lang)
                    if translated_cues:
                        srt_content = _format_cues_to_srt(translated_cues)

    if not srt_content or "-->" not in srt_content:
        return None

    stem = os.path.splitext(video_filepath)[0]
    srt_lang = re.sub(r'[-_]orig$', '', str(sub_track.get('language') or 'sub'), flags=re.IGNORECASE) or 'sub'
    srt_path = f"{stem}.{srt_lang}.srt"
    try:
        srt_dir = os.path.dirname(os.path.abspath(srt_path))
        if srt_dir:
            os.makedirs(srt_dir, exist_ok=True)
        with open(srt_path, "w", encoding="utf-8-sig") as f:
            f.write(srt_content)
        return srt_path
    except Exception:
        return None

