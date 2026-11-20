"""
ChunksPanelMixin: Dynamic chunk visualization, tabbed consoles, and chunk-tree context actions.
"""
from __future__ import annotations
from faqih_downloader.ui.panels.metrics_panel import MetricsPanelMixin
from .visualizer import ChunksVisualizerMixin
from .tabs_builder import ChunksTabsBuilderMixin
from .context_menu import ChunksContextMenuMixin


class ChunksPanelMixin(
    ChunksVisualizerMixin,
    ChunksTabsBuilderMixin,
    ChunksContextMenuMixin,
    MetricsPanelMixin
):
    """
    Mixin providing chunk segment visualization, tab container (chunks, activity log, history),
    and chunk tree context actions. Inherits MetricsPanelMixin.
    """
    pass
