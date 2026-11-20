"""
EngineWorkersMixin: Composition mixin uniting chunk worker loops, dynamic splitting,
progress metrics, and resumer capabilities.
"""
from .chunk_worker import EngineChunkWorkerMixin
from .dynamic_split import EngineDynamicSplitMixin
from .metrics import EngineMetricsMixin
from .resumer import EngineResumerMixin


class EngineWorkersMixin(
    EngineChunkWorkerMixin,
    EngineDynamicSplitMixin,
    EngineMetricsMixin,
    EngineResumerMixin
):
    """Composition mixin for background worker thread pooling and dynamic chunk splitting."""
    pass
