"""Pure, deterministic segment planning."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .domain import MediaInfo, Segment, SplitRequest


LongLastPartPolicy = Callable[[float], bool]


class SegmentPlanner:
    """Create a gap-free plan, using keyframes for internal boundaries."""

    _EPSILON = 1e-6

    @staticmethod
    def nearest_keyframe(timestamp: float, keyframes: Iterable[float]) -> float:
        candidates = tuple(keyframes)
        if not candidates:
            return timestamp
        return min(candidates, key=lambda value: abs(value - timestamp))

    def plan(
        self,
        request: SplitRequest,
        media: MediaInfo,
        allow_long_last_part: LongLastPartPolicy | None = None,
    ) -> tuple[Segment, ...]:
        target = request.segment_duration
        if target <= 0:
            raise ValueError("Segment duration must be greater than zero.")
        if media.duration <= 0:
            raise ValueError("Video duration must be greater than zero.")

        boundaries = [0.0]
        nominal = target
        while nominal < media.duration:
            boundary = self.nearest_keyframe(nominal, media.keyframes)
            boundary = min(max(boundary + request.offset, 0.0), media.duration)

            # A repeated/extreme keyframe must not collapse two planned parts.
            if boundary <= boundaries[-1] + self._EPSILON:
                boundary = min(max(nominal + request.offset, 0.0), media.duration)
            if boundary > boundaries[-1] + self._EPSILON and boundary < media.duration:
                boundaries.append(boundary)
            nominal += target
        boundaries.append(media.duration)

        spans = list(zip(boundaries, boundaries[1:]))
        last_start, last_end = spans[-1]
        last_length = last_end - last_start
        if target < last_length <= target * 1.1:
            keep_long = bool(
                allow_long_last_part and allow_long_last_part(last_length)
            )
            if not keep_long:
                spans[-1:] = [(last_start, last_start + target),
                              (last_start + target, last_end)]

        segments: list[Segment] = []
        output_dir = request.resolved_output_dir
        for index, (start, end) in enumerate(spans, start=1):
            pad_duration = 0.0
            if index == len(spans) and end - start < target:
                pad_duration = target - (end - start)
            segments.append(
                Segment(
                    index=index,
                    start=start,
                    end=end,
                    output_path=output_dir
                    / f"{request.video_path.stem}-part{index}.mp4",
                    pad_duration=pad_duration,
                )
            )
        return tuple(segments)
