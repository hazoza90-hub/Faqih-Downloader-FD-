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
from faqih_downloader.ui.controllers.download_callbacks_mixin import DownloadCallbacksMixin
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
                drain_dl = time.monotonic() + 0.5
                while time.monotonic() < drain_dl and len(eng._active_connections) > 0:
                    time.sleep(0.01)
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

            # Speed EMA calculation test over 2.0s sliding window (0.35 instant + 0.65 previous) and dt >= 0.20 gate
            eng.chunks = [DownloadChunk(0, 0, 9_999_999, downloaded_bytes=0, status="active")]
            emitted = []
            eng.on_progress = lambda *a: emitted.append(a)
            now = 100.0
            eng._speed_samples = deque([(97.8, 0), (99.0, 1_000_000)])
            eng.last_speed_check_time = 99.6
            eng.last_downloaded_bytes = 1_000_000
            eng.current_speed = 1_000_000.0
            eng.chunks[0].downloaded_bytes = 2_500_000  # 2.5 MB over 2.2s window

            with patch("faqih_downloader.core.engine_workers.time.monotonic", return_value=now):
                eng._update_progress_metrics()

            first_instant = 2_500_000 / 2.2
            expected_first = 0.35 * first_instant + 0.65 * 1_000_000.0
            self.assertAlmostEqual(eng.current_speed, expected_first, places=2)
            self.assertEqual(len(emitted), 1)

            # Update < 0.20s later must NOT update speed or emit on_progress
            with patch("faqih_downloader.core.engine_workers.time.monotonic", return_value=100.10):
                eng._update_progress_metrics()
            self.assertAlmostEqual(eng.current_speed, expected_first, places=2)
            self.assertEqual(len(emitted), 1)

            # Next >= 0.20s sample (99.0 stays since 100.25 - 99.0 = 1.25 < 2.0)
            now2 = 100.25
            eng.chunks[0].downloaded_bytes = 2_900_000
            with patch("faqih_downloader.core.engine_workers.time.monotonic", return_value=now2):
                eng._update_progress_metrics()
            second_instant = 2_900_000 / (100.25 - 97.8)
            expected_second = 0.35 * second_instant + 0.65 * expected_first
            self.assertAlmostEqual(eng.current_speed, expected_second, places=2)
            self.assertEqual(len(emitted), 2)

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

    def test_ui_resume_does_not_revert_while_engine_lags_and_double_click_serializes(self):
        """Verifies Resume keeps UI active while bg eng.resume() lags, LED matrix respects pause, and rapid clicks serialize."""
        root = tk.Tk()
        root.withdraw()
        try:
            class DummyApp(KanbanActiveColumnMixin, DownloadControllerMixin, DownloadCallbacksMixin):
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
                    self._draw_main_progress = MagicMock()
                    self._refresh_chunk_displays = MagicMock()
                    self._build_col2_active(r)
                    self.matrix_a1 = MagicMock()

            app = DummyApp(root)
            total = 20 * 1024 * 1024
            done = 10 * 1024 * 1024
            resume_gate = threading.Event()
            toggles = []

            class LaggyEngine:
                def __init__(self):
                    self.is_running = True
                    self.is_paused = False
                    self.total_size = total
                    self.max_connections = 4
                    self.destination_path = "C:/Downloads/vid.mp4"
                    self.chunks = [DownloadChunk(0, 0, total - 1, downloaded_bytes=done, status="active")]
                def get_chunks_snapshot(self):
                    return self.chunks
                def pause(self):
                    time.sleep(0.03)
                    self.is_paused = True
                    toggles.append("pause")
                def resume(self):
                    resume_gate.wait(timeout=2.0)
                    self.is_paused = False
                    toggles.append("resume")

            eng = LaggyEngine()
            app.engine = eng
            app.update_kanban_active_stream("vid.mp4", 50.0, "4.2 MB/s", eng.chunks, 1, downloaded=done, total=total, eta="00:05")

            # Pause and wait for laggy pause()
            app._on_pause_resume()
            for _ in range(40):
                if eng.is_paused and app._pause_desired_state is None:
                    break
                time.sleep(0.02)
            self.assertTrue(eng.is_paused)

            # Verify LED matrix gets is_active=False when _engine_chunk_update_cb runs while paused
            app._chunk_ui_update_pending = app._chunk_update_pending = False
            app._engine_chunk_update_cb()
            root.update()
            self.assertTrue(app.matrix_a1.update_from_chunks.called)
            last_kw = app.matrix_a1.update_from_chunks.call_args.kwargs
            self.assertFalse(last_kw["is_active"])
            self.assertEqual(last_kw["active_count"], 0)

            # Click Resume while eng.resume() is STILL blocked (eng.is_paused remains True)
            app._on_pause_resume()
            self.assertEqual(app.btn_a1_pause.cget("text"), "⏸")
            self.assertNotEqual(app.lbl_a1_eta.cget("text"), "⏸ متوقف مؤقتاً")

            # Release resume_gate and verify convergence
            resume_gate.set()
            for _ in range(50):
                if not eng.is_paused and app._pause_desired_state is None:
                    break
                time.sleep(0.02)
            self.assertFalse(eng.is_paused)

            # Rapid double-click (Pause then Resume immediately) must converge back to running (False)
            resume_gate.clear()
            app._on_pause_resume()  # pause
            app._on_pause_resume()  # resume immediately
            resume_gate.set()
            for _ in range(60):
                if not eng.is_paused and app._pause_desired_state is None:
                    break
                time.sleep(0.02)
            self.assertFalse(eng.is_paused)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_live_http_keepalive_pool_reuses_sockets_across_windows(self):
        """Verifies sequential /videoplayback range windows reuse TCP sockets from _conn_pool with SHA-256 match."""
        import faqih_downloader.core.engine_workers as ew
        payload = os.urandom(512 * 1024)
        expected_sha = hashlib.sha256(payload).hexdigest()
        counts = {"accepts": 0, "reqs": 0}
        cnt_lock = threading.Lock()

        class CountingSrv(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            def get_request(self):
                sock, addr = super().get_request()
                with cnt_lock:
                    counts["accepts"] += 1
                return sock, addr

        class WinHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *a):
                pass
            def do_HEAD(self):
                with cnt_lock:
                    counts["reqs"] += 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
            def do_GET(self):
                with cnt_lock:
                    counts["reqs"] += 1
                s, e = 0, len(payload) - 1
                if "range=" in self.path:
                    r = self.path.split("range=")[1].split("&")[0]
                    s_s, e_s = r.split("-")
                    s, e = int(s_s), int(e_s)
                body = payload[s:e + 1]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {s}-{e}/{len(payload)}")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

        srv = CountingSrv(("127.0.0.1", 0), WinHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td, patch.object(ew, "GOOGLEVIDEO_WINDOW_BYTES", 64 * 1024):
                dest = os.path.join(td, "keepalive.bin")
                done = threading.Event()
                errs = []
                eng = TurboDownloadEngine(
                    f"http://127.0.0.1:{srv.server_address[1]}/videoplayback?id=ka",
                    dest, max_connections=1,
                    on_complete=lambda *a: done.set(),
                    on_error=lambda e: (errs.append(e), done.set()),
                )
                eng.start()
                self.assertTrue(done.wait(timeout=10.0))
                self.assertEqual(errs, [])
                self.assertGreaterEqual(counts["reqs"], 9)
                self.assertLessEqual(counts["reqs"], 10)
                self.assertEqual(counts["accepts"], 2)
                with open(dest, "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), expected_sha)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_save_state_concurrent_and_post_cancel_safety(self):
        """Verifies save_state serializes concurrent saves, preserves safe_shutdown, and blocks post-cancel recreation."""
        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "file.bin")
            eng = TurboDownloadEngine("http://127.0.0.1:1/x.bin", dest, max_connections=2)
            eng.total_size = 2048
            eng.chunks = [DownloadChunk(0, 0, 1023, downloaded_bytes=512), DownloadChunk(1, 1024, 2047, downloaded_bytes=256)]
            results = []
            threads = [threading.Thread(target=lambda: results.append(eng.save_state())) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=3.0)
            self.assertEqual(len(results), 8)
            self.assertTrue(all(results))
            eng.safe_shutdown()
            self.assertTrue(os.path.exists(os.path.join(eng.temp_dir, "state.json")))
            eng.cancel()
            self.assertFalse(os.path.exists(eng.temp_dir))
            self.assertFalse(eng.save_state())
            self.assertFalse(os.path.exists(eng.temp_dir))

    def test_rounded_glass_card_real_mapped_resize_updates_inner_synchronously(self):
        """Verifies mapped RoundedGlassCard inner frame matches card size immediately after real geometry resize."""
        root = tk.Tk()
        root.geometry("400x260")
        try:
            card = RoundedGlassCard(root, radius=10, inner_padx=8, inner_pady=6)
            card.pack(fill=tk.BOTH, expand=True)
            lbl = tk.Label(card.inner, text="Mapped Content")
            lbl.pack(fill=tk.BOTH, expand=True)
            root.update()
            self.assertEqual((card.inner.winfo_width(), card.inner.winfo_height()), (card.winfo_width() - 16, card.winfo_height() - 12))
            root.geometry("620x380")
            root.update()
            self.assertEqual(card.winfo_width(), 620)
            self.assertEqual(card.winfo_height(), 380)
            self.assertEqual((card.inner.winfo_width(), card.inner.winfo_height()), (604, 368))
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_stream_coordinator_prestart_pause_and_no_stale_progress_after_pause(self):
        """Verifies pre-start pause holds engine.start() until resume and prevents stale non-zero speeds after pause()."""
        payload = os.urandom(512 * 1024)
        expected_sha = hashlib.sha256(payload).hexdigest()

        class SlowRangeHandler(_ThrottledRangeHandler):
            chunk_delay_sec = 0.015
            chunk_write_size = 32768
        SlowRangeHandler.payload = payload

        class ThreadedSrv(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        server = ThreadedSrv(("127.0.0.1", 0), SlowRangeHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td:
                dest = os.path.join(td, "coord.bin")
                events = []
                done = threading.Event()
                errs = []
                info = YouTubeStreamInfo(
                    video_id="vc1",
                    title="coord",
                    clean_filename="coord.bin",
                    is_progressive=True,
                    video_url=f"http://127.0.0.1:{server.server_address[1]}/v.bin",
                    video_size=len(payload),
                )
                coord = StreamDownloadCoordinator(
                    stream_info=info,
                    destination_path=dest,
                    max_connections=2,
                    on_progress=lambda d, t, sp, et, ac: events.append((d, t, sp, et, ac)),
                    on_complete=lambda *a: done.set(),
                    on_error=lambda e: (errs.append(e), done.set()),
                )
                coord.start()
                coord.pause()
                time.sleep(0.25)
                # Coordinator must stay paused and must not complete while paused right after start()
                self.assertFalse(done.is_set())
                self.assertEqual(coord.is_paused, True)

                coord.resume()
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and not any(e[0] > 65536 for e in events):
                    time.sleep(0.02)
                self.assertTrue(any(e[0] > 65536 for e in events))

                coord.pause()
                idx = len(events)
                time.sleep(0.2)
                trailing = events[idx:]
                self.assertTrue(all(e[2] == 0.0 and e[3] == "Paused" for e in trailing), f"Stale speed after pause: {trailing}")

                coord.resume()
                self.assertTrue(done.wait(timeout=10.0))
                self.assertEqual(errs, [])
                with open(dest, "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), expected_sha)
        finally:
            server.shutdown()
            server.server_close()

    def test_keepalive_wrapper_uses_blocking_read_and_release_closes_unclosed_zero_length(self):
        """Verifies _KeepAliveResponseWrapper.read batches read1(64KB) with pause/cancel break and owner-thread close guard."""
        from faqih_downloader.core.engine_workers import _KeepAliveResponseWrapper

        class FakeStdlibResp:
            def __init__(self, payload: bytes):
                self._buf = payload
                self.length = len(payload)
                self.will_close = False
                self._closed = False
                self.status = 206
                self.headers = {}
                self.read_calls = 0
                self.read1_calls = 0

            def read(self, n=-1):
                self.read_calls += 1
                chunk = self._buf[:n] if n >= 0 else self._buf
                self._buf = self._buf[len(chunk):]
                self.length -= len(chunk)
                if self.length == 0:
                    self._closed = True
                return chunk

            def read1(self, n=-1):
                self.read1_calls += 1
                chunk = self._buf[:n] if n >= 0 else self._buf
                self._buf = self._buf[len(chunk):]
                self.length -= len(chunk)
                return chunk

            def isclosed(self):
                return self._closed

            def _close_conn(self):
                self._closed = True

            def close(self):
                self._closed = True

        pause_ev = threading.Event()
        raw = FakeStdlibResp(b"hello")
        conn = MagicMock()
        conn.sock = MagicMock()
        wrapper = _KeepAliveResponseWrapper(raw, conn, pause_event=pause_ev)
        self.assertEqual(wrapper.read(5), b"hello")
        self.assertEqual(raw.read1_calls, 1)
        self.assertTrue(raw.isclosed())

        # Cross-thread close while another thread is inside read1() must NOT close raw resp
        raw_slow = FakeStdlibResp(b"a" * 131072)
        pause_slow = threading.Event()
        w_slow = _KeepAliveResponseWrapper(raw_slow, MagicMock(), pause_event=pause_slow)
        w_slow._reading = True
        w_slow._owner_tid = -1
        w_slow.close()
        self.assertFalse(raw_slow.isclosed())
        pause_slow.set()
        self.assertEqual(w_slow.read(65536), b"")

        with tempfile.TemporaryDirectory() as td:
            eng = TurboDownloadEngine("http://example.com/v.bin", os.path.join(td, "v.bin"))
            eng.is_running = True
            raw2 = FakeStdlibResp(b"")
            raw2.length = 0
            raw2._closed = False
            conn2 = MagicMock()
            conn2.sock = MagicMock()
            eng._release_or_close_conn(conn2, None, raw2, ("http", "example.com", 80), 64, 64)
            self.assertTrue(raw2.isclosed())
            self.assertIs(eng._acquire_pooled_conn(("http", "example.com", 80)), conn2)

    def test_stream_coordinator_pause_zeroes_dual_metrics_and_no_stale_speed_after_audio_done(self):
        """Verifies pause() resets _v/_a metrics and _report_combined does not leak stale speed when only audio finished."""
        payload_v = os.urandom(256 * 1024)
        payload_a = os.urandom(16 * 1024)

        class DualHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *a):
                pass
            def do_HEAD(self):
                sz = len(payload_a) if "/audio" in self.path else len(payload_v)
                self.send_response(200)
                self.send_header("Content-Length", str(sz))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
            def do_GET(self):
                data = payload_a if "/audio" in self.path else payload_v
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                if "/audio" in self.path:
                    self.wfile.write(data)
                    self.wfile.flush()
                else:
                    # Slow video chunks so audio completes first, then video pauses/slows
                    pos = 0
                    while pos < len(data):
                        try:
                            self.wfile.write(data[pos:pos + 32768])
                            self.wfile.flush()
                        except OSError:
                            return
                        pos += 32768
                        time.sleep(0.03)

        class DualSrv(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        srv = DualSrv(("127.0.0.1", 0), DualHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td:
                si = YouTubeStreamInfo(
                    video_id="d1", title="dual", clean_filename="dual.mp4", is_progressive=False,
                    video_url=f"http://127.0.0.1:{srv.server_address[1]}/video",
                    audio_url=f"http://127.0.0.1:{srv.server_address[1]}/audio",
                    video_size=len(payload_v), audio_size=len(payload_a),
                )
                events = []
                done = threading.Event()
                coord = StreamDownloadCoordinator(
                    si, os.path.join(td, "dual.mp4"), max_connections=1,
                    on_progress=lambda d, t, sp, et, ac: events.append((d, t, sp, et, ac)),
                    on_complete=lambda *a: done.set(),
                    on_error=lambda e: done.set(),
                )
                with patch("faqih_downloader.services.youtube_service.YouTubeResolver.merge_video_audio"), \
                     patch("faqih_downloader.services.media_env_helpers.ensure_complete_audio_file", return_value=True):
                    coord.start()
                    deadline = time.monotonic() + 5.0
                    while time.monotonic() < deadline and coord._a_downloaded < len(payload_a):
                        time.sleep(0.02)
                    coord._v_speed = 12345.0
                    coord._a_speed = 6789.0
                    coord._v_active = 2
                    coord._a_active = 1
                    coord.pause()
                    self.assertEqual(coord._v_speed, 0.0)
                    self.assertEqual(coord._a_speed, 0.0)
                    self.assertEqual(coord._v_active, 0)
                    self.assertEqual(coord._a_active, 0)

                    # Simulate resume before video sends non-zero speed while audio already completed
                    coord._last_active_speed = 500_000.0
                    coord._is_paused = False
                    coord._pause_event.clear()
                    # Trigger a zero-speed progress callback on video engine while audio is already done
                    v_eng = coord._active_engines[0]
                    events_before = len(events)
                    v_eng.on_progress(coord._v_downloaded, len(payload_v), 0.0, "00:10:00", 1)
                    self.assertGreater(len(events), events_before)
                    self.assertEqual(events[-1][2], 0.0, "Stale _last_active_speed leaked while video is still incomplete")
                    coord.cancel()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_vault_column_resize_sync_and_glass_card_unbinds_configure(self):
        """Verifies Column 3 scrollregion deferral, no update_idletasks inside <Configure>, cv._win_id, and release refresh."""
        from faqih_downloader.ui.panels.kanban_vault_helpers import setup_vault_scroll_view
        from faqih_downloader.ui.controllers.window_resize_mixin import WindowResizeMixin

        root = tk.Tk()
        root.geometry("500x400")
        try:
            body = tk.Frame(root)
            body.pack(fill=tk.BOTH, expand=True)
            cv, container = setup_vault_scroll_view(body, body)
            self.assertTrue(hasattr(cv, "_win_id"))
            card = RoundedGlassCard(container, radius=8, inner_padx=6, inner_pady=4)
            card.pack(fill=tk.X)
            lbl = tk.Label(card.inner, text="Vault Item")
            lbl.pack()
            root.update()

            card._on_inner_resize()
            self.assertEqual(card.inner.bind("<Configure>"), "")

            root._is_resizing_window = True
            with patch.object(cv, "bbox", wraps=cv.bbox) as mock_bbox, \
                 patch.object(container, "update_idletasks", wraps=container.update_idletasks) as mock_uid:
                cv._schedule_vault_scrollregion()
                root.update_idletasks()
                mock_bbox.assert_not_called()
                cv._last_win_w = 0
                cv.event_generate("<Configure>", width=320, height=300)
                root.update_idletasks()
                mock_uid.assert_not_called()

            class DummyWin(WindowResizeMixin):
                def __init__(self, r, c):
                    self.root = r
                    self.vault_cards_canvas = c
                    self._resize_state = {"mode": "e"}

            dw = DummyWin(root, cv)
            with patch.object(cv, "bbox", wraps=cv.bbox) as mock_bbox_rel:
                dw._on_resize_release()
                self.assertFalse(root._is_resizing_window)
                self.assertTrue(mock_bbox_rel.called)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_googlevideo_clen_overrides_preprobed_approx_size_and_tail_drain(self):
        """Verifies clen overrides pre_probed_info approximate size and _drain_small_tail preserves keep-alive."""
        with tempfile.TemporaryDirectory() as td:
            eng = TurboDownloadEngine(
                "https://rr1---sn.googlevideo.com/videoplayback?clen=9876543&id=1",
                os.path.join(td, "gv.mp4"),
                pre_probed_info={"total_size": 9500000, "supports_ranges": True},
            )
            self.assertEqual(eng.total_size, 9876543)

            # _drain_small_tail reads <= 131072 excess bytes after dynamic split to allow keep-alive pooling
            class TailResp:
                def __init__(self):
                    self._rem = b"x" * 1024
                    self.length = 1024
                    self.will_close = False
                    self._closed = False
                def read(self, n=-1):
                    out = self._rem[:n]
                    self._rem = self._rem[len(out):]
                    self.length -= len(out)
                    if self.length == 0:
                        self._closed = True
                    return out
                def isclosed(self):
                    return self._closed

            eng.is_running = True
            raw = TailResp()
            conn = MagicMock()
            conn.sock = MagicMock()
            seg_read = eng._drain_small_tail(raw, raw, 4096, 5120, req_end=5119, chunk_end=4095)
            self.assertEqual(seg_read, 5120)
            self.assertTrue(raw.isclosed())
            eng._release_or_close_conn(conn, raw, raw, ("https", "rr1.googlevideo.com", 443), seg_read, 5120)
            self.assertIs(eng._acquire_pooled_conn(("https", "rr1.googlevideo.com", 443)), conn)

    def test_window_60fps_resize_ws_ex_layered_fast_rect_visualizers_and_vault_hiding(self):
        """Verifies WS_EX_LAYERED removal at alpha=1.0, fast rect coords reuse, C canvas scale, and vault card hide/restore."""
        from faqih_downloader.ui.controllers.window_controller import WindowChromeMixin
        from faqih_downloader.ui.controllers.window_resize_mixin import WindowResizeMixin
        from faqih_downloader.ui.components.led_matrix import LedEqualizerMatrix
        from faqih_downloader.ui.components.waveform_visualizer import WaveformVisualizerCanvas

        root = tk.Tk()
        root.geometry("900x650+50+50")
        try:
            # 1. WS_EX_LAYERED cleared when alpha >= 0.99
            class DummyChrome(WindowChromeMixin):
                def __init__(self, r):
                    self.root = r
            dc = DummyChrome(root)
            with patch("faqih_downloader.ui.controllers.window_controller.IS_WINDOWS", True), \
                 patch("ctypes.windll.user32.GetParent", return_value=999), \
                 patch("ctypes.windll.user32.GetWindowLongW", return_value=0x000C0000), \
                 patch("ctypes.windll.user32.SetWindowLongW") as mock_set_wl:
                dc._clear_layered_style_if_opaque(1.0)
                mock_set_wl.assert_called_once_with(999, -20, 0x00040000)

            # 2. Fast resize rect reuses single item via coords() on drag frames 2+
            card = RoundedGlassCard(root, width=220, height=110)
            card.pack(fill=tk.X)
            led = LedEqualizerMatrix(root, height=40)
            led.pack(fill=tk.X)
            wave = WaveformVisualizerCanvas(root, height=34)
            wave.pack(fill=tk.X)
            cont = tk.Frame(root)
            cont.pack(fill=tk.BOTH, expand=True)
            cards = []
            for i in range(10):
                lbl = tk.Label(cont, text=f"Card {i}")
                lbl.pack(fill=tk.X, pady=(0, 8))
                cards.append(lbl)
            root.update()

            # Simulate drag frames on RoundedGlassCard
            root._is_resizing_window = True
            with patch.object(card, "create_rectangle", wraps=card.create_rectangle) as mock_cre, \
                 patch.object(card, "coords", wraps=card.coords) as mock_coords, \
                 patch.object(card, "delete", wraps=card.delete) as mock_del:
                card._draw_card_bg(240, 110)
                card._draw_card_bg(280, 110)
                card._draw_card_bg(320, 110)
                self.assertEqual(mock_cre.call_count, 1)
                self.assertEqual(mock_del.call_count, 1)
                self.assertEqual(mock_coords.call_count, 2)

            # Led & Wave scale without calling redraw() during drag
            led._last_canvas_size = (240, 40)
            wave._last_canvas_size = (240, 34)
            with patch.object(led, "redraw") as mock_led_r, \
                 patch.object(led.canvas, "scale", wraps=led.canvas.scale) as mock_led_s, \
                 patch.object(wave, "redraw") as mock_wav_r, \
                 patch.object(wave.canvas, "scale", wraps=wave.canvas.scale) as mock_wav_s:
                led._on_canvas_configure(MagicMock(width=360, height=40))
                wave._on_canvas_configure(MagicMock(width=360, height=34))
                mock_led_r.assert_not_called()
                mock_wav_r.assert_not_called()
                mock_led_s.assert_called_once()
                mock_wav_s.assert_called_once()

            # 3. WindowResizeMixin hides >6 vault cards on press, coalesces drag, restores order + redraws on release
            class DummyResizeApp(WindowChromeMixin, WindowResizeMixin):
                def __init__(self, r, vc, vcv):
                    self.root = r
                    self.vault_cards_container = vc
                    self.vault_cards_canvas = vcv
                    self.width, self.height = 900, 650
                    self._min_width, self._min_height = 820, 620
                    self._is_maximized = False
                    self._resize_state = {}

            app = DummyResizeApp(root, cont, MagicMock(winfo_exists=lambda: False))
            app._on_resize_press(MagicMock(x_root=900, y_root=650), "se")
            self.assertTrue(root._is_resizing_window)
            self.assertEqual(len(app._resize_hidden_vault_cards), 4)
            with patch("time.perf_counter", side_effect=[10.0, 10.005]):
                app._on_resize_drag(MagicMock(x_root=940, y_root=670))
                # Immediate second drag within <14ms schedules pending flush
                app._on_resize_drag(MagicMock(x_root=980, y_root=690))
            self.assertIsNotNone(app._pending_resize_geo)

            with patch.object(led, "redraw", wraps=led.redraw) as mock_led_rel, \
                 patch.object(wave, "redraw", wraps=wave.redraw) as mock_wav_rel:
                app._on_resize_release()
                self.assertFalse(root._is_resizing_window)
                self.assertEqual(app._resize_hidden_vault_cards, [])
                self.assertIsNone(card._fast_resize_rect)
                self.assertGreaterEqual(mock_led_rel.call_count, 1)
                self.assertGreaterEqual(mock_wav_rel.call_count, 1)
                packed_order = [w.cget("text") for w in cont.winfo_children() if w.winfo_manager() == "pack"]
                self.assertEqual(packed_order, [f"Card {i}" for i in range(10)])
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_live_https_multithread_repeated_pause_resume_completes_without_crash(self):
        """Live HTTPS (SSLSocket) multi-thread download with repeated pause()/resume() calls must never crash or hang."""
        import ssl
        import ipaddress
        from datetime import datetime, timedelta, timezone
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        payload = os.urandom(2 * 1024 * 1024 + 137)
        expected_sha = hashlib.sha256(payload).hexdigest()
        write_delay = [0.025]

        class HttpsRangeHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *a): pass
            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
            def do_GET(self):
                rng = self.headers.get("Range")
                start, end = 0, len(payload) - 1
                status = 200
                if rng and rng.startswith("bytes="):
                    s, e = rng[6:].split("-", 1)
                    start = int(s) if s else 0
                    end = int(e) if e else len(payload) - 1
                    status = 206
                data = payload[start:end + 1]
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
                self.end_headers()
                pos = 0
                while pos < len(data):
                    try:
                        self.wfile.write(data[pos:pos + 32768])
                        self.wfile.flush()
                    except OSError:
                        return
                    pos += 32768
                    if write_delay[0] > 0:
                        time.sleep(write_delay[0])

        class ThreadedHttpsSrv(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        with tempfile.TemporaryDirectory() as td:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subj).issuer_name(subj)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]), critical=False)
                .sign(key, hashes.SHA256())
            )
            cert_p = os.path.join(td, "cert.pem")
            key_p = os.path.join(td, "key.pem")
            with open(cert_p, "wb") as f: f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(key_p, "wb") as f: f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))

            srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            srv_ctx.load_cert_chain(certfile=cert_p, keyfile=key_p)
            srv = ThreadedHttpsSrv(("127.0.0.1", 0), HttpsRangeHandler)
            srv.socket = srv_ctx.wrap_socket(srv.socket, server_side=True)
            threading.Thread(target=srv.serve_forever, daemon=True).start()

            cli_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            cli_ctx.check_hostname = False
            cli_ctx.verify_mode = ssl.CERT_NONE
            done, errs = threading.Event(), []
            dest = os.path.join(td, "https_out.bin")
            try:
                eng = TurboDownloadEngine(
                    f"https://127.0.0.1:{srv.server_address[1]}/https_out.bin",
                    dest, max_connections=4, ssl_context=cli_ctx,
                    on_complete=lambda *a: done.set(),
                    on_error=lambda e: (errs.append(e), done.set()),
                )
                eng.start()
                deadline = time.monotonic() + 8.0
                while time.monotonic() < deadline and sum(c.downloaded_bytes for c in eng.chunks) < 64 * 1024:
                    time.sleep(0.02)
                for _ in range(3):
                    time.sleep(0.05)
                    eng.pause()
                    self.assertTrue(eng.is_paused)
                    self.assertEqual(eng.current_speed, 0.0)
                    time.sleep(0.04)
                    eng.resume()
                    self.assertFalse(eng.is_paused)
                write_delay[0] = 0.0
                self.assertTrue(done.wait(timeout=15.0))
                self.assertEqual(errs, [])
                with open(dest, "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), expected_sha)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_ui_speed_throttle_neon_bar_scale_and_win32_atomic_resize(self):
        """Verifies 0.35s speed/ETA UI throttle, neon bar & empty card fast drag scaling, and WM_SETREDRAW + release redraw."""
        from faqih_downloader.ui.panels.kanban_card_graphics import draw_neon_progress_bar
        from faqih_downloader.ui.panels.kanban_cards import create_empty_state
        from faqih_downloader.ui.controllers.window_resize_mixin import WindowResizeMixin
        from faqih_downloader.ui.controllers.window_controller import WindowChromeMixin

        class FakeApp(DownloadCallbacksMixin):
            def __init__(self):
                self.root = MagicMock()
                self.root.winfo_exists.return_value = True
                self.root.after.side_effect = lambda _ms, fn: fn()
                self.engine = None
                self.card_speed = MagicMock()
                self.card_size = MagicMock()
                self.card_eta = MagicMock()
                self.card_threads = MagicMock()
                self.update_kanban_active_stream = MagicMock()
                self._draw_main_progress = MagicMock()

        app = FakeApp()
        with patch("faqih_downloader.ui.controllers.download_callbacks_mixin.time.monotonic", side_effect=[10.0, 10.1, 10.4]):
            app._engine_progress_cb(100, 1000, 1024 * 1024, "00:00:10", 2)
            first_spd = app.card_speed.configure.call_args.kwargs["text"]
            app._engine_progress_cb(200, 1000, 5 * 1024 * 1024, "00:00:02", 2)
            throttled_spd = app.card_speed.configure.call_args.kwargs["text"]
            self.assertEqual(throttled_spd, first_spd)
            app._engine_progress_cb(400, 1000, 5 * 1024 * 1024, "00:00:02", 2)
            updated_spd = app.card_speed.configure.call_args.kwargs["text"]
            self.assertEqual(updated_spd, "5.00 MB/s")

        root = tk.Tk()
        try:
            cv_prog = tk.Canvas(root, width=160, height=6)
            cv_prog.pack()
            root.update()
            draw_neon_progress_bar(cv_prog, 0.5)
            cv_prog._last_prog_w = 160
            root._is_resizing_window = True
            with patch.object(cv_prog, "winfo_width", return_value=320), \
                 patch.object(cv_prog, "scale", wraps=cv_prog.scale) as mock_scale, \
                 patch.object(cv_prog, "delete", wraps=cv_prog.delete) as mock_del:
                draw_neon_progress_bar(cv_prog, 0.5)
                mock_scale.assert_called_once_with("all", 0, 0, 2.0, 1.0)
                mock_del.assert_not_called()
                self.assertEqual(cv_prog._last_prog_w, 320)

            class AtomicResizeDummy(WindowChromeMixin, WindowResizeMixin):
                def __init__(self, r, vcv):
                    self.root = r
                    self.vault_cards_canvas = vcv
                    self.width, self.height = 850, 650

            vcv = MagicMock()
            vcv.winfo_exists.return_value = True
            vcv.winfo_width.return_value = 300
            vcv._win_id = 42
            rd = AtomicResizeDummy(root, vcv)
            with patch.object(root, "geometry", wraps=root.geometry) as mock_geo, \
                 patch.object(root, "update_idletasks", wraps=root.update_idletasks) as mock_uit:
                rd._apply_resize_geometry(920, 680, 10, 10)
                mock_geo.assert_called_once_with("920x680+10+10")
                vcv.itemconfigure.assert_called_once_with(42, width=300)
                mock_uit.assert_called_once()

            # Verify create_empty_state updates synchronously during drag via _fast_rect + coords without after()/delete()
            empty_cv = create_empty_state(root, "⏳", "Empty", "Waiting")
            root.update()
            self.assertGreaterEqual(empty_cv._last_size[0], 100)
            root._is_resizing_window = True
            with patch.object(empty_cv, "after") as mock_after:
                root.geometry("600x680")
                root.update()
                mock_after.assert_not_called()
                self.assertIsNotNone(empty_cv._fast_rect)
                with patch.object(empty_cv, "delete") as mock_emp_del, \
                     patch.object(empty_cv, "coords", wraps=empty_cv.coords) as mock_emp_coords:
                    root.geometry("760x680")
                    root.update()
                    mock_emp_del.assert_not_called()
                    self.assertGreaterEqual(mock_emp_coords.call_count, 4)

            # Verify LedEqualizerMatrix stores true 1% level without clamping to 8%
            from faqih_downloader.ui.components.led_matrix import LedEqualizerMatrix
            led_m = LedEqualizerMatrix(root, height=40)
            led_m.pack(fill=tk.X)
            root.update()
            c_1pct = DownloadChunk(0, 0, 9999, downloaded_bytes=100, status="active")
            with patch.object(led_m.canvas, "create_text", wraps=led_m.canvas.create_text) as mock_ct:
                led_m.update_from_chunks([c_1pct], active_count=1, is_active=True, max_lanes=1)
                self.assertAlmostEqual(led_m._levels[0], 0.01, places=4)
                self.assertTrue(any(kw.get("text") == "1%" for _, kw in mock_ct.call_args_list))

            # Verify _on_resize_release restores empty state rounded card and neon progress bar crisp drawing
            with patch("faqih_downloader.ui.panels.kanban_card_graphics.draw_neon_progress_bar", wraps=draw_neon_progress_bar) as mock_prog_rel:
                rd._on_resize_release()
                self.assertFalse(root._is_resizing_window)
                self.assertIsNone(empty_cv._fast_rect)
                mock_prog_rel.assert_called_with(cv_prog, 0.5)

            # Verify engine_workers preserves lowercase 'user-agent' without injecting Chrome UA
            with tempfile.TemporaryDirectory() as td_ua:
                eng_ua = TurboDownloadEngine(
                    "https://rr1.googlevideo.com/videoplayback?id=ua",
                    os.path.join(td_ua, "ua.bin"), max_connections=1,
                    headers={"user-agent": "com.google.android.apps.youtube.vr.oculus/1.56"},
                )
                eng_ua.total_size = 5
                eng_ua.supports_ranges = True
                eng_ua.chunks = [DownloadChunk(0, 0, 4, downloaded_bytes=0, status="pending")]
                eng_ua.chunks[0].part_filepath = os.path.join(td_ua, "ua.part")
                seen_hdrs = {}
                fake_conn = MagicMock()
                fake_resp = MagicMock()
                fake_resp.status = 206
                fake_resp.read.side_effect = [b"hello", b""]
                fake_resp.isclosed.return_value = True
                fake_conn.getresponse.return_value = fake_resp
                def cap_req(method, path, headers=None):
                    seen_hdrs.update(headers or {})
                fake_conn.request.side_effect = cap_req
                with patch.object(eng_ua, "_acquire_pooled_conn", return_value=fake_conn), \
                     patch("faqih_downloader.core.engine_workers._is_urlopen_mocked", return_value=False):
                    eng_ua.is_running = True
                    eng_ua._chunk_worker(eng_ua.chunks[0])
                self.assertNotIn("User-Agent", seen_hdrs)
                self.assertEqual(seen_hdrs.get("user-agent"), "com.google.android.apps.youtube.vr.oculus/1.56")
        finally:
            try: root.destroy()
            except Exception: pass


if __name__ == "__main__":
    unittest.main()
