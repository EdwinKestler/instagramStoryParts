"""Application service that orchestrates the split state machine."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .domain import Segment, SplitRequest, SplitResult
from .fsm import SplitState, SplitStateMachine, TransitionListener
from .planner import LongLastPartPolicy, SegmentPlanner
from .ports import MediaProbe, SegmentExporter


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    completed: int
    total: int
    segment: Segment
    skipped: bool = False


ProgressListener = Callable[[ProgressUpdate], None]


class VideoSplitService:
    """One-shot coordinator with infrastructure injected through protocols."""

    def __init__(
        self,
        probe: MediaProbe,
        exporter: SegmentExporter,
        planner: SegmentPlanner | None = None,
        state_listener: TransitionListener | None = None,
    ) -> None:
        self.probe = probe
        self.exporter = exporter
        self.planner = planner or SegmentPlanner()
        self.state_machine = SplitStateMachine(state_listener)

    def split(
        self,
        request: SplitRequest,
        progress_listener: ProgressListener | None = None,
        allow_long_last_part: LongLastPartPolicy | None = None,
    ) -> SplitResult:
        try:
            self.state_machine.transition_to(SplitState.VALIDATING)
            self._validate(request)
            request.resolved_output_dir.mkdir(parents=True, exist_ok=True)

            self.state_machine.transition_to(SplitState.PROBING)
            media = self.probe.probe(request.video_path)

            self.state_machine.transition_to(SplitState.PLANNING)
            segments = self.planner.plan(request, media, allow_long_last_part)

            self.state_machine.transition_to(SplitState.EXPORTING)
            exported: list[Path] = []
            skipped: list[Path] = []
            pending: list[Segment] = []
            completed = 0
            total = len(segments)

            for segment in segments:
                if segment.output_path.exists() and not request.overwrite:
                    skipped.append(segment.output_path)
                    completed += 1
                    if progress_listener:
                        progress_listener(
                            ProgressUpdate(completed, total, segment, skipped=True)
                        )
                else:
                    pending.append(segment)

            with ThreadPoolExecutor(max_workers=request.max_workers) as executor:
                futures = {
                    executor.submit(self.exporter.export, request, segment, media): segment
                    for segment in pending
                }
                for future in as_completed(futures):
                    segment = futures[future]
                    future.result()
                    exported.append(segment.output_path)
                    completed += 1
                    if progress_listener:
                        progress_listener(ProgressUpdate(completed, total, segment))

            self.state_machine.transition_to(SplitState.COMPLETED)
            return SplitResult(
                tuple(sorted(exported)),
                tuple(sorted(skipped)),
            )
        except Exception:
            self.state_machine.fail()
            raise

    @staticmethod
    def _validate(request: SplitRequest) -> None:
        if not request.video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {request.video_path}")
        if request.segment_duration <= 0:
            raise ValueError("Segment duration must be greater than zero.")
        if request.max_workers <= 0:
            raise ValueError("max_workers must be greater than zero.")
