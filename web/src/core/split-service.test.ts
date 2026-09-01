import { describe, expect, it, vi } from "vitest";

import type { MediaInfo, Segment, SplitRequest } from "./domain";
import { LocalVideoSplitService } from "./split-service";
import type { LocalMediaAdapter } from "../media/ports";

class FakeMediaAdapter implements LocalMediaAdapter {
  readonly info: MediaInfo = {
    duration: 125,
    keyframes: [0, 60, 120],
    hasAudio: true
  };
  loadedFile: File | undefined;
  readonly exported: Segment[] = [];
  cancelled = false;
  disposed = false;

  async loadSource(file: File): Promise<void> {
    this.loadedFile = file;
  }

  async probe(): Promise<MediaInfo> {
    return this.info;
  }

  async exportSegment(segment: Segment): Promise<Blob> {
    this.exported.push(segment);
    return new Blob([`part-${segment.index}`], { type: "video/mp4" });
  }

  cancel(): void {
    this.cancelled = true;
  }

  async dispose(): Promise<void> {
    this.disposed = true;
  }
}

const request: SplitRequest = {
  fileName: "source.mp4",
  segmentDuration: 60,
  offset: 0,
  allowLongLastPart: false
};

describe("LocalVideoSplitService", () => {
  it("runs injected media dependencies and reaches completed", async () => {
    const media = new FakeMediaAdapter();
    const service = new LocalVideoSplitService(media);
    const states: string[] = [];
    const progress = vi.fn();
    const file = new File(["video"], "source.mp4", { type: "video/mp4" });

    const artifacts = await service.split(file, request, {
      onStateChange: ({ current }) => states.push(current),
      onProgress: progress
    });

    expect(media.loadedFile).toBe(file);
    expect(media.exported).toHaveLength(3);
    expect(media.disposed).toBe(true);
    expect(artifacts).toHaveLength(3);
    expect(progress).toHaveBeenCalledTimes(3);
    expect(states).toEqual([
      "validating",
      "loading",
      "probing",
      "planning",
      "exporting",
      "completed"
    ]);
    expect(service.stateMachine?.state).toBe("completed");
  });

  it("models validation failures and still disposes resources", async () => {
    const media = new FakeMediaAdapter();
    const service = new LocalVideoSplitService(media);
    const empty = new File([], "empty.mp4", { type: "video/mp4" });

    await expect(service.split(empty, request)).rejects.toThrow("empty");

    expect(service.stateMachine?.state).toBe("failed");
    expect(media.loadedFile).toBeUndefined();
    expect(media.disposed).toBe(true);
  });
});
