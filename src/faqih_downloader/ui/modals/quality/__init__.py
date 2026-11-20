"""
quality package for Faqih Downloader (FD).
Provides video/audio format and stream picker modal.
"""
from .layout_builder import QualityModalLayoutMixin
from .selection_handlers import QualityModalSelectionMixin
from .action_handlers import QualityModalActionsMixin
from .modal import QualitySelectionModal, _BaseToplevel

__all__ = [
    "QualityModalLayoutMixin",
    "QualityModalSelectionMixin",
    "QualityModalActionsMixin",
    "QualitySelectionModal",
    "_BaseToplevel",
]
