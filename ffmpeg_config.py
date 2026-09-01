"""Backward-compatible access to the shared FFmpeg locator."""

from pathlib import Path

from instagram_story_parts.media import default_locator


def set_ffmpeg_dir(path: str) -> None:
    if path:
        default_locator.configure(Path(path))


def set_ffmpeg_path(path: str) -> None:
    candidate = Path(path)
    set_ffmpeg_dir(str(candidate if candidate.is_dir() else candidate.parent))


def get_ffmpeg_dir() -> str:
    directory = default_locator.directory
    return str(directory if directory is not None else default_locator.ffmpeg().parent)


def get_ffmpeg_path() -> str:
    return str(default_locator.ffmpeg())
