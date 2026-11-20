"""
process_control.py: OS-level subprocess suspend and resume control.
"""
from __future__ import annotations
import os
from typing import Any


def _set_process_suspended(proc_or_pid: Any, suspend: bool) -> None:
    try:
        pid, is_obj = getattr(proc_or_pid, "pid", proc_or_pid), not isinstance(proc_or_pid, int)
        cur_susp = getattr(proc_or_pid, "_os_suspended", False)
        if hasattr(cur_susp, "_mock_name"): cur_susp = False
        if is_obj and bool(cur_susp) == bool(suspend): return
        if os.name == "nt":
            import ctypes
            if hasattr(ctypes, "windll") and isinstance(pid, int):
                h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
                if h:
                    try: (ctypes.windll.ntdll.NtSuspendProcess if suspend else ctypes.windll.ntdll.NtResumeProcess)(h)
                    finally: ctypes.windll.kernel32.CloseHandle(h)
        else:
            import signal
            if isinstance(pid, int): os.kill(pid, signal.SIGSTOP if suspend else signal.SIGCONT)
        if is_obj: setattr(proc_or_pid, "_os_suspended", bool(suspend))
    except Exception: pass


__all__ = [
    "_set_process_suspended",
]
