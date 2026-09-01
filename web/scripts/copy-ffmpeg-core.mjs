import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const sourceRoot = resolve(webRoot, "node_modules/@ffmpeg/core/dist/esm");
const targetRoot = resolve(webRoot, "public/vendor/ffmpeg/0.12.10");

await mkdir(targetRoot, { recursive: true });
await Promise.all([
  copyFile(resolve(sourceRoot, "ffmpeg-core.js"), resolve(targetRoot, "ffmpeg-core.js")),
  copyFile(resolve(sourceRoot, "ffmpeg-core.wasm"), resolve(targetRoot, "ffmpeg-core.wasm"))
]);

console.log("Prepared self-hosted FFmpeg core assets.");
