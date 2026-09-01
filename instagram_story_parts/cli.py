"""Command-line adapter for the application service."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .domain import SplitRequest
from .media import FFmpegSegmentExporter, FFprobeMediaProbe, default_locator
from .service import ProgressUpdate, VideoSplitService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a video into social-media-sized segments."
    )
    parser.add_argument("video", type=Path, help="Input video file")
    parser.add_argument("-o", "--output-dir", type=Path)
    parser.add_argument("-d", "--duration", type=float, default=60.0)
    parser.add_argument("-f", "--offset", type=float, default=0.0)
    parser.add_argument("--ffmpeg-dir", type=Path)
    parser.add_argument("--allow-long-last", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ffmpeg_dir:
        default_locator.configure(args.ffmpeg_dir)

    request = SplitRequest(
        args.video,
        args.output_dir,
        args.duration,
        args.offset,
        args.overwrite,
        args.workers,
    )
    service = VideoSplitService(
        FFprobeMediaProbe(default_locator),
        FFmpegSegmentExporter(default_locator),
    )

    def progress(update: ProgressUpdate) -> None:
        percent = int(update.completed / update.total * 100) if update.total else 100
        print(
            f"\rProgress: {update.completed}/{update.total} ({percent}%)",
            end="",
            flush=True,
        )

    def allow_long(length: float) -> bool:
        if args.allow_long_last:
            return True
        try:
            answer = input(
                f"The last part will be {length:.1f}s (>{args.duration:g}s). "
                "Allow it? [y/N] "
            )
            return answer.strip().lower().startswith("y")
        except EOFError:
            return False

    result = service.split(request, progress, allow_long)
    print(f"\nCompleted {result.completed_count} part(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
