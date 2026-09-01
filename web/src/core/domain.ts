export interface SplitRequest {
  readonly fileName: string;
  readonly segmentDuration: number;
  readonly offset: number;
  readonly allowLongLastPart: boolean;
}

export interface MediaInfo {
  readonly duration: number;
  readonly keyframes: readonly number[];
  readonly hasAudio: boolean;
}

export interface Segment {
  readonly index: number;
  readonly start: number;
  readonly end: number;
  readonly padDuration: number;
  readonly outputName: string;
}

export interface SplitArtifact {
  readonly segment: Segment;
  readonly blob: Blob;
}

export function segmentDuration(segment: Segment): number {
  return segment.end - segment.start;
}

export function finalSegmentDuration(segment: Segment): number {
  return segmentDuration(segment) + segment.padDuration;
}
