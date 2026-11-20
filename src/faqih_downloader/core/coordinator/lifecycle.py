"""
lifecycle.py: Thin composition mixin aggregating coordinator controls, progress, engine bridge, and post-hooks.
"""
from .controls import CoordinatorControlsMixin
from .progress import CoordinatorProgressMixin
from .engine_bridge import CoordinatorEngineBridgeMixin
from .post_hooks import CoordinatorPostHooksMixin


class CoordinatorLifecycleMixin(
    CoordinatorControlsMixin,
    CoordinatorProgressMixin,
    CoordinatorEngineBridgeMixin,
    CoordinatorPostHooksMixin,
):
    """Composite lifecycle mixin combining controls, progress, engine bridge, and post-hooks."""


__all__ = ["CoordinatorLifecycleMixin"]
