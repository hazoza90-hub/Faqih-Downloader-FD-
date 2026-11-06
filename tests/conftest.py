import os
import sys

# Ensure project root and src/ are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Fix Windows Tcl/Tk library paths to prevent intermittent TclError
tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
if os.path.isdir(tcl_dir):
    os.environ["TCL_LIBRARY"] = tcl_dir
if os.path.isdir(tk_dir):
    os.environ["TK_LIBRARY"] = tk_dir

try:
    import time
    import tkinter as tk
    _RealTk = tk.Tk

    class SafeTk(_RealTk):
        """Wraps tk.Tk with retry logic to withstand transient Windows Tcl file locking."""
        def __init__(self, *args, **kwargs):
            last_err = None
            for attempt in range(5):
                try:
                    super().__init__(*args, **kwargs)
                    return
                except Exception as e:
                    last_err = e
                    time.sleep(0.08)
            if last_err:
                raise last_err

    tk.Tk = SafeTk
except Exception:
    pass
