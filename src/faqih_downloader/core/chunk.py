"""
Download chunk state data class and permissive SSL context provider.
"""
import ssl
import threading
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DownloadChunk:
    """Represents a discrete contiguous byte range of the target file."""
    chunk_id: int
    start_byte: int
    end_byte: int
    downloaded_bytes: int = 0
    status: str = "pending"  # pending, active, completed, failed
    part_filepath: str = ""
    error_msg: str = ""
    retry_count: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def current_byte(self) -> int:
        with self.lock:
            return self.start_byte + self.downloaded_bytes

    @property
    def is_completed(self) -> bool:
        with self.lock:
            return self.status == "completed"

    @is_completed.setter
    def is_completed(self, value: bool):
        with self.lock:
            if value:
                self.status = "completed"
            elif self.status == "completed":
                self.status = "pending"

    @property
    def total_bytes(self) -> int:
        with self.lock:
            return max(0, self.end_byte - self.start_byte + 1)

    @property
    def remaining_bytes(self) -> int:
        with self.lock:
            cur = self.start_byte + self.downloaded_bytes
            return max(0, self.end_byte - cur + 1)

    @property
    def progress_pct(self) -> float:
        with self.lock:
            tot = self.end_byte - self.start_byte + 1
            if tot <= 0:
                return 100.0
            return min(100.0, (self.downloaded_bytes / tot) * 100.0)


# Permissive SSL context cache
_PERMISSIVE_SSL_CONTEXT: Optional[ssl.SSLContext] = None
_SSL_CONTEXT_LOCK = threading.Lock()

def get_permissive_ssl_context() -> ssl.SSLContext:
    """
    Creates or returns a reusable, robust, permissive SSL context that disables
    certificate verification and hostname validation. This resolves expired or
    self-signed TLS certificates (such as archive.org CDN nodes) with zero external pip dependencies.
    """
    global _PERMISSIVE_SSL_CONTEXT
    if _PERMISSIVE_SSL_CONTEXT is None:
        with _SSL_CONTEXT_LOCK:
            if _PERMISSIVE_SSL_CONTEXT is None:
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    _PERMISSIVE_SSL_CONTEXT = ctx
                except Exception:
                    if hasattr(ssl, "_create_unverified_context"):
                        _PERMISSIVE_SSL_CONTEXT = ssl._create_unverified_context()
                    else:
                        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if hasattr(ssl, "PROTOCOL_TLS_CLIENT") else ssl.PROTOCOL_TLS)
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        _PERMISSIVE_SSL_CONTEXT = ctx
    return _PERMISSIVE_SSL_CONTEXT

