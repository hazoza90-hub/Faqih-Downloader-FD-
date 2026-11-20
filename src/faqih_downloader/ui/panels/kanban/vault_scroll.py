"""
KanbanVaultScrollMixin: Smooth mousewheel scrolling and wheel routing for Completed Vault.
"""
from __future__ import annotations
from typing import Any, Tuple


class KanbanVaultScrollMixin:
    """Provides smooth scrolling with eased interpolation and global mousewheel routing for Completed Vault."""

    def _get_vault_scroll_bounds(self, cv: Any) -> Tuple[float, float]:
        try:
            if hasattr(cv, "yview"):
                t, b = cv.yview()
                return float(t), float(b)
        except Exception:
            pass
        return 0.0, 1.0

    def _on_vault_mousewheel(self, event: Any):
        """Smoothly scrolls Completed Vault canvas with instant direction reversal and edge guards."""
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists() or not getattr(event, "delta", None):
            return
        top, btm = self._get_vault_scroll_bounds(cv)
        if top <= 0.0 and btm >= 1.0:
            self._vault_scroll_steps = 0
            return
        notch = int(-1 * (event.delta / 120))
        if notch == 0:
            return
        steps = getattr(self, "_vault_scroll_steps", 0)
        if (notch < 0 and steps > 0) or (notch > 0 and steps < 0):
            steps = 0
        if (notch < 0 and top <= 0.0) or (notch > 0 and btm >= 1.0):
            self._vault_scroll_steps = 0
            return
        self._vault_scroll_steps = max(-70, min(70, steps + notch * 14))
        if getattr(self, "_vault_scroll_timer", None) is None:
            self._step_vault_smooth_scroll()

    def _step_vault_smooth_scroll(self):
        """Performs 10ms interpolation step for vault canvas smooth scrolling."""
        self._vault_scroll_timer = None
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists():
            self._vault_scroll_steps = 0
            return
        top, btm = self._get_vault_scroll_bounds(cv)
        steps = getattr(self, "_vault_scroll_steps", 0)
        if (top <= 0.0 and btm >= 1.0) or steps == 0:
            self._vault_scroll_steps = 0
            return
        step = int(steps * 0.35) or (1 if steps > 0 else -1)
        if (step < 0 and top <= 0.0) or (step > 0 and btm >= 1.0):
            self._vault_scroll_steps = 0
            return
        try:
            cv.yview_scroll(step, "units")
            self._vault_scroll_steps -= step
            if self._vault_scroll_steps != 0:
                self._vault_scroll_timer = cv.after(10, self._step_vault_smooth_scroll)
        except Exception:
            self._vault_scroll_steps = 0

    def _on_global_col3_wheel(self, event: Any):
        """Global handler forwarding mousewheel to modal Toplevel or Completed Vault."""
        cv = getattr(self, "vault_cards_canvas", None)
        if not cv or not cv.winfo_exists() or not getattr(event, "delta", None):
            return
        try:
            target = cv.winfo_containing(event.x_root, event.y_root) or getattr(event, "widget", None)
            if target is not None and hasattr(target, "winfo_toplevel") and hasattr(cv, "winfo_toplevel"):
                top_win = target.winfo_toplevel()
                if top_win is not cv.winfo_toplevel() and hasattr(top_win, "_on_mousewheel"):
                    top_win._on_mousewheel(event)
                    return
            curr = target
            allowed = (cv, getattr(self, "vault_cards_container", None), getattr(self, "col3_frame", None))
            while curr is not None:
                if curr in allowed:
                    self._on_vault_mousewheel(event)
                    return
                curr = getattr(curr, "master", None)
        except Exception:
            pass
