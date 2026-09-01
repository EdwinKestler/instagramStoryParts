import type { MediaInfo, Segment, SplitRequest } from "./domain";

export class SegmentPlanner {
  static readonly EPSILON = 1e-6;

  static nearestKeyframe(timestamp: number, keyframes: readonly number[]): number {
    if (keyframes.length === 0) return timestamp;
    return keyframes.reduce((closest, candidate) =>
      Math.abs(candidate - timestamp) < Math.abs(closest - timestamp)
        ? candidate
        : closest
    );
  }

  plan(request: SplitRequest, media: MediaInfo): readonly Segment[] {
    const target = request.segmentDuration;
    if (!Number.isFinite(target) || target <= 0) {
      throw new Error("Segment duration must be greater than zero.");
    }
    if (!Number.isFinite(media.duration) || media.duration <= 0) {
      throw new Error("Video duration must be greater than zero.");
    }

    const boundaries = [0];
    for (let nominal = target; nominal < media.duration; nominal += target) {
      let boundary = SegmentPlanner.nearestKeyframe(nominal, media.keyframes);
      boundary = clamp(boundary + request.offset, 0, media.duration);
      const previous = boundaries.at(-1) ?? 0;
      if (boundary <= previous + SegmentPlanner.EPSILON) {
        boundary = clamp(nominal + request.offset, 0, media.duration);
      }
      if (
        boundary > previous + SegmentPlanner.EPSILON &&
        boundary < media.duration
      ) {
        boundaries.push(boundary);
      }
    }
    boundaries.push(media.duration);

    const spans: Array<[number, number]> = boundaries.slice(0, -1).map((start, index) => [
      start,
      boundaries[index + 1] ?? media.duration
    ]);
    const finalSpan = spans.at(-1);
    if (finalSpan) {
      const [start, end] = finalSpan;
      const length = end - start;
      if (
        length > target &&
        length <= target * 1.1 &&
        !request.allowLongLastPart
      ) {
        spans.splice(spans.length - 1, 1, [start, start + target], [start + target, end]);
      }
    }

    const stem = safeStem(request.fileName);
    return spans.map(([start, end], zeroBasedIndex) => {
      const index = zeroBasedIndex + 1;
      const isFinal = index === spans.length;
      const duration = end - start;
      return {
        index,
        start,
        end,
        padDuration: isFinal && duration < target ? target - duration : 0,
        outputName: `${stem}-part${index}.mp4`
      };
    });
  }
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function safeStem(fileName: string): string {
  const withoutExtension = fileName.replace(/\.[^/.]+$/, "");
  const sanitized = withoutExtension
    .normalize("NFKD")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return sanitized || "video";
}
