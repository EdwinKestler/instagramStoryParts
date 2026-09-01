"""Compatibility entry point for the modular application package."""

from pathlib import Path
from typing import Callable, Optional

from ffprobe_utils import run_ffprobe
from instagram_story_parts.cli import main
from instagram_story_parts.domain import SplitRequest
from instagram_story_parts.media import (
    FFmpegSegmentExporter,
    FFprobeMediaProbe,
    default_locator,
)
from instagram_story_parts.planner import SegmentPlanner
from instagram_story_parts.service import ProgressUpdate, VideoSplitService

SEGMENT_DURATION_DEFAULT = 60
MAX_WORKERS = 4


def get_keyframes(video_path: str, ffprobe_path: str) -> list[float]:
    data = run_ffprobe(
        ffprobe_path,
        [
            "-select_streams", "v:0",
            "-skip_frame", "nokey",
            "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time,pts_time,pkt_pts_time",
        ],
        video_path,
    )
    keyframes: list[float] = []
    for frame in (data or {}).get("frames", []):
        value = (
            frame.get("best_effort_timestamp_time")
            or frame.get("pts_time")
            or frame.get("pkt_pts_time")
        )
        if value is not None:
            keyframes.append(float(value))
    return keyframes


def adjust_to_keyframe(time: float, keyframes: list[float]) -> float:
    return SegmentPlanner.nearest_keyframe(time, keyframes)


def trim_video_to_parts(
    video_path: str,
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    segment_duration: int = SEGMENT_DURATION_DEFAULT,
    offset: float = 0.0,
    ask_allow_long_last_part: Optional[Callable[[float], bool]] = None,
) -> int:
    """Legacy facade around :class:`VideoSplitService`."""
    request = SplitRequest(
        video_path=Path(video_path),
        output_dir=Path(output_dir) if output_dir else None,
        segment_duration=float(segment_duration),
        offset=offset,
        max_workers=MAX_WORKERS,
    )
    service = VideoSplitService(
        FFprobeMediaProbe(default_locator),
        FFmpegSegmentExporter(default_locator),
    )

    def report(update: ProgressUpdate) -> None:
        if progress_callback:
            progress_callback(update.completed, update.total)

    result = service.split(request, report, ask_allow_long_last_part)
    return result.completed_count


if __name__ == "__main__":
    raise SystemExit(main())
