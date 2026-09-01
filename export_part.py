"""Export one segment; retained as a small compatibility utility."""

import argparse
from pathlib import Path
from typing import Any, Optional

from instagram_story_parts.domain import Segment, SplitRequest
from instagram_story_parts.media import (
    FFmpegSegmentExporter,
    FFprobeMediaProbe,
    default_locator,
)

VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"
AUDIO_FPS = 44100
PRESET = "medium"
THREADS = 4
AUDIO_CHANNELS = 2


def check_audio_stream(
    video_path: str, ffprobe_path: str | None = None
) -> tuple[bool, Optional[dict[str, Any]]]:
    media = FFprobeMediaProbe(default_locator).probe(Path(video_path))
    return media.has_audio, ({"codec_type": "audio"} if media.has_audio else None)


def verify_output_audio(
    output_path: str, ffprobe_path: str | None = None
) -> tuple[bool, Optional[dict[str, Any]]]:
    return check_audio_stream(output_path, ffprobe_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export one video segment.")
    parser.add_argument("video", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("end", type=float)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.start < 0 or args.end <= args.start:
        parser.error("start must be non-negative and end must be greater than start")

    request = SplitRequest(args.video, args.output.parent, args.end - args.start)
    media = FFprobeMediaProbe(default_locator).probe(args.video)
    segment = Segment(1, args.start, args.end, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    FFmpegSegmentExporter(default_locator).export(request, segment, media)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
