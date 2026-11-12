"""
Live E2E tests for Pause/Resume unblocking, Speed EMA smoothing, StreamCoordinator pause/resume,
Kanban active card Pause/Resume UI controls, and RoundedGlassCard C-native layout resize.
"""
import hashlib
import http.server
import os
import socketserver
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from faqih_downloader.core.chunk import DownloadChunk
from faqih_downloader.core.engine import TurboDownloadEngine
from faqih_downloader.core.stream_coordinator import StreamDownloadCoordinator
from faqih_downloader.services.youtube_models import YouTubeStreamInfo
from faqih_downloader.ui.controllers.download_controller import DownloadControllerMixin
from faqih_downloader.ui.panels.kanban_active_mixin import KanbanActiveColumnMixin
from faqih_downloader.utils.window_effects import RoundedGlassCard


class _ThrottledRangeHandler(http.server.BaseHTTPRequestHandler):
    payload: bytes = b""
    chunk_delay_sec: float = 0.015
    chunk_write_size: int = 32768
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

    def do_GET(self):
        data = self.payload
        total = len(data)
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            start_s, end_s = rng[6:].split("-", 1)
            start = int(start_s)
            end = int(end_s) if end_s else (total - 1)
            end = min(end, total - 1)
            seg = data[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.send_header("Content-Length", str(len(seg)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
        else:
            seg = data
            self.send_response(200)
            self.send_header("Content-Length", str(len(seg)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

        pos = 0
        try:
            while pos < len(seg):
                piece = seg[pos : pos + self.chunk_write_size]
                self.wfile.write(piece)
                self.wfile.flush()
                pos += len(piece)
                if self.chunk_delay_sec > 0 and len(seg) > 1:
                    time.sleep(self.chunk_delay_sec)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class TestLivePauseResumeAndPerf(unittest.TestCase):

    def test_live_http_pause_freezes_progress_zeroes_speed_and_resumes_to_sha256_match(self):
        """
        Live HTTP test:
        Start multi-chunk download -> pause() mid-flight -> verify socket close unblocks quickly,
        speed == 0.0, progress frozen & retry_count == 0 -> resume() -> 100% completion + SHA-256 match.
        """
        payload = os.urandom(2 * 1024 * 1024 + 137)
        expected_hash = hashlib.sha256(payload).hexdigest()
        _ThrottledRangeHandler.payload = payload
        _ThrottledRangeHandler.chunk_delay_sec = 0.025
        _ThrottledRangeHandler.chunk_write_size = 32768

        srv = _ThreadingHTTPServer(("127.0.0.1", 0), _ThrottledRangeHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        prog_events = []
        done_evt = threading.Event()
        errs = []

        def on_prog(dl, tot, spd, eta, act):
            prog_events.append((dl, tot, spd, eta, act))

        try:
            with tempfile.TemporaryDirectory() as td:
                dest = os.path.join(td, "live_pause_resume.bin")
                eng = TurboDownloadEngine(
                    url=f"http://127.0.0.1:{port}/file.bin",
                    destination_path=dest,
                    max_connections=4,
                    min_split_threshold=64 * 1024,
                    on_progress=on_prog,
                    on_complete=lambda p, s, e: done_evt.set(),
                    on_error=lambda err: errs.append(err),
                )
                eng.start()

                # Wait until some real bytes are downloaded (> 128 KB and < 85% complete)
                deadline = time.monotonic() + 8.0
                while time.monotonic() < deadline:
                    dl_now = sum(c.downloaded_bytes for c in eng.chunks)
                    if dl_now >= 128 * 1024:
                        break
                    time.sleep(0.05)

                dl_before_pause = sum(c.downloaded_bytes for c in eng.chunks)
                self.assertGreater(dl_before_pause, 0, "Download did not make initial progress")
                self.assertLess(dl_before_pause, len(payload), "Download finished before pause test")

                t_pause_start = time.monotonic()
                eng.pause()
                pause_call_ms = (time.monotonic() - t_pause_start) * 1000.0
                self.assertLess(pause_call_ms, 500.0, "engine.pause() must return rapidly without blocking")
                self.assertTrue(eng.is_paused)
                self.assertEqual(eng.current_speed, 0.0)
                self.assertEqual(len(eng._active_connections), 0)

                paused_events = [ev for ev in prog_events if ev[3] == "Paused"]
                self.assertTrue(paused_events, "pause() must immediately emit 'Paused' progress event")
                self.assertEqual(paused_events[-1][2], 0.0)
                self.assertGreater(paused_events[-1][0], 0)

                # Wait for any in-flight write to settle briefly, then confirm progress stays frozen
                time.sleep(0.2)
                snap_1 = sum(c.downloaded_bytes for c in eng.chunks)
                time.sleep(0.45)
                snap_2 = sum(c.downloaded_bytes for c in eng.chunks)
                self.assertEqual(snap_1, snap_2, "Progress must remain completely frozen while paused")
                self.assertEqual(eng.current_speed, 0.0, "Speed must stay 0.0 while paused")
                self.assertTrue(all(c.retry_count == 0 for c in eng.chunks), "Pausing must not increment retry_count")

                # Resume and remove throttling so completion finishes fast
                _ThrottledRangeHandler.chunk_delay_sec = 0.0
                eng.resume()
                self.assertFalse(eng.is_paused)
                downloading_events = [ev for ev in prog_events if ev[3] == "Downloading"]
                self.assertTrue(downloading_events, "resume() must immediately emit 'Downloading' progress event")

                self.assertTrue(done_evt.wait(timeout=15.0), f"Resumed download timed out! errors={errs}")
                self.assertEqual(errs, [])
                self.assertEqual(os.path.getsize(dest), len(payload))
                with open(dest, "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), expected_hash)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_resume_spawns_new_worker_when_chunk_thread_is_dead(self):
        """Verifies resume() creates and starts _chunk_worker threads for incomplete chunks whose thread died."""
        with tempfile.TemporaryDirectory() as td:
            eng = TurboDownloadEngine("http://example.com/a.bin", os.path.join(td, "a.bin"), max_connections=2)
            eng.is_running = True
            eng.is_paused = True
            eng._pause_event.set()
            eng.total_size = 2000

            c0 = DownloadChunk(0, 0, 999, downloaded_bytes=500, status="active", part_filepath=os.path.join(td, "p0"))
            c1 = DownloadChunk(1, 1000, 1999, downloaded_bytes=1000, status="completed", part_filepath=os.path.join(td, "p1"))
            eng.chunks = [c0, c1]

            dead_thread = threading.Thread(target=lambda: None)
            dead_thread.start()
            dead_thread.join()
            eng._worker_threads[0] = dead_thread

            spawned = []
            with patch.object(eng, "_chunk_worker", side_effect=lambda ch: spawned.append(ch.chunk_id)):
                eng.resume()
                t0 = eng._worker_threads.get(0)
                if t0:
                    t0.join(timeout=2.0)

            self.assertEqual(spawned, [0])
            self.assertNotEqual(eng._worker_threads[0], dead_thread)

    def test_pool_reuse_without_blocking_read_and_ema_speed_window(self):
        """Verifies _release_or_close_conn pools clean length==0 connections and EMA uses 0.25/0.75 >=1.5s window."""
        with tempfile.TemporaryDirectory() as td:
            eng = TurboDownloadEngine("http://example.com/x.bin", os.path.join(td, "x.bin"))
            eng.is_running = True
            eng.total_size = 10_000_000

            mock_conn = MagicMock()
            mock_conn.sock = MagicMock()
            mock_raw = MagicMock()
            mock_raw.will_close = False
            mock_raw.length = 0
            mock_raw.isclosed.return_value = True

            eng._release_or_close_conn(mock_conn, None, mock_raw, ("http", "example.com", 80), 1024, 1024)
            mock_raw.read.assert_not_called()
            self.assertIs(eng._acquire_pooled_conn(("http", "example.com", 80)), mock_conn)

            # Speed EMA calculation test over >= 1.5s sample window
            eng.chunks = [DownloadChunk(0, 0, 9_999_999, downloaded_bytes=0, status="active")]
            now = 100.0
            eng._speed_samples = deque([(98.0, 0), (99.0, 1_000_000)])
            eng.last_speed_check_time = 99.6
            eng.last_downloaded_bytes = 1_000_000
            eng.current_speed = 1_000_000.0
            eng.chunks[0].downloaded_bytes = 3_000_000  # 3 MB over 2.0s => 1.5 MB/s window speed

            with patch("faqih_downloader.core.engine_workers.time.monotonic", return_value=now):
                eng._update_progress_metrics()

            expected = 0.25 * (3_000_000 / 2.0) + 0.75 * 1_000_000.0
            self.assertAlmostEqual(eng.current_speed, expected, places=2)

    def test_stream_coordinator_pause_and_resume_emit_progress(self):
        """Verifies StreamDownloadCoordinator.pause()/resume() update state and emit Paused/Downloading callbacks."""
        events = []
        si = YouTubeStreamInfo(
            video_id="v1", title="V", clean_filename="v.mp4",
            is_progressive=False, video_url="http://ex/v", audio_url="http://ex/a",
            video_size=1000, audio_size=500,
        )
        with tempfile.TemporaryDirectory() as td:
            coord = StreamDownloadCoordinator(
                si, os.path.join(td, "v.mp4"),
                on_progress=lambda d, t, s, e, a: events.append((d, t, s, e, a)),
            )
            e1, e2 = MagicMock(), MagicMock()
            e1.chunks = [MagicMock(status="active", downloaded_bytes=300)]
            e2.chunks = [MagicMock(status="active", downloaded_bytes=200)]
            coord._active_engines = [e1, e2]
            coord._v_downloaded, coord._a_downloaded = 300, 200
            coord.pause()
            self.assertTrue(coord.is_paused)
            e1.pause.assert_called_once()
            e2.pause.assert_called_once()
            self.assertEqual(events[-1], (500, 1500, 0.0, "Paused", 0))

            coord.resume()
            self.assertFalse(coord.is_paused)
            e1.resume.assert_called_once()
            e2.resume.assert_called_once()
            self.assertEqual(events[-1][0:4], (500, 1500, 0.0, "Downloading"))
            self.assertEqual(events[-1][4], 2)

    def test_kanban_active_card_pause_button_and_non_blocking_toggle(self):
        """Verifies card_active_1 has visible pause button, displays paused state without resetting MB/%, and never sends size_bytes=0."""
        root = tk.Tk()
        root.withdraw()
        try:
            class DummyApp(KanbanActiveColumnMixin, DownloadControllerMixin):
                def __init__(self, r):
                    self.root = r
                    self._active_stream_live = False
                    self.c_panel_light = "#1e293b"
                    self.c_warning = "#f59e0b"
                    self.c_accent = "#38bdf8"
                    self.btn_pause = tk.Button(r, text="|| Pause")
                    self.card_speed = tk.Label(r, text="4.2 MB/s")
                    self.entry_dest = MagicMock()
                    self.entry_dest.get.return_value = "C:/Downloads/vid.mp4"
                    self._active_download_url = "https://example.com/vid.mp4"
                    self.history_manager = MagicMock()
                    self._refresh_history_table = MagicMock()
                    self._build_col2_active(r)

            app = DummyApp(root)
            self.assertTrue(hasattr(app, "btn_a1_pause"))
            self.assertEqual(app.btn_a1_pause.cget("text"), "⏸")

            total = 20 * 1024 * 1024
            done = 10 * 1024 * 1024
            eng = MagicMock()
            eng.is_running = True
            eng.is_paused = False
            eng.total_size = total
            eng.destination_path = "C:/Downloads/vid.mp4"
            eng.chunks = [DownloadChunk(0, 0, total - 1, downloaded_bytes=done, status="active")]
            eng.get_chunks_snapshot.return_value = eng.chunks
            eng.pause = MagicMock(side_effect=lambda: setattr(eng, "is_paused", True))
            eng.resume = MagicMock(side_effect=lambda: setattr(eng, "is_paused", False))
            app.engine = eng

            # Initial active state
            app.update_kanban_active_stream("vid.mp4", 50.0, "4.2 MB/s", eng.chunks, 1, downloaded=done, total=total, eta="00:05")
            self.assertEqual(app.lbl_a1_pct.cget("text"), "50%")
            self.assertIn("10.0 MB / 20.0 MB", app.lbl_a1_size.cget("text"))

            # Click pause
            app._on_pause_resume()
            self.assertEqual(app.lbl_a1_eta.cget("text"), "⏸ متوقف مؤقتاً")
            self.assertEqual(app.lbl_a1_speed.cget("text"), "0.0 MB/s")
            self.assertEqual(app.lbl_col2_total_speed.cget("text"), "0.0 MB/s")
            self.assertEqual(app.btn_a1_pause.cget("text"), "▶")
            self.assertEqual(app.lbl_a1_pct.cget("text"), "50%")
            self.assertIn("10.0 MB / 20.0 MB", app.lbl_a1_size.cget("text"))

            # Wait briefly for background thread history update; ensure real total used & no full table rebuild
            for _ in range(40):
                if app.history_manager.add_or_update_entry.called:
                    break
                time.sleep(0.02)
            app.history_manager.add_or_update_entry.assert_called_once()
            kwargs = app.history_manager.add_or_update_entry.call_args.kwargs
            self.assertEqual(kwargs["size_bytes"], total)
            self.assertEqual(kwargs["status"], "Paused")
            app._refresh_history_table.assert_not_called()
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_rounded_glass_card_c_native_packing_eliminates_create_window_lag(self):
        """Verifies RoundedGlassCard avoids create_window/_win_id, enables propagate=False, and redraws synchronously."""
        root = tk.Tk()
        root.withdraw()
        try:
            card = RoundedGlassCard(root, width=240, height=120, inner_padx=10, inner_pady=8)
            card.pack(fill=tk.BOTH, expand=True)
            self.assertFalse(hasattr(card, "_win_id"))
            self.assertFalse(hasattr(card, "_resize_redraw_job"))
            self.assertEqual(card.find_all(), ())
            self.assertEqual(card.inner.pack_info()["fill"], "both")
            self.assertEqual(int(card.inner.pack_info()["padx"]), 10)
            self.assertEqual(int(card.inner.pack_info()["pady"]), 8)

            ev = MagicMock(width=300, height=160)
            card._on_resize(ev)
            self.assertEqual(card._last_size, (300, 160))
            self.assertIsNotNone(card._last_drawn_state)
            self.assertEqual(card._last_drawn_state[:2], (300, 160))
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
