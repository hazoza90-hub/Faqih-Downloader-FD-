"""
Structured data models and filename/filesize formatting helpers for YouTube & social media streams.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .constants import INVALID_FILENAME_CHARS


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """
    Sanitizes a string to make it safe for use as a filesystem filename across OSes.
    Removes reserved characters and trims leading/trailing dots and spaces.
    """
    if not name:
        return "youtube_download"
    name = "".join(c for c in name if ord(c) <= 0xFFFF and c != "\ufffd")
    cleaned = INVALID_FILENAME_CHARS.sub("_", name)
    cleaned = re.sub(r'[\s_]+', ' ', cleaned).strip(" .")
    if not cleaned:
        cleaned = "youtube_download"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned


@dataclass
class VideoFormatOption:
    """
    Structured representation of a selectable download quality/format option
    for presentation in the quality selection modal and execution by the downloader.
    """
    format_id: str                      # Identifier e.g. '137+140', '22', '140'
    resolution_label: str               # e.g. '4K (2160p)', '1080p (Full HD)', '720p (HD)', 'Audio Only (M4A)'
    height: int                         # Vertical height in pixels (0 for audio-only)
    ext: str                            # Target container extension e.g. 'mp4', 'm4a', 'webm'
    filesize_approx: int                # Total estimated bytes (video + audio if merged)
    fps: int = 30                       # Framerate if video
    vcodec: str = ""                    # Video codec name
    acodec: str = ""                    # Audio codec name
    is_progressive: bool = False        # True if single stream with multiplexed audio
    is_audio_only: bool = False         # True if stream contains audio only
    video_url: str = ""                 # URL for video stream (or audio stream if audio-only)
    video_headers: Dict[str, str] = field(default_factory=dict)
    audio_url: Optional[str] = None     # Paired audio stream URL if split/adaptive
    audio_headers: Dict[str, str] = field(default_factory=dict)
    audio_ext: str = "m4a"
    audio_size: int = 0
    note: str = ""                      # Human-readable note e.g. "60 FPS • Lossless Merge (FFmpeg)"
    selected_audio_track: Optional[Dict[str, Any]] = None
    selected_subtitle_track: Optional[Dict[str, Any]] = None
    subtitle_embed_mode: str = "soft_embed"
    subtitle_position: str = "bottom"
    subtitle_preset: str = "youtube"
    subtitle_font_scale: float = 1.0
    subtitle_text_color: str = "#FFFFFF"
    subtitle_bg_mode: str = "box"
    subtitle_pos_x: float = 50.0
    subtitle_pos_y: float = 86.0
    clip_start_sec: float = 0.0
    clip_end_sec: float = 0.0
    subtitle_custom_edits: Dict[str, str] = field(default_factory=dict)
    dual_subtitle_enabled: bool = False
    secondary_subtitle_track: Optional[Dict[str, Any]] = None
    audio_boost_enabled: bool = False
    selected_chapter_title: str = ""
    external_subtitle_tracks: List[Dict[str, Any]] = field(default_factory=list)


def format_filesize(num_bytes: int) -> str:
    """Formats raw byte count into human-readable units (e.g., '142.5 MB')."""
    if not num_bytes or num_bytes <= 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_idx]}"


@dataclass
class YouTubeStreamInfo:
    """
    Resolved metadata and stream URLs for YouTube and social media streams.
    """
    video_id: str
    title: str
    clean_filename: str
    is_progressive: bool  # True if audio and video are already multiplexed in a single stream
    video_url: str
    video_headers: Dict[str, str] = field(default_factory=dict)
    video_ext: str = "mp4"
    video_resolution: str = "720p"
    video_size: int = 0
    audio_url: Optional[str] = None
    audio_headers: Dict[str, str] = field(default_factory=dict)
    audio_ext: str = "m4a"
    audio_size: int = 0
    duration: int = 0
    thumbnail_url: str = ""
    is_audio_only: bool = False
    platform: str = "YouTube"
    subtitle_track: Optional[Dict[str, Any]] = None
    audio_language: Optional[str] = None
    subtitle_embed_mode: str = "soft_embed"
    subtitle_position: str = "bottom"
    subtitle_preset: str = "youtube"
    subtitle_font_scale: float = 1.0
    subtitle_text_color: str = "#FFFFFF"
    subtitle_bg_mode: str = "box"
    subtitle_pos_x: float = 50.0
    subtitle_pos_y: float = 86.0
    webpage_url: str = ""
    audio_format_id: str = ""
    clip_start_sec: float = 0.0
    clip_end_sec: float = 0.0
    subtitle_custom_edits: Dict[str, str] = field(default_factory=dict)
    dual_subtitle_enabled: bool = False
    secondary_subtitle_track: Optional[Dict[str, Any]] = None
    audio_boost_enabled: bool = False
    selected_chapter_title: str = ""
    external_subtitle_tracks: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if self.subtitle_track and isinstance(self.subtitle_track, dict):
            sc = self.subtitle_track.get("style_config")
            if isinstance(sc, dict):
                if "preset" in sc: self.subtitle_preset = str(sc["preset"])
                if "font_scale" in sc: self.subtitle_font_scale = float(sc["font_scale"])
                if "text_color" in sc: self.subtitle_text_color = str(sc["text_color"])
                if "bg_mode" in sc: self.subtitle_bg_mode = str(sc["bg_mode"])
                if "pos_x" in sc: self.subtitle_pos_x = float(sc["pos_x"])
                if "pos_y" in sc: self.subtitle_pos_y = float(sc["pos_y"])
                if "subtitle_position" in sc: self.subtitle_position = str(sc["subtitle_position"])
                if "clip_start" in sc and not self.clip_start_sec: self.clip_start_sec = float(sc["clip_start"])
                if "clip_end" in sc and not self.clip_end_sec: self.clip_end_sec = float(sc["clip_end"])
                if "custom_edits" in sc and not self.subtitle_custom_edits: self.subtitle_custom_edits = dict(sc["custom_edits"])
                if "dual_sub" in sc: self.dual_subtitle_enabled = bool(sc["dual_sub"])
                if "secondary_track" in sc: self.secondary_subtitle_track = sc["secondary_track"]
                if "audio_boost" in sc and not self.audio_boost_enabled: self.audio_boost_enabled = bool(sc["audio_boost"])
                if "chapter_title" in sc and not self.selected_chapter_title: self.selected_chapter_title = str(sc["chapter_title"])


# Clean alias
MediaStreamInfo = YouTubeStreamInfo


def resolve_preferred_option_index(options: List[Any]) -> int:
    """Helper resolving preferred format index using user settings."""
    try:
        from ...ui.modals.quality_modal_helpers import resolve_preferred_option_index as _res
        return _res(options)
    except Exception:
        try:
            from faqih_downloader.ui.modals.quality_modal_helpers import resolve_preferred_option_index as _res
            return _res(options)
        except Exception:
            return 0
