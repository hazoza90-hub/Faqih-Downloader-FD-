"""
Backward-compatibility shim for chunks_panel.
Logic has moved to faqih_downloader.ui.panels.chunks.
"""
from .metrics_panel import MetricsPanelMixin
from .chunks import (
    ChunksPanelMixin,
    ChunksVisualizerMixin,
    ChunksTabsBuilderMixin,
    ChunksContextMenuMixin,
)

__all__ = [
    "ChunksPanelMixin",
    "MetricsPanelMixin",
    "ChunksVisualizerMixin",
    "ChunksTabsBuilderMixin",
    "ChunksContextMenuMixin",
]
