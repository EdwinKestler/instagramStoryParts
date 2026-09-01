import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile } from "@ffmpeg/util";

import {
  finalSegmentDuration,
  segmentDuration,
  type MediaInfo,
  type Segment
} from "../core/domain";
import type { LocalMediaAdapter, MediaLogListener } from "./ports";

const CORE_VERSION = "0.12.10";
const CORE_BASE_URL = `/vendor/ffmpeg/${CORE_VERSION}`;

interface ProbeSummary {
  readonly format?: { readonly duration?: string };
  readonly streams?: ReadonlyArray<{ readonly codec_type?: string }>;
}

interface KeyframeSummary {
  readonly frames?: ReadonlyArray<{
    readonly best_effort_timestamp_time?: string;
    readonly pts_time?: string;
    readonly pkt_pts_time?: string;
  }>;
}

export class FFmpegWasmAdapter implements LocalMediaAdapter {
  #ffmpeg = this.createFFmpeg();
  #loaded = false;
  #sourceName: string | undefined;

  constructor(private readonly logListener?: MediaLogListener) {}

  async loadSource(file: File): Promise<void> {
    if (!this.#loaded) {
      await this.#ffmpeg.load({
        coreURL: `${CORE_BASE_URL}/ffmpeg-core.js`,
        wasmURL: `${CORE_BASE_URL}/ffmpeg-core.wasm`
      });
      this.#loaded = true;
    }

    this.#sourceName = `source-${crypto.randomUUID()}${safeExtension(file.name)}`;
    await this.#ffmpeg.writeFile(this.#sourceName, await fetchFile(file));
  }

  async probe(): Promise<MediaInfo> {
    const sourceName = this.requireSource();
    const metadataName = `metadata-${crypto.randomUUID()}.json`;
    const keyframesName = `keyframes-${crypto.randomUUID()}.json`;
    try {
      const metadataExitCode = await this.#ffmpeg.ffprobe([
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type",
        "-of",
        "json",
        sourceName,
        "-o",
        metadataName
      ]);
      if (metadataExitCode !== 0) {
        this.logListener?.({
          message: `FFprobe metadata command returned ${metadataExitCode}; checking its output.`
        });
      }

      const keyframeExitCode = await this.#ffmpeg.ffprobe([
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-skip_frame",
        "nokey",
        "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,pts_time,pkt_pts_time",
        "-of",
        "json",
        sourceName,
        "-o",
        keyframesName
      ]);
      if (keyframeExitCode !== 0) {
        this.logListener?.({
          message: `FFprobe keyframe command returned ${keyframeExitCode}; checking its output.`
        });
      }

      const metadata = await this.readJson<ProbeSummary>(
        metadataName,
        `Unable to read video metadata (FFprobe exit ${metadataExitCode}).`
      );
      const keyframeData = await this.readJson<KeyframeSummary>(
        keyframesName,
        `Unable to read video keyframes (FFprobe exit ${keyframeExitCode}).`
      );
      const duration = Number(metadata.format?.duration);
      if (!Number.isFinite(duration) || duration <= 0) {
        throw new Error("The selected file does not contain a valid video duration.");
      }
      const keyframes = (keyframeData.frames ?? [])
        .map((frame) =>
          Number(
            frame.best_effort_timestamp_time ?? frame.pts_time ?? frame.pkt_pts_time
          )
        )
        .filter((value) => Number.isFinite(value));
      return {
        duration,
        keyframes,
        hasAudio: (metadata.streams ?? []).some(
          (stream) => stream.codec_type === "audio"
        )
      };
    } finally {
      await this.deleteIfPresent(metadataName);
      await this.deleteIfPresent(keyframesName);
    }
  }

  async exportSegment(segment: Segment, media: MediaInfo): Promise<Blob> {
    const sourceName = this.requireSource();
    const outputName = `output-${segment.index}-${crypto.randomUUID()}.mp4`;
    try {
      const command = segment.padDuration > 0
        ? this.paddedCommand(sourceName, outputName, segment, media.hasAudio)
        : this.copyCommand(sourceName, outputName, segment);
      const exitCode = await this.#ffmpeg.exec(command);
      if (exitCode !== 0) {
        throw new Error(`FFmpeg failed while producing part ${segment.index}.`);
      }
      const data = await this.#ffmpeg.readFile(outputName);
      if (!(data instanceof Uint8Array)) {
        throw new Error(`Part ${segment.index} did not produce binary video data.`);
      }
      const bytes = data.slice().buffer as ArrayBuffer;
      return new Blob([bytes], { type: "video/mp4" });
    } finally {
      await this.deleteIfPresent(outputName);
    }
  }

  cancel(): void {
    if (this.#loaded) this.#ffmpeg.terminate();
    this.#ffmpeg = this.createFFmpeg();
    this.#loaded = false;
    this.#sourceName = undefined;
  }

  async dispose(): Promise<void> {
    if (this.#sourceName && this.#loaded) {
      await this.deleteIfPresent(this.#sourceName);
    }
    this.#sourceName = undefined;
  }

  private copyCommand(
    sourceName: string,
    outputName: string,
    segment: Segment
  ): string[] {
    return [
      "-hide_banner",
      "-loglevel",
      "error",
      "-ss",
      segment.start.toFixed(6),
      "-i",
      sourceName,
      "-t",
      segmentDuration(segment).toFixed(6),
      "-map",
      "0:v:0",
      "-map",
      "0:a?",
      "-c",
      "copy",
      "-movflags",
      "+faststart",
      outputName
    ];
  }

  private paddedCommand(
    sourceName: string,
    outputName: string,
    segment: Segment,
    hasAudio: boolean
  ): string[] {
    const command = [
      "-hide_banner",
      "-loglevel",
      "error",
      "-ss",
      segment.start.toFixed(6),
      "-i",
      sourceName,
      "-t",
      finalSegmentDuration(segment).toFixed(6),
      "-vf",
      `tpad=stop_mode=add:stop_duration=${segment.padDuration.toFixed(6)}`,
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-threads",
      "1"
    ];
    if (hasAudio) {
      command.push(
        "-af",
        `apad=pad_dur=${segment.padDuration.toFixed(6)}`,
        "-c:a",
        "aac",
        "-b:a",
        "192k"
      );
    } else {
      command.push("-an");
    }
    command.push("-movflags", "+faststart", outputName);
    return command;
  }

  private createFFmpeg(): FFmpeg {
    const ffmpeg = new FFmpeg();
    ffmpeg.on("log", ({ message }) => this.logListener?.({ message }));
    return ffmpeg;
  }

  private requireSource(): string {
    if (!this.#sourceName) throw new Error("No source video is loaded.");
    return this.#sourceName;
  }

  private async readText(name: string): Promise<string> {
    const value = await this.#ffmpeg.readFile(name, "utf8");
    return typeof value === "string" ? value : new TextDecoder().decode(value);
  }

  private async readJson<T>(name: string, errorMessage: string): Promise<T> {
    try {
      return JSON.parse(await this.readText(name)) as T;
    } catch {
      throw new Error(errorMessage);
    }
  }

  private async deleteIfPresent(name: string): Promise<void> {
    try {
      await this.#ffmpeg.deleteFile(name);
    } catch {
      // Cleanup is intentionally idempotent.
    }
  }
}

function safeExtension(fileName: string): string {
  const match = /\.[a-zA-Z0-9]{1,8}$/.exec(fileName);
  return match?.[0].toLowerCase() ?? ".mp4";
}
