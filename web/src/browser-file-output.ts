import type { SplitArtifact } from "./core/domain";

interface WritableFileStream {
  write(data: Blob): Promise<void>;
  close(): Promise<void>;
}

interface BrowserFileHandle {
  createWritable(): Promise<WritableFileStream>;
}

export interface BrowserDirectoryHandle {
  getFileHandle(name: string, options: { create: boolean }): Promise<BrowserFileHandle>;
}

declare global {
  interface Window {
    showDirectoryPicker?: (options?: {
      id?: string;
      mode?: "read" | "readwrite";
      startIn?: string;
    }) => Promise<BrowserDirectoryHandle>;
  }
}

export async function chooseOutputDirectory(): Promise<BrowserDirectoryHandle> {
  if (!window.showDirectoryPicker) {
    throw new Error("Folder selection is not supported by this browser.");
  }
  return window.showDirectoryPicker({
    id: "story-parts-output",
    mode: "readwrite",
    startIn: "downloads"
  });
}

export async function writeArtifactToDirectory(
  directory: BrowserDirectoryHandle,
  artifact: SplitArtifact
): Promise<void> {
  const handle = await directory.getFileHandle(artifact.segment.outputName, {
    create: true
  });
  const stream = await handle.createWritable();
  await stream.write(artifact.blob);
  await stream.close();
}

export function downloadArtifact(artifact: SplitArtifact): void {
  const url = URL.createObjectURL(artifact.blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = artifact.segment.outputName;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export async function shareArtifact(artifact: SplitArtifact): Promise<boolean> {
  const file = new File([artifact.blob], artifact.segment.outputName, {
    type: "video/mp4"
  });
  if (!navigator.canShare?.({ files: [file] })) return false;
  await navigator.share({ files: [file], title: artifact.segment.outputName });
  return true;
}
