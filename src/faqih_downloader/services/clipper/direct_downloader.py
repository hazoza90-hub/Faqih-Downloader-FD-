"""
direct_downloader.py: Direct FFmpeg HTTP-range clipped stream downloading and progress tracking.
"""
from __future__ import annotations
import os
import re
import sys
import time
import shutil
import subprocess
from typing import Dict, Optional, Callable, Any

from .state_sync import estimate_clip_total_bytes
from .process_control import _set_process_suspended


def _format_ffmpeg_headers(headers: Optional[Dict[str, str]]) -> str:
    """Formats a dict of HTTP headers into a CRLF-separated string for FFmpeg -headers."""
    return "".join(f"{k}: {v}\r\n" for k, v in headers.items() if k and v) if isinstance(headers, dict) else ""


def download_clipped_stream_direct(
    coordinator: Any,
    set_suspended_fn: Optional[Callable[[Any, bool], None]] = None,
) -> bool:
    """Directly downloads and extracts a specified clip/chapter range via HTTP range seek FFmpeg."""
    si = getattr(coordinator, "stream_info", None)
    if not si: return False
    from ..media_env_helpers import find_ffmpeg_bin
    ffmpeg_bin = find_ffmpeg_bin()
    if not ffmpeg_bin: return False

    c_start, c_end = float(getattr(si, "clip_start_sec", 0.0) or 0.0), float(getattr(si, "clip_end_sec", 0.0) or 0.0)
    if not (c_end > c_start >= 0): return False
    duration, clip_dur = float(getattr(si, "duration", 0.0) or 0.0), c_end - c_start
    if duration > 0 and clip_dur >= duration * 0.85: return False

    mce = sys.modules.get("faqih_downloader.services.media_clipper_engine")
    eff_set_suspended = set_suspended_fn or (getattr(mce, "_set_process_suspended", None) if mce else None) or _set_process_suspended

    v_url = getattr(si, "video_url", "") or ""
    raw_total = getattr(si, "video_size", 0) + (getattr(si, "audio_size", 0) if not getattr(si, "is_progressive", False) else 0)
    est_total = estimate_clip_total_bytes(si, raw_total) or (getattr(si, "video_size", 0) or 10485760)

    from ...core.chunk import DownloadChunk
    chunk_count, chunks_list = 8, []
    part_sz = max(1, est_total // chunk_count)
    for i in range(chunk_count):
        sb = i * part_sz
        eb = (i + 1) * part_sz - 1 if i < chunk_count - 1 else max(sb, est_total - 1)
        chunks_list.append(DownloadChunk(chunk_id=i, start_byte=sb, end_byte=max(sb, eb), downloaded_bytes=0, status="active" if i == 0 else "pending"))
    coordinator._clip_chunks = chunks_list
    coordinator._clip_total_size = est_total

    a_url = getattr(si, "audio_url", None) or ""
    bridge, ffmpeg_v_url, ffmpeg_a_url = None, v_url, a_url
    if any(dom in v_url or (a_url and dom in a_url) for dom in ("googlevideo.com", "gvt1.com")):
        try:
            from ..preview_stream_proxy import PreviewStreamBridge
            bridge = PreviewStreamBridge()
            bridge.start()
            if "googlevideo.com" in v_url or "gvt1.com" in v_url:
                ffmpeg_v_url = bridge.register_stream(v_url, headers=getattr(si, "video_headers", {}))
            if a_url and ("googlevideo.com" in a_url or "gvt1.com" in a_url):
                ffmpeg_a_url = ffmpeg_v_url if a_url == v_url else bridge.register_stream(a_url, headers=getattr(si, "audio_headers", {}) or getattr(si, "video_headers", {}))
        except Exception:
            ffmpeg_v_url, ffmpeg_a_url = v_url, a_url

    clip_in = ["-ss", f"{c_start:.3f}"]
    reconn = ["-reconnect", "1", "-reconnect_on_network_error", "1", "-reconnect_on_http_error", "4xx,5xx", "-reconnect_delay_max", "4", "-multiple_requests", "1", "-seekable", "1", "-rw_timeout", "15000000"]
    v_rec = reconn if (ffmpeg_v_url.startswith("http://") or ffmpeg_v_url.startswith("https://")) else []
    v_hdr_str = _format_ffmpeg_headers(getattr(si, "video_headers", {})) if ffmpeg_v_url == v_url else ""
    v_hdr_args = ["-headers", v_hdr_str] if v_hdr_str else []
    a_rec = reconn if (ffmpeg_a_url.startswith("http://") or ffmpeg_a_url.startswith("https://")) else []
    is_prog, is_audio_only = bool(getattr(si, "is_progressive", False)), bool(getattr(si, "is_audio_only", False))
    is_dual = bool(ffmpeg_v_url and ffmpeg_a_url and not is_prog and not is_audio_only)
    if is_dual:
        a_hdr_str = _format_ffmpeg_headers(getattr(si, "audio_headers", {}) or getattr(si, "video_headers", {})) if ffmpeg_a_url == a_url else ""
        cmd = [str(ffmpeg_bin), *v_rec, *clip_in, *v_hdr_args, "-i", ffmpeg_v_url, *a_rec, *clip_in, *(["-headers", a_hdr_str] if a_hdr_str else []), "-i", ffmpeg_a_url, "-t", f"{clip_dur:.3f}", "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd = [str(ffmpeg_bin), *v_rec, *clip_in, *v_hdr_args, "-i", ffmpeg_v_url, "-t", f"{clip_dur:.3f}"]

    boost_args, boost_enabled = [], bool(getattr(si, "audio_boost_enabled", False))
    sub = getattr(si, "subtitle_track", None) or getattr(si, "selected_subtitle_track", None)
    has_sub_burn = bool(sub and sub.get("sub_id") not in (None, "none") and (sub.get("url") or sub.get("base_url")) and getattr(si, "subtitle_embed_mode", "hard_burn") == "hard_burn")
    if boost_enabled and (not has_sub_burn or is_audio_only):
        try:
            from ..audio_and_chapters_engine import get_studio_audio_boost_filter
            boost_args = ["-af", get_studio_audio_boost_filter()]
            setattr(si, "_audio_boost_applied", True)
        except Exception: pass

    is_mp3 = coordinator.destination_path.lower().endswith(".mp3") or (is_audio_only and getattr(si, "video_ext", "").lower() == "mp3")
    if is_mp3 and not coordinator.destination_path.lower().endswith(".mp3"):
        coordinator.destination_path = os.path.splitext(coordinator.destination_path)[0] + ".mp3"
    dest_ext = os.path.splitext(coordinator.destination_path)[1] or ".mp4"
    temp_clip_path = f"{coordinator.destination_path}.clip.tmp{dest_ext}"
    if is_mp3: out_args = ["-vn", *boost_args, "-c:a", "libmp3lame", "-q:a", "2", "-y", temp_clip_path]
    elif is_audio_only: out_args = ["-vn", *boost_args, "-c:a", "aac", "-b:a", "192k", "-y", temp_clip_path]
    else: out_args = ["-c:v", "copy", *boost_args, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", temp_clip_path]
    cmd.extend(out_args)

    if hasattr(coordinator, "log"):
        tag = getattr(si, "platform", "Media").upper().replace(" / X", "")
        coordinator.log(f"[{tag}] Direct HTTP-range stream clipping: {c_start:.1f}s -> {c_end:.1f}s")

    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=False, creationflags=cflags)
        coordinator._active_subproc = proc
    except Exception as ex:
        if hasattr(coordinator, "log"): coordinator.log(f"[CLIPPER] FFmpeg direct launch failed: {ex}")
        return False

    buf, start_time, dl_bytes, dynamic_total, last_time_sec = b"", time.time(), 0, est_total, 0.0
    try:
        while True:
            if coordinator._cancel_event.is_set() or not coordinator.is_running:
                try: proc.kill(); proc.wait(timeout=0.5)
                except Exception: pass
                if os.path.exists(temp_clip_path):
                    try: os.remove(temp_clip_path)
                    except Exception: pass
                return False

            if coordinator.is_paused:
                eff_set_suspended(proc, True)
                while coordinator.is_paused and not coordinator._cancel_event.is_set() and coordinator.is_running: time.sleep(0.1)
                eff_set_suspended(proc, False)

            raw = b""
            try: raw = proc.stderr.read1(1024) if hasattr(proc.stderr, "read1") else proc.stderr.read(1024)
            except Exception: pass

            if not raw:
                if proc.poll() is not None: break
                time.sleep(0.04); continue

            buf += raw
            while b"\r" in buf or b"\n" in buf:
                ir, in_ = buf.find(b"\r"), buf.find(b"\n")
                idx = min(ir, in_) if (ir != -1 and in_ != -1) else (ir if ir != -1 else in_)
                line_str = buf[:idx].decode("utf-8", errors="replace"); buf = buf[idx + 1:]
                m_sz = re.search(r"(?:size|Lsize)=\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?i?B)?", line_str, re.IGNORECASE)
                m_tm = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line_str)
                if not m_sz and not m_tm: continue
                if m_tm: last_time_sec = float(m_tm.group(1)) * 3600.0 + float(m_tm.group(2)) * 60.0 + float(m_tm.group(3))
                if m_sz:
                    val = float(m_sz.group(1)); unit = (m_sz.group(2) or "").lower()
                    if "m" in unit: dl_bytes = int(val * 1024 * 1024)
                    elif "g" in unit: dl_bytes = int(val * 1024 * 1024 * 1024)
                    else: dl_bytes = int(val * 1024)

                pct = min(99.0, max(0.0, (last_time_sec / clip_dur) * 100.0)) if clip_dur > 0 else 0.0
                if pct >= 20.0 and dl_bytes > 0:
                    dynamic_total = max(dl_bytes, int(dl_bytes / (pct / 100.0)))
                    if dynamic_total != getattr(coordinator, "_clip_total_size", 0):
                        coordinator._clip_total_size = dynamic_total
                        p_sz = max(1, dynamic_total // chunk_count)
                        for i, chk in enumerate(coordinator._clip_chunks):
                            sb = i * p_sz
                            eb = (i + 1) * p_sz - 1 if i < chunk_count - 1 else max(sb, dynamic_total - 1)
                            with chk.lock: chk.start_byte, chk.end_byte = sb, max(sb, eb)

                eff_dl = max(dl_bytes, int(dynamic_total * (pct / 100.0))) if (pct > 0 and dynamic_total > 0) else dl_bytes
                el = max(0.05, time.time() - start_time); speed = eff_dl / el; rem = max(0, dynamic_total - eff_dl)
                eta_s = int(rem / speed) if speed > 1024 and rem > 0 else 0; eta_str = f"{eta_s // 60}:{eta_s % 60:02d}"

                accum = eff_dl
                for c in coordinator._clip_chunks:
                    with c.lock:
                        c_tot = c.total_bytes
                        if accum >= c_tot: c.downloaded_bytes, c.status, accum = c_tot, "completed", accum - c_tot
                        elif accum > 0: c.downloaded_bytes, c.status, accum = accum, "active", 0
                        else: c.downloaded_bytes, c.status = 0, "pending"

                ac = sum(1 for c in coordinator._clip_chunks if c.status == "active") or 1
                coordinator._last_active_speed = speed
                if coordinator.on_progress: coordinator.on_progress(eff_dl, dynamic_total, speed, eta_str, ac)
                if coordinator.on_chunk_update:
                    try: coordinator.on_chunk_update()
                    except Exception: pass
        proc.wait()
        if proc.returncode == 0 and os.path.isfile(temp_clip_path) and os.path.getsize(temp_clip_path) > 0:
            for _ in range(4):
                try: os.replace(temp_clip_path, coordinator.destination_path); break
                except Exception:
                    try: shutil.move(temp_clip_path, coordinator.destination_path); break
                    except Exception: time.sleep(0.08)
            setattr(si, "_already_trimmed", True)
            coordinator._process_subtitles(coordinator.destination_path)
            for c in coordinator._clip_chunks:
                with c.lock: c.downloaded_bytes, c.status = c.total_bytes, "completed"
            if coordinator.on_chunk_update:
                try: coordinator.on_chunk_update()
                except Exception: pass
            final_sz = os.path.getsize(coordinator.destination_path) if os.path.isfile(coordinator.destination_path) else dynamic_total
            el = max(0.05, time.time() - start_time)
            with coordinator._lock: coordinator._is_running = False
            if coordinator.on_complete: coordinator.on_complete(coordinator.destination_path, final_sz, el)
            return True
        return False
    except Exception as ex:
        if hasattr(coordinator, "log"): coordinator.log(f"[CLIPPER] FFmpeg execution error: {ex}")
        return False
    finally:
        if bridge is not None:
            try: bridge.stop()
            except Exception: pass
        if os.path.exists(temp_clip_path) and not getattr(si, "_already_trimmed", False):
            try: os.remove(temp_clip_path)
            except Exception: pass


__all__ = [
    "_format_ffmpeg_headers",
    "download_clipped_stream_direct",
]
