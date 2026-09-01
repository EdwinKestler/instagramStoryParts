"""Domain models shared by the CLI, GUI, and media adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SplitRequest:
    """User-supplied settings for one split operation."""

    video_path: Path
    output_dir: Path | None = None
    segment_duration: float = 60.0
    offset: float = 0.0
    overwrite: bool = False
    max_workers: int = 4

    @property
    def resolved_output_dir(self) -> Path:
        return self.output_dir or self.video_path.parent


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Media facts required by the pure segment planner."""

    duration: float
    keyframes: tuple[float, ...] = ()
    has_audio: bool = False


@dataclass(frozen=True, slots=True)
class Segment:
    """A planned, continuous portion of the source video."""

    index: int
    start: float
    end: float
    output_path: Path
    pad_duration: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def final_duration(self) -> float:
        return self.duration + self.pad_duration


@dataclass(frozen=True, slots=True)
class SplitResult:
    """Summary returned after a split job reaches a terminal state."""

    exported: tuple[Path, ...]
    skipped: tuple[Path, ...]

    @property
    def completed_count(self) -> int:
        return len(self.exported) + len(self.skipped)
