"""Tests for the __main__ CLI argument parser."""

import pytest

from instavideosplitter.__main__ import _build_parser
from instavideosplitter.constants import MAX_WORKERS, SEGMENT_DURATION_DEFAULT


@pytest.fixture()
def parser():
    return _build_parser()


def test_defaults(parser):
    args = parser.parse_args(["video.mp4"])
    assert args.video == "video.mp4"
    assert args.duration == SEGMENT_DURATION_DEFAULT
    assert args.offset == 0.0
    assert args.workers == MAX_WORKERS
    assert args.allow_long_last is False
    assert args.verbose is False
    assert args.quiet is False
    assert args.gui is False


def test_all_flags(parser):
    args = parser.parse_args([
        "clip.mp4",
        "-d", "30",
        "-o", "/tmp/out",
        "-f", "-1.5",
        "-w", "2",
        "--allow-long-last",
        "--ffmpeg-dir", "/usr/bin",
        "--verbose",
    ])
    assert args.duration == 30
    assert args.output_dir == "/tmp/out"
    assert args.offset == -1.5
    assert args.workers == 2
    assert args.allow_long_last is True
    assert args.ffmpeg_dir == "/usr/bin"
    assert args.verbose is True


def test_verbose_and_quiet_are_mutually_exclusive(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["video.mp4", "--verbose", "--quiet"])


def test_gui_flag_no_video_required(parser):
    args = parser.parse_args(["--gui"])
    assert args.gui is True
    assert args.video is None


def test_version_exits(parser):
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
