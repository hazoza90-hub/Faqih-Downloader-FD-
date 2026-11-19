"""
audio_recovery.py: Audio stream completeness validation and yt-dlp fallback recovery.
"""
import os
import sys
import shutil
from typing import Dict, Optional, Callable, Any

from .browser_cookies import _resolve_cookie_browser
from .ffmpeg_probe import probe_media_file_duration


def ensure_complete_audio_file(
    stream_info: Any,
    audio_tmp: str,
    tag: str = "Media",
    on_log: Optional[Callable[[str], None]] = None,
    has_prior_error: bool = False,
    find_ffmpeg_fn: Optional[Callable[[], Optional[str]]] = None,
    probe_duration_fn: Optional[Callable[[str], float]] = None,
    recover_fn: Optional[Callable[..., bool]] = None,
) -> bool:
    """Verifies audio stream completeness and duration; triggers yt-dlp fallback if truncated or missing."""
    meh = sys.modules.get("faqih_downloader.services.media_env_helpers")
    eff_probe_fn = probe_duration_fn
    if eff_probe_fn is None:
        meh_probe = getattr(meh, "probe_media_file_duration", None) if meh else None
        if meh_probe is not None and meh_probe is not probe_media_file_duration:
            eff_probe_fn = meh_probe
        else:
            eff_probe_fn = lambda p: probe_media_file_duration(p, find_ffmpeg_fn=find_ffmpeg_fn)
    eff_recover_fn = recover_fn or (getattr(meh, "recover_audio_stream_fallback", recover_audio_stream_fallback) if meh else recover_audio_stream_fallback)

    cur_sz = os.path.getsize(audio_tmp) if os.path.isfile(audio_tmp) else 0
    exp_dur = float(getattr(stream_info, "duration", 0) or 0)
    exp_sz = int(getattr(stream_info, "audio_size", 0) or 0)
    if not has_prior_error and cur_sz >= 1024 and exp_sz > 0 and cur_sz >= int(0.90 * exp_sz):
        return True
    a_dur = eff_probe_fn(audio_tmp) if cur_sz > 0 else 0.0

    is_trunc = has_prior_error or (cur_sz < 1024)
    if not is_trunc and exp_dur > 15:
        if a_dur > 0 and a_dur < (0.85 * exp_dur):
            is_trunc = True
        elif a_dur == 0 and exp_sz > 0 and cur_sz < (0.85 * exp_sz):
            is_trunc = True

    if is_trunc:
        if on_log:
            on_log(f"[{tag}] Audio stream missing, failed or incomplete ({cur_sz:,} bytes). Triggering yt-dlp fallback...")
        return eff_recover_fn(stream_info, audio_tmp, on_log=on_log)
    return True


def recover_audio_stream_fallback(stream_info: Any, audio_tmp: str, on_log: Optional[Callable[[str], None]] = None) -> bool:
    """Fallback audio downloader via yt_dlp directly to audio_tmp when stream is truncated."""
    try:
        import yt_dlp
        try:
            from ...config import get_setting
        except ImportError:
            from faqih_downloader.config import get_setting
        cb = _resolve_cookie_browser(get_setting("cookies_browser", "none"))
        target_url = getattr(stream_info, "webpage_url", "") or ""
        v_id = getattr(stream_info, "video_id", "")
        if not target_url and v_id:
            target_url = f"https://www.youtube.com/watch?v={v_id}"
        if not target_url:
            return False

        fmt_id = str(getattr(stream_info, "audio_format_id", "") or "").strip()
        lang = getattr(stream_info, "audio_language", None)
        if fmt_id:
            fmt_spec = f"{fmt_id}/bestaudio[language={lang}]/bestaudio" if lang else f"{fmt_id}/bestaudio"
        elif lang:
            fmt_spec = f"bestaudio[language={lang}]/bestaudio"
        else:
            fmt_spec = "bestaudio"

        ydl_opts: Dict[str, Any] = {
            "format": fmt_spec,
            "outtmpl": audio_tmp,
            "overwrites": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": ["android_vr", "tv", "web"]}},
        }
        if cb:
            ydl_opts["cookiesfrombrowser"] = (cb,)
        if hasattr(stream_info, "audio_headers") and stream_info.audio_headers:
            ydl_opts["http_headers"] = stream_info.audio_headers

        if on_log:
            on_log(f"[AUDIO FALLBACK] Downloading complete audio track ({fmt_id or lang or 'default'}) via yt-dlp...")
        if os.path.exists(audio_tmp):
            try: os.remove(audio_tmp)
            except Exception: pass

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])

        if not os.path.exists(audio_tmp):
            d_dir = os.path.dirname(audio_tmp) or "."
            b_name = os.path.basename(audio_tmp)
            for f in os.listdir(d_dir):
                if f.startswith(b_name) and os.path.isfile(os.path.join(d_dir, f)):
                    shutil.move(os.path.join(d_dir, f), audio_tmp)
                    break
        ok = os.path.isfile(audio_tmp) and os.path.getsize(audio_tmp) > 1024
        if on_log and ok:
            on_log(f"[AUDIO FALLBACK SUCCESS] Full audio track restored ({os.path.getsize(audio_tmp):,} bytes)!")
        return ok
    except Exception as e:
        if on_log:
            on_log(f"[AUDIO FALLBACK FAILED] {e}")
        return False


__all__ = [
    "ensure_complete_audio_file",
    "recover_audio_stream_fallback",
]
