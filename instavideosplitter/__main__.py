"""Command-line interface for InstaVideoSplitter.

Run as a module:
    python -m instavideosplitter [OPTIONS] VIDEO
    python -m instavideosplitter --gui

Or via the installed entry point:
    instavideosplitter [OPTIONS] VIDEO
"""

import argparse
import logging
import sys

from . import __version__
from .constants import MAX_WORKERS, SEGMENT_DURATION_DEFAULT


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instavideosplitter",
        description="Split a video into Instagram Story-compatible segments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s myvideo.mp4
  %(prog)s myvideo.mp4 -d 30 -o ./clips
  %(prog)s myvideo.mp4 -f -1.5 --allow-long-last
  %(prog)s myvideo.mp4 -d 60 -w 2 --quiet
  %(prog)s --gui
        """,
    )

    # Positional
    parser.add_argument(
        "video",
        nargs="?",
        metavar="VIDEO",
        help="Input video file to split.",
    )

    # Splitting options
    split = parser.add_argument_group("splitting options")
    split.add_argument(
        "-d", "--duration",
        type=int,
        default=SEGMENT_DURATION_DEFAULT,
        metavar="SECONDS",
        help=f"Segment length in seconds. (default: {SEGMENT_DURATION_DEFAULT})",
    )
    split.add_argument(
        "-o", "--output-dir",
        metavar="DIR",
        help="Output directory. (default: same folder as the input video)",
    )
    split.add_argument(
        "-f", "--offset",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help=(
            "Seconds added to every keyframe-aligned cut point. "
            "Negative values shift cuts earlier. (default: 0.0)"
        ),
    )
    split.add_argument(
        "-w", "--workers",
        type=int,
        default=MAX_WORKERS,
        metavar="N",
        help=f"Maximum parallel export processes. (default: {MAX_WORKERS})",
    )
    split.add_argument(
        "--allow-long-last",
        action="store_true",
        help=(
            "Automatically keep the last segment even when it is up to "
            "~10%% longer than --duration."
        ),
    )

    # ffmpeg override
    parser.add_argument(
        "--ffmpeg-dir",
        metavar="DIR",
        help=(
            "Directory containing the ffmpeg/ffprobe binaries. "
            "Overrides the FFMPEG_DIR environment variable."
        ),
    )

    # Output verbosity (mutually exclusive)
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level output.",
    )
    verbosity.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors.",
    )

    # GUI / version
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface instead of processing a file.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


# ── Logging setup ─────────────────────────────────────────────────────────────

def _configure_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv: list = None) -> None:  # noqa: ANN001
    """Parse arguments and run the requested action.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose, args.quiet)

    # ── GUI mode ──────────────────────────────────────────────────────────────
    if args.gui:
        try:
            from .gui import main as gui_main
            gui_main()
        except ImportError as exc:
            logging.error(
                "GUI dependencies not installed. "
                "Run: pip install customtkinter pillow opencv-python\n%s", exc
            )
            sys.exit(1)
        return

    # ── CLI mode ──────────────────────────────────────────────────────────────
    if not args.video:
        parser.print_help()
        sys.exit(0)

    if args.ffmpeg_dir:
        from .ffmpeg_config import set_ffmpeg_dir
        set_ffmpeg_dir(args.ffmpeg_dir)

    if args.duration <= 0:
        parser.error("--duration must be a positive integer.")
    if args.workers < 1:
        parser.error("--workers must be at least 1.")

    from .core import trim_video_to_parts

    def _allow(length: float) -> bool:
        if args.allow_long_last:
            return True
        try:
            ans = input(
                f"\n  Last segment is {length:.1f}s (>{args.duration}s). Keep it? [y/N] "
            )
            return ans.strip().lower().startswith("y")
        except EOFError:
            return False

    def _progress(completed: int, total: int) -> None:
        if not args.quiet:
            pct = int(completed / total * 100)
            bar = "█" * pct + "░" * (100 - pct)
            print(f"\r  [{bar[:30]}] {pct:3d}%  ({completed}/{total})", end="", flush=True)

    logging.info("InstaVideoSplitter %s", __version__)
    logging.info("Input : %s", args.video)
    logging.info("Output: %s", args.output_dir or "(same as input)")
    logging.info("Segment: %ds  offset: %+.1fs  workers: %d", args.duration, args.offset, args.workers)

    try:
        num_parts = trim_video_to_parts(
            args.video,
            output_dir=args.output_dir,
            progress_callback=_progress,
            segment_duration=args.duration,
            offset=args.offset,
            workers=args.workers,
            ask_allow_long_last_part=_allow,
        )
        if not args.quiet:
            print()  # newline after progress bar
        logging.info("Done — %d part(s) written.", num_parts)
    except FileNotFoundError:
        logging.error("File not found: %s", args.video)
        sys.exit(1)
    except ValueError as exc:
        logging.error("Invalid input: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.error("Interrupted.")
        sys.exit(130)
    except Exception as exc:
        logging.error("Unexpected error: %s", exc)
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
