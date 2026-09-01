import type { MediaInfo, SplitArtifact, SplitRequest } from "./domain";
import { SplitStateMachine, type StateTransition } from "./fsm";
import { SegmentPlanner } from "./planner";
import type { LocalMediaAdapter } from "../media/ports";

export interface SplitProgress {
  readonly completed: number;
  readonly total: number;
  readonly currentPart: number;
}

export interface SplitCallbacks {
  readonly onStateChange?: (transition: StateTransition) => void;
  readonly onProgress?: (progress: SplitProgress) => void;
  readonly onArtifact?: (artifact: SplitArtifact) => Promise<void> | void;
}

export class LocalVideoSplitService {
  static readonly MAX_FILE_BYTES = 2_000_000_000;

  #machine: SplitStateMachine | undefined;
  #cancelRequested = false;

  constructor(
    private readonly media: LocalMediaAdapter,
    private readonly planner = new SegmentPlanner()
  ) {}

  get stateMachine(): SplitStateMachine | undefined {
    return this.#machine;
  }

  async split(
    file: File,
    request: SplitRequest,
    callbacks: SplitCallbacks = {}
  ): Promise<readonly SplitArtifact[]> {
    this.#cancelRequested = false;
    this.#machine = new SplitStateMachine(callbacks.onStateChange);
    const machine = this.#machine;
    try {
      machine.transitionTo("validating");
      this.validate(file, request);

      machine.transitionTo("loading");
      await this.media.loadSource(file);
      this.throwIfCancelled();

      machine.transitionTo("probing");
      const mediaInfo = await this.media.probe();
      this.throwIfCancelled();

      machine.transitionTo("planning");
      const segments = this.planner.plan(request, mediaInfo);

      machine.transitionTo("exporting");
      const artifacts: SplitArtifact[] = [];
      for (const segment of segments) {
        this.throwIfCancelled();
        const blob = await this.media.exportSegment(segment, mediaInfo);
        const artifact = { segment, blob } satisfies SplitArtifact;
        artifacts.push(artifact);
        await callbacks.onArtifact?.(artifact);
        callbacks.onProgress?.({
          completed: artifacts.length,
          total: segments.length,
          currentPart: segment.index
        });
      }

      machine.transitionTo("completed");
      return artifacts;
    } catch (error) {
      if (this.#cancelRequested) machine.cancel();
      else machine.fail();
      throw error;
    } finally {
      await this.media.dispose();
    }
  }

  cancel(): void {
    this.#cancelRequested = true;
    this.media.cancel();
  }

  private validate(file: File, request: SplitRequest): void {
    if (file.size <= 0) throw new Error("The selected video is empty.");
    if (file.size > LocalVideoSplitService.MAX_FILE_BYTES) {
      throw new Error("Browser processing currently supports videos smaller than 2 GB.");
    }
    if (!Number.isFinite(request.segmentDuration) || request.segmentDuration <= 0) {
      throw new Error("Segment duration must be greater than zero.");
    }
    if (!Number.isFinite(request.offset) || Math.abs(request.offset) > 5) {
      throw new Error("Offset must be between -5 and +5 seconds.");
    }
  }

  private throwIfCancelled(): void {
    if (this.#cancelRequested) throw new Error("Video processing was cancelled.");
  }
}

export function describeMedia(media: MediaInfo): string {
  const audio = media.hasAudio ? "audio detected" : "no audio";
  return `${formatDuration(media.duration)}, ${media.keyframes.length} keyframes, ${audio}`;
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}
