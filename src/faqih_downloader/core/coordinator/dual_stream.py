"""
dual_stream.py: Parallel dual-stream (video + audio) download execution and worker draining.
"""
import time
import threading
from typing import Any, List, Tuple


def _drain_engine_workers(*engines: Any) -> None:
    """Waits briefly for active worker threads on stopped engines to terminate."""
    for eng in engines:
        if eng is None:
            continue
        for w in list(getattr(eng, "active_workers", [])):
            if w.is_alive() and w != threading.current_thread():
                w.join(timeout=0.15)


def run_dual_stream_download(
    coordinator: Any,
    video_tmp: str,
    audio_tmp: str,
    tag: str,
) -> Tuple[bool, List[str], List[str], Any, Any]:
    """Downloads separate video and audio streams in parallel with combined progress reporting."""
    coordinator._active_phase = 1
    coordinator.log(f"[{tag}] Phase 1/2: Downloading Video & Audio streams in parallel ({coordinator.stream_info.video_resolution})...")
    v_completed = threading.Event()
    a_completed = threading.Event()
    v_error: List[str] = []
    a_error: List[str] = []

    coordinator._v_speed = 0.0
    coordinator._a_speed = 0.0
    coordinator._v_active = 0
    coordinator._a_active = 0

    def _report_combined():
        with coordinator._lock:
            combined_total = max(1, coordinator._v_total_size + coordinator._a_total_size)
            combined_dl = min(combined_total, coordinator._v_downloaded + coordinator._a_downloaded)
            if coordinator._is_paused:
                combined_speed, combined_active = 0.0, 0
            else:
                combined_speed = coordinator._v_speed + coordinator._a_speed
                combined_active = coordinator._v_active if not v_completed.is_set() else coordinator._a_active
                if combined_speed > 0:
                    coordinator._last_active_speed = combined_speed
                elif combined_dl > 0 and coordinator._last_active_speed <= 0.0:
                    st = coordinator.start_time
                    el = (time.time() - st) if (isinstance(st, (int, float)) and st > 0) else 0.1
                    coordinator._last_active_speed = combined_dl / max(0.05, el)
                if combined_speed <= 0.0 and coordinator._last_active_speed > 0 and (v_completed.is_set() and a_completed.is_set()):
                    combined_speed = coordinator._last_active_speed
        if coordinator._is_paused:
            eta_str = "Paused"
        elif combined_speed > 1024 and combined_total > combined_dl:
            eta_sec = int((combined_total - combined_dl) / combined_speed)
            eta_str = f"{eta_sec // 3600:02d}:{(eta_sec % 3600) // 60:02d}:{eta_sec % 60:02d}"
        else:
            eta_str = "--:--:--"
        coordinator._emit_progress(combined_dl, combined_total, combined_speed, eta_str, combined_active)

    def _on_v_complete(path, size, elapsed):
        with coordinator._lock:
            if size > 0: coordinator._v_total_size = size
            coordinator._v_downloaded = coordinator._v_total_size
            coordinator._v_speed = 0.0
            coordinator._v_active = 0
            if not a_completed.is_set():
                coordinator.current_engine = a_engine
        v_completed.set()
        _report_combined()

    def _on_v_error(err):
        v_error.append(err)
        v_completed.set()
        a_completed.set()
        try: a_engine.cancel()
        except Exception: pass

    def _on_v_progress(downloaded, total, speed, eta, active):
        with coordinator._lock:
            coordinator._v_downloaded = downloaded
            if total > 0: coordinator._v_total_size = total
            coordinator._v_speed = speed
            coordinator._v_active = active
        _report_combined()

    def _on_a_complete(path, size, elapsed):
        with coordinator._lock:
            if size > 0: coordinator._a_total_size = size
            coordinator._a_downloaded = coordinator._a_total_size
            coordinator._a_speed = 0.0
            coordinator._a_active = 0
        a_completed.set()
        _report_combined()

    def _on_a_error(err):
        with coordinator._lock:
            coordinator._a_speed = 0.0
            coordinator._a_active = 0
        a_error.append(err); a_completed.set(); _report_combined()

    def _on_a_progress(downloaded, total, speed, eta, active):
        with coordinator._lock:
            coordinator._a_downloaded = downloaded
            if total > 0: coordinator._a_total_size = total
            coordinator._a_speed, coordinator._a_active = speed, active
        _report_combined()

    v_conn = max(1, coordinator.max_connections)
    v_engine = coordinator._make_engine(
        coordinator.stream_info.video_url, video_tmp, v_conn, (coordinator.max_connections > 1),
        coordinator.stream_info.video_headers, _on_v_progress, _on_v_complete, _on_v_error,
        getattr(coordinator.stream_info, "video_size", 0),
    )
    a_conn = min(2, max(1, coordinator.max_connections))  # Wi-Fi safe: a_conn = 1 on single-stream
    a_engine = coordinator._make_engine(
        coordinator.stream_info.audio_url, audio_tmp, a_conn, (a_conn > 1),  # Wi-Fi safe: allow_dynamic_split=False when a_conn <= 1
        coordinator.stream_info.audio_headers, _on_a_progress, _on_a_complete, _on_a_error,
        getattr(coordinator.stream_info, "audio_size", 0),
    )
    if coordinator.rate_limit > 0:
        a_engine.rate_limiter = v_engine.rate_limiter

    with coordinator._lock:
        coordinator.current_engine = v_engine; coordinator._active_engines = [v_engine, a_engine]
    while coordinator._is_paused and not coordinator._cancel_event.is_set(): time.sleep(0.05)
    if not coordinator._cancel_event.is_set(): v_engine.start()
    while coordinator._is_paused and not coordinator._cancel_event.is_set(): time.sleep(0.05)
    if not coordinator._cancel_event.is_set(): a_engine.start()

    while not (v_completed.is_set() and a_completed.is_set()) and not coordinator._cancel_event.is_set():
        if v_error:
            break
        time.sleep(0.05)

    if coordinator._cancel_event.is_set():
        v_engine.cancel(); a_engine.cancel(); _drain_engine_workers(v_engine, a_engine)
        return True, v_error, a_error, v_engine, a_engine
    if v_error:
        a_engine.cancel(); _drain_engine_workers(v_engine, a_engine)
        raise RuntimeError(f"Video stream download error: {v_error[0]}")
    return False, v_error, a_error, v_engine, a_engine


__all__ = ["_drain_engine_workers", "run_dual_stream_download"]
