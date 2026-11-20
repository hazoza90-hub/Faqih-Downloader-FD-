"""
chunks package for Faqih Downloader (FD).
Provides chunk visualizer, tabbed consoles, and context actions.
"""
from faqih_downloader.ui.panels.metrics_panel import MetricsPanelMixin
from .visualizer import ChunksVisualizerMixin
from .tabs_builder import ChunksTabsBuilderMixin
from .context_menu import ChunksContextMenuMixin
from .panel import ChunksPanelMixin

__all__ = [
    "MetricsPanelMixin",
    "ChunksVisualizerMixin",
    "ChunksTabsBuilderMixin",
    "ChunksContextMenuMixin",
    "ChunksPanelMixin",
]
