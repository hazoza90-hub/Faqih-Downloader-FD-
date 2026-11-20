"""
coordinator package: Controls, progress, engine bridge, post-hooks, lifecycle, MP3 transcoding, single-stream, dual-stream, and merger modules.
"""
from .controls import CoordinatorControlsMixin
from .progress import CoordinatorProgressMixin
from .engine_bridge import CoordinatorEngineBridgeMixin
from .post_hooks import CoordinatorPostHooksMixin
from .lifecycle import CoordinatorLifecycleMixin
from .mp3_transcoder import transcode_audio_to_mp3
from .single_stream import run_single_stream_download
from .dual_stream import _drain_engine_workers, run_dual_stream_download
from .dual_merger import merge_dual_streams

__all__ = [
    "CoordinatorControlsMixin",
    "CoordinatorProgressMixin",
    "CoordinatorEngineBridgeMixin",
    "CoordinatorPostHooksMixin",
    "CoordinatorLifecycleMixin",
    "transcode_audio_to_mp3",
    "run_single_stream_download",
    "_drain_engine_workers",
    "run_dual_stream_download",
    "merge_dual_streams",
]
