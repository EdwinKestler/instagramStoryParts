import "./styles.css";

import type { SplitArtifact, SplitRequest } from "./core/domain";
import { LocalVideoSplitService } from "./core/split-service";
import type { SplitState } from "./core/fsm";
import {
  chooseOutputDirectory,
  downloadArtifact,
  shareArtifact,
  writeArtifactToDirectory,
  type BrowserDirectoryHandle
} from "./browser-file-output";
import { FFmpegWasmAdapter } from "./media/ffmpeg-adapter";

const elements = {
  input: required<HTMLInputElement>("video-input"),
  dropZone: required<HTMLElement>("drop-zone"),
  browse: required<HTMLButtonElement>("browse-button"),
  replace: required<HTMLButtonElement>("replace-button"),
  fileCard: required<HTMLElement>("file-card"),
  preview: required<HTMLVideoElement>("video-preview"),
  fileName: required<HTMLElement>("file-name"),
  fileDetails: required<HTMLElement>("file-details"),
  form: required<HTMLFormElement>("split-form"),
  offset: required<HTMLInputElement>("offset-input"),
  offsetValue: required<HTMLOutputElement>("offset-value"),
  allowLong: required<HTMLInputElement>("allow-long-input"),
  folder: required<HTMLButtonElement>("folder-button"),
  destination: required<HTMLElement>("destination-label"),
  process: required<HTMLButtonElement>("process-button"),
  cancel: required<HTMLButtonElement>("cancel-button"),
  progressPanel: required<HTMLElement>("progress-panel"),
  stateLabel: required<HTMLElement>("state-label"),
  status: required<HTMLElement>("status-text"),
  percent: required<HTMLElement>("progress-percent"),
  progress: required<HTMLProgressElement>("progress-bar"),
  resultsPanel: required<HTMLElement>("results-panel"),
  resultsSummary: required<HTMLElement>("results-summary"),
  resultsList: required<HTMLElement>("results-list"),
  log: required<HTMLElement>("log-output")
};

const recentLogs: string[] = [];
const mediaAdapter = new FFmpegWasmAdapter(({ message }) => appendLog(message));
const service = new LocalVideoSplitService(mediaAdapter);
let selectedFile: File | undefined;
let selectedDirectory: BrowserDirectoryHandle | undefined;
let previewUrl: string | undefined;
let processing = false;

elements.browse.addEventListener("click", () => elements.input.click());
elements.replace.addEventListener("click", () => elements.input.click());
elements.dropZone.addEventListener("click", (event) => {
  if ((event.target as HTMLElement).closest("button")) return;
  elements.input.click();
});
elements.dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    elements.input.click();
  }
});
elements.input.addEventListener("change", () => {
  const file = elements.input.files?.[0];
  if (file) selectFile(file);
});
for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("is-dragging");
  });
}
elements.dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files[0];
  if (file) selectFile(file);
});

elements.offset.addEventListener("input", () => {
  const value = Number(elements.offset.value);
  elements.offsetValue.value = `${value >= 0 ? "+" : ""}${value.toFixed(1)}s`;
});

if (!window.showDirectoryPicker) {
  elements.folder.textContent = "Downloads only";
  elements.folder.disabled = true;
}
elements.folder.addEventListener("click", async () => {
  try {
    selectedDirectory = await chooseOutputDirectory();
    const directoryName = "name" in selectedDirectory
      ? String(selectedDirectory.name)
      : "selected folder";
    elements.destination.textContent = `Save directly to ${directoryName}`;
    elements.folder.textContent = "Change folder";
  } catch (error) {
    if (isAbortError(error)) return;
    showError(error);
  }
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile || processing) return;
  await processFile(selectedFile);
});

elements.cancel.addEventListener("click", () => {
  if (!processing) return;
  elements.status.textContent = "Cancelling local processing…";
  service.cancel();
});

window.addEventListener("beforeunload", (event) => {
  if (!processing) return;
  event.preventDefault();
});

function selectFile(file: File): void {
  if (!file.type.startsWith("video/") && !/\.(mkv|avi|mov|mp4|webm)$/i.test(file.name)) {
    showError(new Error("Please choose a supported video file."));
    return;
  }
  selectedFile = file;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  elements.preview.src = previewUrl;
  elements.fileName.textContent = file.name;
  elements.fileDetails.textContent = `${formatBytes(file.size)} · stays on this device`;
  elements.fileCard.hidden = false;
  elements.dropZone.hidden = true;
  elements.process.disabled = false;
  elements.resultsPanel.hidden = true;
  elements.resultsList.replaceChildren();
  appendLog(`Selected ${file.name} (${formatBytes(file.size)}).`);
}

async function processFile(file: File): Promise<void> {
  processing = true;
  elements.process.disabled = true;
  elements.cancel.hidden = false;
  elements.progressPanel.hidden = false;
  elements.resultsPanel.hidden = true;
  elements.resultsList.replaceChildren();
  updateProgress(0);

  const durationInput = document.querySelector<HTMLInputElement>(
    'input[name="duration"]:checked'
  );
  const request: SplitRequest = {
    fileName: file.name,
    segmentDuration: Number(durationInput?.value ?? 60),
    offset: Number(elements.offset.value),
    allowLongLastPart: elements.allowLong.checked
  };

  try {
    const artifacts = await service.split(file, request, {
      onStateChange: ({ current }) => updateState(current),
      onProgress: ({ completed, total }) => {
        updateProgress(Math.round((completed / total) * 100));
        elements.status.textContent = `Finished part ${completed} of ${total}`;
      },
      onArtifact: async (artifact) => {
        if (selectedDirectory) {
          await writeArtifactToDirectory(selectedDirectory, artifact);
        }
        renderArtifact(artifact, Boolean(selectedDirectory));
      }
    });
    elements.resultsSummary.textContent = `${artifacts.length} MP4 file${artifacts.length === 1 ? "" : "s"}`;
    elements.resultsPanel.hidden = false;
    updateProgress(100);
    elements.status.textContent = selectedDirectory
      ? "All parts were saved to your selected folder."
      : "Choose Download or Share for each finished part.";
  } catch (error) {
    if (service.stateMachine?.state === "cancelled") {
      elements.status.textContent = "Processing cancelled. No cloud copy was created.";
      appendLog("Processing cancelled by the user.");
    } else {
      showError(error);
    }
  } finally {
    processing = false;
    elements.process.disabled = !selectedFile;
    elements.cancel.hidden = true;
  }
}

function renderArtifact(artifact: SplitArtifact, saved: boolean): void {
  const row = document.createElement("article");
  row.className = "result-row";

  const information = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = artifact.segment.outputName;
  const detail = document.createElement("span");
  detail.className = "muted";
  detail.textContent = `${formatBytes(artifact.blob.size)} · ${saved ? "saved locally" : "ready locally"}`;
  information.append(title, detail);

  const actions = document.createElement("div");
  actions.className = "result-actions";
  const download = document.createElement("button");
  download.className = "button tertiary small";
  download.type = "button";
  download.textContent = saved ? "Download again" : "Download";
  download.addEventListener("click", () => downloadArtifact(artifact));
  actions.append(download);

  if (typeof navigator.canShare === "function") {
    const share = document.createElement("button");
    share.className = "button secondary small";
    share.type = "button";
    share.textContent = "Share / Save";
    share.addEventListener("click", async () => {
      try {
        const shared = await shareArtifact(artifact);
        if (!shared) downloadArtifact(artifact);
      } catch (error) {
        if (!isAbortError(error)) showError(error);
      }
    });
    actions.append(share);
  }

  row.append(information, actions);
  elements.resultsList.append(row);
}

function updateState(state: SplitState): void {
  const labels: Record<SplitState, [string, string]> = {
    created: ["READY", "Preparing a private processing job…"],
    validating: ["CHECKING", "Validating the selected video…"],
    loading: ["LOADING ENGINE", "Loading FFmpeg and copying the video into browser memory…"],
    probing: ["ANALYZING", "Reading duration, audio tracks, and keyframes…"],
    planning: ["PLANNING", "Calculating continuous segment boundaries…"],
    exporting: ["PROCESSING", "Creating local MP4 parts…"],
    completed: ["COMPLETE", "All parts were created locally."],
    failed: ["ERROR", "The video could not be processed."],
    cancelled: ["CANCELLED", "Local processing was cancelled."]
  };
  const [label, message] = labels[state];
  elements.stateLabel.textContent = label;
  elements.status.textContent = message;
  appendLog(`State: ${state}`);
}

function updateProgress(percent: number): void {
  const safePercent = Math.min(Math.max(percent, 0), 100);
  elements.progress.value = safePercent;
  elements.progress.textContent = `${safePercent}%`;
  elements.percent.textContent = `${safePercent}%`;
}

function appendLog(message: string): void {
  recentLogs.push(message);
  if (recentLogs.length > 30) recentLogs.shift();
  elements.log.textContent = recentLogs.join("\n");
}

function showError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  elements.progressPanel.hidden = false;
  elements.stateLabel.textContent = "ERROR";
  elements.status.textContent = message;
  appendLog(`Error: ${message}`);
}

function required<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing required element #${id}.`);
  return element as T;
}

function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  if (bytes < 1_000_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${(bytes / 1_000_000_000).toFixed(2)} GB`;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
