"""
MediaOptionsBarMixin composite mixin combining layout, state sync, event handlers, and media actions.
"""
from ..media_options_actions import MediaOptionsActionsMixin
from .layout_builder import MediaBarLayoutMixin
from .state_sync import MediaBarStateSyncMixin
from .event_handlers import MediaBarEventHandlersMixin


class MediaOptionsBarMixin(
    MediaBarLayoutMixin,
    MediaBarStateSyncMixin,
    MediaBarEventHandlersMixin,
    MediaOptionsActionsMixin
):
    """Mixin providing the Main Window Media Settings Bar for quality, dubbing, and subtitles."""
    pass


__all__ = ["MediaOptionsBarMixin"]
