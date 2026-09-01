"""Dependency-inversion interfaces for infrastructure code."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .domain import MediaInfo, Segment, SplitRequest


class MediaProbe(Protocol):
    def probe(self, video_path: Path) -> MediaInfo:
        """Read duration, audio presence, and keyframes from a media file."""


class SegmentExporter(Protocol):
    def export(
        self, request: SplitRequest, segment: Segment, media: MediaInfo
    ) -> None:
        """Materialize one planned segment or raise an exception."""
