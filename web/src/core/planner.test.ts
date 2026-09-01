import { describe, expect, it } from "vitest";

import type { MediaInfo, SplitRequest } from "./domain";
import { finalSegmentDuration } from "./domain";
import { SegmentPlanner } from "./planner";

const baseRequest: SplitRequest = {
  fileName: "Angel_a.mp4",
  segmentDuration: 60,
  offset: 0,
  allowLongLastPart: false
};

describe("SegmentPlanner", () => {
  it("creates continuous parts and pads only a short final part", () => {
    const media: MediaInfo = {
      duration: 125,
      keyframes: [0, 59.5, 120.2],
      hasAudio: true
    };

    const segments = new SegmentPlanner().plan(baseRequest, media);

    expect(segments).toHaveLength(3);
    expect(segments[0]?.start).toBe(0);
    expect(segments[0]?.end).toBe(59.5);
    expect(segments[1]?.start).toBe(59.5);
    expect(segments[1]?.end).toBe(120.2);
    expect(segments[2]?.start).toBe(120.2);
    expect(segments[2]?.end).toBe(125);
    expect(finalSegmentDuration(segments[2]!)).toBeCloseTo(60);
    expect(segments.map(({ outputName }) => outputName)).toEqual([
      "Angel_a-part1.mp4",
      "Angel_a-part2.mp4",
      "Angel_a-part3.mp4"
    ]);
  });

  it("does not discard the start when a positive offset is used", () => {
    const media: MediaInfo = {
      duration: 180,
      keyframes: [0, 60, 120],
      hasAudio: false
    };

    const segments = new SegmentPlanner().plan(
      { ...baseRequest, offset: 1.5 },
      media
    );

    expect(segments[0]?.start).toBe(0);
    expect(segments.at(-1)?.end).toBe(180);
    for (let index = 1; index < segments.length; index += 1) {
      expect(segments[index]?.start).toBe(segments[index - 1]?.end);
    }
  });

  it("can split or retain a slightly long final part by policy", () => {
    const media: MediaInfo = {
      duration: 124,
      keyframes: [0, 60, 124],
      hasAudio: true
    };
    const planner = new SegmentPlanner();

    expect(planner.plan(baseRequest, media)).toHaveLength(3);
    expect(
      planner.plan({ ...baseRequest, allowLongLastPart: true }, media)
    ).toHaveLength(2);
  });

  it("rejects invalid durations", () => {
    expect(() =>
      new SegmentPlanner().plan(
        { ...baseRequest, segmentDuration: 0 },
        { duration: 10, keyframes: [], hasAudio: false }
      )
    ).toThrow("greater than zero");
  });
});
