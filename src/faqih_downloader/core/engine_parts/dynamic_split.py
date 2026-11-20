"""
EngineDynamicSplitMixin: Adaptive Dynamic Midpoint Splitting Mechanism.
"""
import os
from ..chunk import DownloadChunk


class EngineDynamicSplitMixin:
    """Provides adaptive dynamic midpoint chunk splitting mechanism for accelerating transfers."""

    def _dynamic_split_check(self):
        """TDM Adaptive Dynamic Midpoint Splitting Mechanism."""
        with self._lock:
            if not self.allow_dynamic_split or not getattr(self, "supports_ranges", False):
                return

        split_any = False
        while True:
            if self._is_stopped():
                break
            new_chunk = candidate = None
            split_start = old_end = new_id = 0
            with self._lock:
                if sum(1 for c in self.chunks if c.status in ("active", "pending")) >= self.max_connections:
                    break
                candidates = [c for c in self.chunks if c.status in ("active", "pending") and c.remaining_bytes >= self.min_split_threshold * 2] or \
                             [c for c in self.chunks if c.status in ("active", "pending") and c.remaining_bytes >= self.min_split_threshold]
                if not candidates:
                    break
                candidate = max(candidates, key=lambda c: c.remaining_bytes)
                with candidate.lock:
                    remaining = candidate.end_byte - (candidate.start_byte + candidate.downloaded_bytes) + 1
                    half = remaining // 2
                    if remaining < self.min_split_threshold or half < 32768 or candidate.status not in ("active", "pending"):
                        break
                    split_start = candidate.start_byte + candidate.downloaded_bytes + half
                    old_end = candidate.end_byte
                    candidate.end_byte = split_start - 1

                new_id = len(self.chunks)
                part_path = os.path.join(self.temp_dir, f"{os.path.basename(self.destination_path)}.part_{new_id}")
                new_chunk = DownloadChunk(new_id, split_start, old_end, 0, "pending", part_filepath=part_path)
                self.chunks.append(new_chunk)

            if new_chunk and candidate:
                split_any = True
                self.log(f"[SPLIT] Fast Ramp-Up Split: Chunk #{candidate.chunk_id} split! Spawned Chunk #{new_id} [{split_start:,} - {old_end:,}]")
                self._spawn_worker(new_chunk)
            else:
                break

        if split_any:
            self.save_state()
