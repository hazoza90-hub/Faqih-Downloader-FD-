"""
Subtitle Style Engine (subtitle_style_engine.py).
Provides professional subtitle formatting: YouTube roll-up deduplication,
overlap elimination, Arabic NFC & ligature/notdef box glyph sanitization,
terminal punctuation reordering for libass, and 1:1 preview-matching ASS generation.
"""
from __future__ import annotations
import os, re, unicodedata, subprocess
from typing import List, Tuple, Dict, Any, Optional

INVISIBLE_CHARS_REGEX = re.compile(r'[\u200b-\u200f\ufeff\u202a-\u202e\u2066-\u2069\u00ad]')
ARABIC_CHAR_REGEX = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
NEUTRAL_TERMINAL_PUNCT_REGEX = re.compile(r'([\.\!\:\;\,\—\…\?\-]+\s*)$')


def format_ass_timestamp(seconds: float) -> str:
    """Formats float seconds into standard ASS timestamp H:MM:SS.cc (centiseconds)."""
    if seconds < 0: seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100: secs += 1; cs = 0
    if secs >= 60: mins += 1; secs = 0
    if mins >= 60: hrs += 1; mins = 0
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"


def parse_srt_timestamp_to_seconds(ts: str) -> float:
    """Parses HH:MM:SS,mmm or HH:MM:SS.mmm into float seconds."""
    s = str(ts or "").strip().replace(",", ".")
    parts = s.split(":")
    try:
        if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except Exception: pass
    try: return float(s)
    except Exception: return 0.0


def normalize_and_dedupe_cues(
    cues: List[Tuple[float, float, str]],
    max_words: int = 14
) -> List[Tuple[float, float, str]]:
    """Deduplicates roll-up lines, prevents overlaps, and caps cues at 2 lines / max_words."""
    if not cues: return []
    cleaned: List[Tuple[float, float, str]] = []
    for s, e, text in cues:
        t = (text or "").strip()
        if t and e > s: cleaned.append((float(s), float(e), t))
    if not cleaned: return []
    cleaned.sort(key=lambda c: (c[0], c[1]))

    deduped: List[Tuple[float, float, str]] = []
    for s, e, text in cleaned:
        if not deduped:
            deduped.append((s, e, text)); continue
        prev_s, prev_e, prev_text = deduped[-1]
        prev_lines = [l.strip() for l in prev_text.splitlines() if l.strip()]
        cur_lines = [l.strip() for l in text.splitlines() if l.strip()]
        if prev_lines and cur_lines:
            if cur_lines[0] == prev_lines[-1]: cur_lines = cur_lines[1:]
            elif len(cur_lines) > 1 and "\n".join(cur_lines).startswith(prev_text):
                cur_lines = [l.strip() for l in "\n".join(cur_lines)[len(prev_text):].splitlines() if l.strip()]
        new_text = "\n".join(cur_lines).strip()
        if not new_text:
            if e > prev_e: deduped[-1] = (prev_s, e, prev_text)
            continue
        deduped.append((s, e, new_text))

    split_cues: List[Tuple[float, float, str]] = []
    for s, e, text in deduped:
        dur = max(0.2, e - s)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) > 2:
            chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
            chunk_dur = dur / len(chunks)
            for idx, ch in enumerate(chunks):
                cs = s + idx * chunk_dur
                split_cues.append((cs, cs + chunk_dur, ch))
            continue
        words = text.split()
        if len(words) > max_words:
            mid = len(words) // 2
            t_mid = s + dur / 2.0
            split_cues.append((s, t_mid - 0.02, " ".join(words[:mid])))
            split_cues.append((t_mid, e, " ".join(words[mid:])))
            continue
        split_cues.append((s, e, text))

    final_cues: List[Tuple[float, float, str]] = []
    for i in range(len(split_cues)):
        cur_s, cur_e, cur_t = split_cues[i]
        if i + 1 < len(split_cues):
            next_s = split_cues[i + 1][0]
            if cur_e >= next_s: cur_e = max(cur_s + 0.1, next_s - 0.02)
        final_cues.append((cur_s, cur_e, cur_t))
    return final_cues


def sanitize_arabic_subtitle_text(text: str, for_ass: bool = False) -> str:
    """Normalizes NFC, strips invisible box chars, and reorders terminal punctuation for libass."""
    if not text: return ""
    norm = unicodedata.normalize("NFC", text)
    clean = INVISIBLE_CHARS_REGEX.sub("", norm)
    if not for_ass: return clean

    lines = clean.splitlines()
    processed: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and ARABIC_CHAR_REGEX.search(stripped):
            m = NEUTRAL_TERMINAL_PUNCT_REGEX.search(stripped)
            if m:
                punct, core = m.group(1).strip(), stripped[:m.start()].strip()
                line = f"{punct}{core}" if punct and core else stripped
            else:
                line = stripped
        processed.append(line if stripped else "")
    return "\n".join(processed)


def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """Converts '#RRGGBB' or 'RRGGBB' into ASS '&HAABBGGRR' format."""
    h = str(hex_str or "").strip().lstrip("#")
    if len(h) == 6:
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"&H{max(0, min(255, alpha)):02X}{b:02X}{g:02X}{r:02X}"
        except Exception: pass
    return f"&H{alpha:02X}FFFFFF"


def probe_video_dimensions(video_path: str, ffmpeg_path: Optional[str] = None) -> Tuple[int, int]:
    """Probes video (width, height) using FFmpeg; defaults to (1920, 1080)."""
    if not video_path or not os.path.isfile(video_path): return (1920, 1080)
    ff = ffmpeg_path
    if not ff:
        try:
            from .youtube_models import find_ffmpeg_bin
            ff = find_ffmpeg_bin()
        except Exception:
            import shutil; ff = shutil.which("ffmpeg")
    if not ff: return (1920, 1080)
    try:
        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        cmd = [ff, "-hide_banner", "-i", os.path.abspath(video_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=cflags, timeout=10)
        m = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', res.stderr)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if w > 0 and h > 0: return (w, h)
    except Exception: pass
    return (1920, 1080)


def _parse_srt_text_to_cues(content: str) -> List[Tuple[float, float, str]]:
    """Extracts (start, end, text) cues from SRT text."""
    blocks = re.split(r'\r?\n\r?\n+', content.strip())
    cues: List[Tuple[float, float, str]] = []
    ts_pat = re.compile(r'((?:\d+:)?\d{1,2}:\d{2}[.,]\d+)\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d+)')
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines: continue
        ts_idx, m = -1, None
        for i, line in enumerate(lines):
            match = ts_pat.search(line)
            if match: ts_idx, m = i, match; break
        if ts_idx == -1 or not m: continue
        body = "\n".join(lines[ts_idx + 1:])
        if body: cues.append((parse_srt_timestamp_to_seconds(m.group(1)), parse_srt_timestamp_to_seconds(m.group(2)), body))
    return cues


def generate_styled_ass_file(
    srt_source: Any,
    output_ass_path: str,
    video_path: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    preset: str = "youtube",
    font_scale: float = 1.0,
    text_color: str = "#FFFFFF",
    bg_mode: str = "box",
    pos_x: float = 50.0,
    pos_y: float = 86.0,
    subtitle_position: Optional[str] = None,
    font_name: str = "Arial",
    **kwargs
) -> bool:
    """Generates ASS subtitle file with 1:1 preview styling and coordinates."""
    vid_w, vid_h = (width or 0), (height or 0)
    if vid_w <= 0 or vid_h <= 0:
        vid_w, vid_h = probe_video_dimensions(video_path, ffmpeg_path=ffmpeg_path) if (video_path and os.path.isfile(video_path)) else (1920, 1080)

    sub_pos = str(subtitle_position or "").strip().lower()
    if sub_pos and pos_y == 86.0:
        pos_y = 12.0 if sub_pos == "top" else (50.0 if sub_pos == "middle" else 86.0)

    px, py = int(vid_w * (pos_x / 100.0)), int(vid_h * (pos_y / 100.0))
    scale = max(0.6, min(1.6, float(font_scale or 1.0)))
    ref_dim = min(vid_w, vid_h)
    p_name = str(preset or "youtube").strip().lower()

    if p_name == "tiktok":
        border_style, outline, shadow = 1, 4, 2
        prim_col, back_col, out_col = "&H00FFFFFF", "&H00000000", "&H00000000"
        font_size = int(ref_dim * 0.045 * scale)
    elif p_name == "golden":
        border_style, outline, shadow = 3, 10, 0
        prim_col, back_col, out_col = "&H0000D7FF", "&H64000000", "&H64000000"
        font_size = int(ref_dim * 0.042 * scale)
    elif p_name == "custom":
        prim_col = hex_to_ass_color(text_color, alpha=0)
        is_box = str(bg_mode or "box").lower() == "box"
        border_style, outline, shadow = (3, 10, 0) if is_box else (1, 4, 2)
        back_col, out_col = ("&H64000000", "&H64000000") if is_box else ("&H00000000", "&H00000000")
        font_size = int(ref_dim * 0.042 * scale)
    else:  # youtube
        border_style, outline, shadow = 3, 10, 0
        prim_col, back_col, out_col = "&H00FFFFFF", "&H64000000", "&H64000000"
        font_size = int(ref_dim * 0.042 * scale)

    cues: List[Tuple[float, float, str]] = []
    if isinstance(srt_source, list): cues = srt_source
    elif isinstance(srt_source, str):
        if os.path.isfile(srt_source):
            with open(srt_source, "r", encoding="utf-8-sig", errors="replace") as f:
                cues = _parse_srt_text_to_cues(f.read())
        else: cues = _parse_srt_text_to_cues(srt_source)

    norm_cues = normalize_and_dedupe_cues(cues, max_words=8 if p_name == "tiktok" else 14)
    lines = [
        "[Script Info]", "Title: Faqih Downloader Styled Subtitle", "ScriptType: v4.00+", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.601", f"PlayResX: {vid_w}", f"PlayResY: {vid_h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{prim_col},&H000000FF,{out_col},{back_col},1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},5,20,20,20,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for s, e, body in norm_cues:
        s_str, e_str = format_ass_timestamp(s), format_ass_timestamp(e)
        sanitized = sanitize_arabic_subtitle_text(body, for_ass=True)
        ass_body = sanitized.replace("\r\n", "\\N").replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{s_str},{e_str},Default,,0,0,0,,{{\\an5\\pos({px},{py})}}{ass_body}")

    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return True
    except Exception: return False
