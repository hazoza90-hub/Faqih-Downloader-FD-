"""
Engine supervisor loop mixin: chunk scheduling, worker lifecycle, dynamic splitting, and completion assembly.
"""
import os
import time
import threading
import shutil

from ..chunk import DownloadChunk


class EngineSupervisorMixin:
    """Master supervisor loop coordinating worker threads, dynamic split triggers, and final file assembly."""

    def _supervisor_loop(self):
        """Master supervisor: manages initial connection, dynamic splitting, and assembly."""
        try:
            is_resuming = bool(
                getattr(self, "_resume_mode", False)
                or (self.chunks and any(c.downloaded_bytes > 0 for c in self.chunks))
            )

            # If not in resume mode, check if state file exists in temp_dir to restore
            if not is_resuming and not self.chunks and os.path.exists(self.temp_dir):
                if self.load_state() and self.chunks:
                    is_resuming = True

            if not is_resuming:
                if not getattr(self, "_has_pre_probed", False):
                    self.probe()
                else:
                    if os.path.isdir(self.destination_path) or self.destination_path.endswith(("/", "\\")):
                        self.destination_path = os.path.join(self.destination_path, self.filename or "download.bin")
                        self.temp_dir = self.destination_path + ".sd_parts"
                    if self.supports_ranges and self.total_size > 0:
                        self.log(f"Server supports HTTP 206 Multi-threading! Total Size: {self.total_size / (1024*1024):.2f} MB ({self.total_size:,} bytes).")
                    else:
                        self.log(f"Server does not support HTTP Range requests. Size: {self.total_size:,} bytes. Single-stream fallback active.")

                if self.total_size > 0:
                    dest_dir = os.path.dirname(os.path.abspath(self.destination_path)) or "."
                    while dest_dir and not os.path.exists(dest_dir):
                        parent = os.path.dirname(dest_dir)
                        if parent == dest_dir:
                            break
                        dest_dir = parent
                    try:
                        if shutil.disk_usage(dest_dir or ".").free < self.total_size:
                            raise OSError("Insufficient disk space for download")
                    except OSError as oe:
                        if "Insufficient disk space" in str(oe):
                            raise
                    except Exception:
                        pass

                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
                os.makedirs(self.temp_dir, exist_ok=True)

                # Pre-split contiguous chunks immediately at start if multi-connection ranges supported
                with self._lock:
                    self.chunks.clear()
                    if self.supports_ranges and self.allow_dynamic_split and self.total_size >= self.min_split_threshold and self.max_connections > 1:
                        init_parts = min(self.max_connections, max(1, self.total_size // self.min_split_threshold))
                        part_sz = self.total_size // init_parts
                        for i in range(init_parts):
                            s_b = i * part_sz
                            e_b = (self.total_size - 1) if (i == init_parts - 1) else ((i + 1) * part_sz - 1)
                            self.chunks.append(DownloadChunk(i, s_b, e_b, part_filepath=os.path.join(self.temp_dir, f"{self.filename}.part_{i}")))
                    else:
                        init_end = (self.total_size - 1) if self.total_size > 0 else 0
                        self.chunks.append(DownloadChunk(0, 0, init_end, part_filepath=os.path.join(self.temp_dir, f"{self.filename}.part_0")))
                    to_spawn = list(self.chunks)

                self.save_state()
                for c in to_spawn:
                    self._spawn_worker(c)
            else:
                self._prepare_resume_chunks()

            # Scheduling & Dynamic Splitting Loop
            while self.is_running and not self._cancel_event.is_set():
                ramp_up = (self.supports_ranges and len(self.chunks) < self.max_connections)
                time.sleep(0.02 if ramp_up else 0.08)

                if self.is_paused:
                    self.current_speed = 0.0
                    continue

                # Schedule pending chunks if worker slots available
                with self._lock:
                    active_count = sum(1 for c in self.chunks if c.status == "active")
                    if active_count < self.max_connections:
                        pending = [c for c in self.chunks if c.status == "pending"]
                        for c in pending[:self.max_connections - active_count]:
                            self._spawn_worker(c)

                # Check if we should dynamically split active chunks
                if self.supports_ranges and self.total_size > 0:
                    self._dynamic_split_check()

                # Update progress & calculate real-time speed
                self._update_progress_metrics()

                # Check completion or failure
                with self._lock:
                    all_finished = all(c.status in ("completed", "failed") for c in self.chunks)
                    any_failed = any(c.status == "failed" for c in self.chunks)

                # Fail fast if a chunk failed permanently
                if any_failed or self._error_abort_event.is_set():
                    failed_chunks = [c for c in self.chunks if c.status == "failed"]
                    err = failed_chunks[0].error_msg if failed_chunks else "Chunk transfer failure"
                    self._stop_workers_for_error()
                    self.save_state()
                    raise RuntimeError(f"Download failed in chunk: {err}")

                if all_finished:
                    break

            if self._cancel_event.is_set():
                return

            with self._lock:
                _workers_to_join = list(self.active_workers)
            for _w in _workers_to_join:
                if _w.is_alive() and _w != threading.current_thread():
                    _w.join(timeout=5.0)

            # Perform strict sequential assembly
            self.assemble()

            active_elapsed = self._accumulated_active_sec
            if self._last_active_start_mono is not None:
                active_elapsed += max(0.0, time.monotonic() - self._last_active_start_mono)

            elapsed = max(0.01, active_elapsed) if active_elapsed > 0.001 else max(0.01, time.time() - self.start_time)

            total_downloaded = sum(c.downloaded_bytes for c in self.chunks)
            if self.total_size > 0:
                total_downloaded = max(total_downloaded, self.total_size)
            session_transferred = max(0, total_downloaded - getattr(self, "_session_start_bytes", 0))
            bytes_for_speed = session_transferred if session_transferred > 0 else (self.total_size if self.total_size > 0 else total_downloaded)

            avg_speed = (bytes_for_speed / elapsed) if elapsed > 0 else 0
            speed_str = f"{avg_speed / (1024*1024):.2f} MB/s" if avg_speed >= 1024*1024 else f"{avg_speed / 1024:.1f} KB/s"
            self.log(f"[SUCCESS] Download finished successfully in {elapsed:.1f}s (Average Speed: {speed_str})!")
            self.is_running = False
            if self.on_complete:
                self.on_complete(self.destination_path, self.total_size, elapsed)
        except Exception as e:
            self.is_running = False
            self.log(f"[ERROR] {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.is_running = False
            if self._cancel_event.is_set():
                self.cleanup_temp_files()
