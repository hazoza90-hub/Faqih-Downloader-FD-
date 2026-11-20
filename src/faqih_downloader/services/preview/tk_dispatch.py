"""
tk_dispatch.py: Thread-safe Tkinter main-thread callback dispatcher for preview sessions.
"""
import threading
from typing import Any, Callable


def _schedule_on_tk(session: Any, fn: Callable[[], None], delay_ms: int = 0) -> None:
    app = session.parent_app
    tk_w = getattr(app, "root", None) if app else None
    if not tk_w or not hasattr(tk_w, "after"):
        tk_w = session.modal_ref if (session.modal_ref and hasattr(session.modal_ref, "after")) else None
    if delay_ms <= 0 and app and hasattr(app, "dispatch_to_main_thread"):
        app.dispatch_to_main_thread(fn)
    elif tk_w and hasattr(tk_w, "after"):
        try: tk_w.after(delay_ms, fn)
        except Exception:
            if delay_ms > 0: threading.Timer(delay_ms / 1000.0, fn).start()
            else: fn()
    elif delay_ms > 0: threading.Timer(delay_ms / 1000.0, fn).start()
    else: fn()


__all__ = ["_schedule_on_tk"]
