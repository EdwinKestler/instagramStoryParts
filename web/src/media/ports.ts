import type { MediaInfo, Segment } from "../core/domain";

export interface MediaLogEntry {
  readonly message: string;
}

export interface LocalMediaAdapter {
  loadSource(file: File): Promise<void>;
  probe(): Promise<MediaInfo>;
  exportSegment(segment: Segment, media: MediaInfo): Promise<Blob>;
  cancel(): void;
  dispose(): Promise<void>;
}

export type MediaLogListener = (entry: MediaLogEntry) => void;
