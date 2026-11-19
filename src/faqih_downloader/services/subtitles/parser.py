"""
parser.py: Subtitle format parsing (XML, JSON3, WebVTT, SRT), timestamp conversion, and cue formatting.
"""
import re
import html
import json
from typing import List, Tuple


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
            from ..subtitle_style_engine import normalize_and_dedupe_cues
            cues = normalize_and_dedupe_cues(cues)
        except Exception:
            pass
    return cues


def _format_cues_to_srt(cues: List[Tuple[float, float, str]]) -> str:
    """Formats cues into standard SubRip (.srt) text."""
    if not cues:
        return ""
    try:
        from ..subtitle_style_engine import normalize_and_dedupe_cues
        cues = normalize_and_dedupe_cues(cues)
    except Exception:
        pass
    out: List[str] = []
    for idx, (start, end, body) in enumerate(cues, 1):
        try:
            from ..subtitle_style_engine import sanitize_arabic_subtitle_text
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


def _strip_tlang_param(url: str) -> str:
    """Removes &tlang=... or ?tlang=... query parameter from URL."""
    if not url:
        return ""
    u = re.sub(r'([?&])tlang=[^&]*(&|$)', r'\1', url)
    return u.replace("?&", "?").rstrip("?&")


__all__ = [
    "_format_srt_timestamp",
    "_format_seconds_to_srt",
    "_parse_timestamp_or_seconds",
    "_parse_xml_subtitles_to_srt",
    "_parse_json_subtitles_to_srt",
    "_parse_xml_to_cues",
    "_parse_json_to_cues",
    "_parse_vtt_to_cues",
    "_parse_timedtext_to_cues",
    "_format_cues_to_srt",
    "convert_vtt_to_srt",
    "_strip_tlang_param",
]
