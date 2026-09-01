"""Portable FFmpeg/FFprobe infrastructure adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Sequence

from .domain import MediaInfo, Segment, SplitRequest


class MediaToolNotFound(FileNotFoundError):
    pass


class MediaCommandError(RuntimeError):
    pass


class FFmpegLocator:
    """Resolve executable names across Windows, macOS, and Linux."""

    def __init__(self, directory: Path | str | None = None) -> None:
        self._directory = Path(directory).expanduser().resolve() if directory else None

    @property
    def directory(self) -> Path | None:
        return self._directory

    def configure(self, directory: Path | str) -> None:
        candidate = Path(directory).expanduser().resolve()
        search_directories = (
            candidate,
            candidate / "bin",
            candidate / "ffmpeg" / "bin",
        )
        for executable_directory in search_directories:
            try:
                self._resolve_in_directory("ffmpeg", executable_directory)
                self._resolve_in_directory("ffprobe", executable_directory)
            except MediaToolNotFound:
                continue
            self._directory = executable_directory
            return
        raise MediaToolNotFound(
            "ffmpeg and ffprobe were not found in "
            f"'{candidate}' or a supported bin subdirectory."
        )

    def ffmpeg(self) -> Path:
        if self._directory:
            return self._resolve_in_directory("ffmpeg", self._directory)
        discovered = shutil.which("ffmpeg")
        if discovered:
            return Path(discovered)
        try:
            import imageio_ffmpeg

            return Path(imageio_ffmpeg.get_ffmpeg_exe())
        except (ImportError, RuntimeError) as exc:
            raise MediaToolNotFound(
                "ffmpeg was not found. Install FFmpeg or select its bin directory."
            ) from exc

    def ffprobe(self) -> Path:
        if self._directory:
            return self._resolve_in_directory("ffprobe", self._directory)
        discovered = shutil.which("ffprobe")
        if discovered:
            return Path(discovered)
        ffmpeg_sibling = self.ffmpeg().with_name(
            "ffprobe.exe" if os.name == "nt" else "ffprobe"
        )
        if ffmpeg_sibling.is_file():
            return ffmpeg_sibling
        raise MediaToolNotFound(
            "ffprobe was not found. Install FFmpeg (including ffprobe) or select "
            "its bin directory."
        )

    @staticmethod
    def _resolve_in_directory(name: str, directory: Path) -> Path:
        discovered = shutil.which(name, path=str(directory))
        if discovered:
            return Path(discovered)
        candidates = [directory / name, directory / f"{name}.exe"]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise MediaToolNotFound(f"{name} was not found in '{directory}'.")


default_locator = FFmpegLocator()


def _run_json(command: Sequence[str | os.PathLike[str]]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(value) for value in command],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise MediaCommandError(detail or "ffprobe failed.") from exc
    except json.JSONDecodeError as exc:
        raise MediaCommandError("ffprobe returned invalid JSON.") from exc


class FFprobeMediaProbe:
    def __init__(self, locator: FFmpegLocator = default_locator) -> None:
        self._locator = locator

    def probe(self, video_path: Path) -> MediaInfo:
        path = video_path
        probe = self._locator.ffprobe()
        summary = _run_json(
            [
                probe,
                "-v", "error",
                "-show_entries", "format=duration:stream=codec_type",
                "-of", "json",
                path,
            ]
        )
        frames = _run_json(
            [
                probe,
                "-v", "error",
                "-select_streams", "v:0",
                "-skip_frame", "nokey",
                "-show_frames",
                "-show_entries", "frame=best_effort_timestamp_time,pts_time,pkt_pts_time",
                "-of", "json",
                path,
            ]
        )
        try:
            duration = float(summary["format"]["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MediaCommandError("Could not determine the video duration.") from exc
        has_audio = any(
            stream.get("codec_type") == "audio"
            for stream in summary.get("streams", [])
        )
        keyframes: list[float] = []
        for frame in frames.get("frames", []):
            value = (
                frame.get("best_effort_timestamp_time")
                or frame.get("pts_time")
                or frame.get("pkt_pts_time")
            )
            if value is not None:
                keyframes.append(float(value))
        return MediaInfo(duration, tuple(keyframes), has_audio)


class FFmpegSegmentExporter:
    def __init__(self, locator: FFmpegLocator = default_locator) -> None:
        self._locator = locator

    def export(
        self, request: SplitRequest, segment: Segment, media: MediaInfo
    ) -> None:
        if segment.pad_duration <= 0:
            self._copy_segment(request.video_path, segment, segment.output_path)
            return

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{segment.output_path.stem}-",
            suffix=".mp4",
            dir=segment.output_path.parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            self._copy_segment(request.video_path, segment, temporary_path)
            command = [
                self._locator.ffmpeg(),
                "-hide_banner", "-loglevel", "error", "-y",
                "-i", temporary_path,
                "-vf", f"tpad=stop_mode=add:stop_duration={segment.pad_duration:.6f}",
                "-t", f"{segment.final_duration:.6f}",
                "-c:v", "libx264", "-preset", "medium",
            ]
            if media.has_audio:
                command.extend(
                    [
                        "-af", f"apad=pad_dur={segment.pad_duration:.6f}",
                        "-c:a", "aac", "-b:a", "192k",
                    ]
                )
            else:
                command.append("-an")
            command.append(segment.output_path)
            self._run(command)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _copy_segment(
        self, source: Path, segment: Segment, destination: Path
    ) -> None:
        self._run(
            [
                self._locator.ffmpeg(),
                "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{segment.start:.6f}",
                "-i", source,
                "-t", f"{segment.duration:.6f}",
                "-map", "0:v:0", "-map", "0:a?",
                "-c", "copy",
                destination,
            ]
        )

    @staticmethod
    def _run(command: Sequence[str | os.PathLike[str]]) -> None:
        try:
            subprocess.run(
                [str(value) for value in command],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
            raise MediaCommandError(detail or "ffmpeg failed.") from exc
