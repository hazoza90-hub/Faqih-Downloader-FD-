"""
Backward-compatibility shim for quality_modal.
Logic has moved to faqih_downloader.ui.modals.quality.
"""
from .quality import (
    QualitySelectionModal,
    _BaseToplevel,
    QualityModalLayoutMixin,
    QualityModalSelectionMixin,
    QualityModalActionsMixin,
)

__all__ = [
    "QualitySelectionModal",
    "_BaseToplevel",
    "QualityModalLayoutMixin",
    "QualityModalSelectionMixin",
    "QualityModalActionsMixin",
]
