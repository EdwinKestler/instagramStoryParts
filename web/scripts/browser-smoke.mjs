import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { once } from "node:events";

const sourcePath = resolve(process.argv[2] ?? "../input/Angel_a.mp4");
const applicationUrl = process.argv[3] ?? "https://instagram-story-parts.vercel.app";
const browserPath = findBrowser();

if (!existsSync(sourcePath)) throw new Error(`Video fixture not found: ${sourcePath}`);
if (!browserPath) throw new Error("Chrome or Edge is required for the browser smoke test.");

const profilePath = await mkdtemp(join(tmpdir(), "story-parts-browser-"));
const debuggingPort = 20_000 + Math.floor(Math.random() * 20_000);
const browser = spawn(
  browserPath,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${debuggingPort}`,
    `--user-data-dir=${profilePath}`,
    "about:blank"
  ],
  { stdio: "ignore" }
);

try {
  const target = await waitForTarget(debuggingPort);
  const cdp = connect(target.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("DOM.enable");
  await cdp.send("Page.navigate", { url: applicationUrl });
  await waitFor(async () =>
    Boolean(await evaluate(cdp, "document.readyState === 'complete'"))
  );

  const isolated = await evaluate(cdp, "globalThis.crossOriginIsolated");
  if (!isolated) throw new Error("Production page is not cross-origin isolated.");

  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const { nodeId } = await cdp.send("DOM.querySelector", {
    nodeId: root.nodeId,
    selector: "#video-input"
  });
  if (!nodeId) throw new Error("The video input was not rendered.");
  await cdp.send("DOM.setFileInputFiles", { nodeId, files: [sourcePath] });
  await waitFor(async () =>
    (await evaluate(cdp, "document.querySelector('#video-input').files.length")) === 1
  );
  await waitFor(async () =>
    Boolean(await evaluate(cdp, "!document.querySelector('#process-button').disabled"))
  );

  await evaluate(
    cdp,
    "document.querySelector(\"input[name='duration'][value='60']\").checked = true; " +
      "document.querySelector('#process-button').click(); true"
  );
  const terminalState = await waitForTerminalState(cdp, 10 * 60_000);
  if (terminalState !== "COMPLETE") {
    const message = await evaluate(cdp, "document.querySelector('#status-text').textContent");
    const log = await evaluate(cdp, "document.querySelector('#log-output').textContent");
    throw new Error(`Browser processing ended in ${terminalState}: ${message}\n${log}`);
  }

  const resultCount = await evaluate(
    cdp,
    "document.querySelectorAll('#results-list .result-row').length"
  );
  if (!Number.isInteger(resultCount) || resultCount < 1) {
    throw new Error("Browser processing completed without output artifacts.");
  }
  console.log(
    JSON.stringify({ applicationUrl, crossOriginIsolated: isolated, resultCount })
  );
  cdp.close();
} finally {
  browser.kill();
  if (browser.exitCode === null) {
    await Promise.race([
      once(browser, "exit"),
      new Promise((resolveWait) => setTimeout(resolveWait, 5_000))
    ]);
  }
  try {
    await rm(profilePath, {
      recursive: true,
      force: true,
      maxRetries: 10,
      retryDelay: 250
    });
  } catch (error) {
    console.warn(`Temporary browser profile cleanup failed: ${error}`);
  }
}

function findBrowser() {
  const candidates = process.platform === "win32"
    ? [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
      ]
    : ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"];
  return candidates.find(existsSync);
}

async function waitForTarget(port) {
  return waitFor(async () => {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (!response.ok) return undefined;
      const targets = await response.json();
      return targets.find(({ type }) => type === "page");
    } catch {
      return undefined;
    }
  });
}

function connect(url) {
  const socket = new WebSocket(url);
  const pending = new Map();
  let nextId = 1;
  const ready = new Promise((resolveReady, rejectReady) => {
    socket.addEventListener("open", resolveReady, { once: true });
    socket.addEventListener("error", rejectReady, { once: true });
  });
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(String(data));
    if (!message.id) return;
    const operation = pending.get(message.id);
    if (!operation) return;
    pending.delete(message.id);
    if (message.error) operation.reject(new Error(message.error.message));
    else operation.resolve(message.result);
  });
  return {
    ready,
    send(method, params = {}) {
      const id = nextId++;
      return new Promise((resolveOperation, rejectOperation) => {
        pending.set(id, { resolve: resolveOperation, reject: rejectOperation });
        socket.send(JSON.stringify({ id, method, params }));
      });
    },
    close() {
      socket.close();
    }
  };
}

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  });
  if (result.exceptionDetails) {
    throw new Error(
      result.exceptionDetails.exception?.description ??
        result.exceptionDetails.text ??
        "Browser evaluation failed."
    );
  }
  return result.result.value;
}

async function waitForTerminalState(cdp, timeout) {
  return waitFor(async () => {
    const state = await evaluate(cdp, "document.querySelector('#state-label').textContent");
    return ["COMPLETE", "ERROR", "CANCELLED"].includes(state) ? state : undefined;
  }, timeout);
}

async function waitFor(operation, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const value = await operation();
    if (value) return value;
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`Timed out after ${Math.round(timeout / 1_000)} seconds.`);
}
