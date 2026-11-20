"""
VaultRestoreScrollMixin: Smooth scrolling and debounced canvas scrollregion updates.
"""
from __future__ import annotations
from typing import Tuple


class VaultRestoreScrollMixin:
    """Provides debounced scrollregion configuration and eased smooth scrolling for VaultRestoreModal."""

    def _schedule_scrollregion_update(self, event=None):
        """Debounces canvas scrollregion updates so rapid additions batch bbox('all')."""
        if getattr(self, "_scrollregion_pending", False):
            return
        self._scrollregion_pending = True
        try:
            self.after_idle(self._apply_scrollregion)
        except Exception:
            self._scrollregion_pending = False

    def _apply_scrollregion(self):
        self._scrollregion_pending = False
        if getattr(self, "_closing", False):
            return
        try:
            if self.winfo_exists() and hasattr(self, "canvas") and self.canvas.winfo_exists():
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _get_scroll_bounds(self) -> Tuple[float, float]:
        try:
            if hasattr(self, "canvas") and self.canvas.winfo_exists() and hasattr(self.canvas, "yview"):
                t, b = self.canvas.yview()
                return float(t), float(b)
            if hasattr(self, "scrollbar") and self.scrollbar.winfo_exists():
                t, b = self.scrollbar.get()
                return float(t), float(b)
        except Exception:
            pass
        return 0.0, 1.0

    def _on_mousewheel(self, event):
        """Scrolls canvas smoothly with instant direction reversal and edge clamping."""
        if getattr(self, "_closing", False):
            return
        try:
            if not self.winfo_exists() or not hasattr(self, "canvas") or not self.canvas.winfo_exists():
                return
            top, btm = self._get_scroll_bounds()
            if top <= 0.0 and btm >= 1.0:
                self._scroll_steps_remaining = 0
                return
            notch = int(-1 * (event.delta / 120))
            if notch == 0:
                return
            if (notch < 0 and self._scroll_steps_remaining > 0) or (notch > 0 and self._scroll_steps_remaining < 0):
                self._scroll_steps_remaining = 0
            if (notch < 0 and top <= 0.0) or (notch > 0 and btm >= 1.0):
                self._scroll_steps_remaining = 0
                return
            self._scroll_steps_remaining = max(-90, min(90, self._scroll_steps_remaining + notch * 18))
            if self._scroll_timer_id is None:
                self._step_smooth_scroll()
        except Exception:
            pass

    def _step_smooth_scroll(self):
        """Executes smooth 10ms eased interpolation step for mousewheel scrolling."""
        self._scroll_timer_id = None
        if getattr(self, "_closing", False):
            self._scroll_steps_remaining = 0
            return
        try:
            if not self.winfo_exists() or not hasattr(self, "canvas") or not self.canvas.winfo_exists():
                self._scroll_steps_remaining = 0
                return
            top, btm = self._get_scroll_bounds()
            if top <= 0.0 and btm >= 1.0 or self._scroll_steps_remaining == 0:
                self._scroll_steps_remaining = 0
                return
            step = int(self._scroll_steps_remaining * 0.35) or (1 if self._scroll_steps_remaining > 0 else -1)
            if (step < 0 and top <= 0.0) or (step > 0 and btm >= 1.0):
                self._scroll_steps_remaining = 0
                return
            self.canvas.yview_scroll(step, "units")
            self._scroll_steps_remaining -= step
            if self._scroll_steps_remaining != 0:
                self._scroll_timer_id = self.after(10, self._step_smooth_scroll)
        except Exception:
            self._scroll_steps_remaining = 0
