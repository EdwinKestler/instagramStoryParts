"""InstaVideoSplitter — split long videos into Instagram Story-compatible segments.

Typical usage
-------------
From Python::

    from instavideosplitter import trim_video_to_parts

    trim_video_to_parts("myvideo.mp4", output_dir="./clips", segment_duration=60)

From the terminal::

    python -m instavideosplitter myvideo.mp4 -d 60 -o ./clips
    python -m instavideosplitter --gui
"""

from .constants import SEGMENT_DURATION_DEFAULT
from .core import adjust_to_keyframe, get_keyframes, trim_video_to_parts

__version__ = "1.0.0-rc1"
__all__ = [
    "trim_video_to_parts",
    "get_keyframes",
    "adjust_to_keyframe",
    "SEGMENT_DURATION_DEFAULT",
    "__version__",
]
