# InstaVideoSplitter / Story Parts

Split long videos into short, social-media-sized MP4 parts. The repository now
contains two clients around the same explicit planning and state-machine
architecture:

- A Python command-line and desktop application backed by native FFmpeg.
- A static, installable web application that runs FFmpeg entirely in the
  browser. Selected videos and generated parts are never uploaded or stored by
  the deployment.

The project is licensed under the MIT License.

Production web app: [instagram-story-parts.vercel.app](https://instagram-story-parts.vercel.app)

## Web application

Requirements: Node.js 24 or newer and npm.

```powershell
cd web
npm install
npm run dev
```

Open the local URL Vite prints, normally `http://localhost:5173`. Select a
video, choose a duration, optionally select a local destination folder, and
process it. The first run downloads approximately 31 MB of FFmpeg-WASM; later
runs can use the browser cache. Browser processing currently rejects files of
2 GB or larger, and practical phone limits may be lower due to available RAM.

Production checks:

```powershell
cd web
npm test
npm run typecheck
npm run build
npm run preview
```

With Chrome or Edge installed and a local test video available, run the optional
end-to-end production smoke test from `web/`:

```powershell
npm run test:browser -- "..\input\Angel_a.mp4"
```

The browser client has no upload endpoint, analytics, external fonts, or cloud
media storage. Chromium-based desktop browsers can write parts directly to a
chosen local folder. Other browsers fall back to individual downloads, and
supported phones can also use the system share sheet.

See [the Vercel deployment and budget runbook](docs/VERCEL_DEPLOYMENT.md) for
deployment, privacy verification, and the controls that keep the monthly target
below $100 USD.

## Python architecture

The Python codebase uses a layered, object-oriented design:

- `instagram_story_parts/domain.py` contains immutable request, media, segment,
  and result models.
- `instagram_story_parts/fsm.py` defines the explicit job lifecycle:
  `created -> validating -> probing -> planning -> exporting -> completed`.
  Any active state may transition to `failed`.
- `instagram_story_parts/planner.py` is pure business logic. It creates a
  continuous plan, aligns internal boundaries to keyframes, and pads a short
  final segment.
- `instagram_story_parts/ports.py` defines probe and exporter protocols. Tests
  can inject fakes without importing GUI or media libraries.
- `instagram_story_parts/media.py` provides the FFmpeg and FFprobe adapters.
- `instagram_story_parts/service.py` owns orchestration, concurrency, progress,
  and FSM transitions.
- The root scripts remain compatibility entry points for existing users.

The TypeScript web client mirrors these boundaries in `web/src/core` and uses a
`LocalMediaAdapter` port for the browser FFmpeg implementation. This keeps UI,
job lifecycle, segment policy, and media execution independently testable.

## Python installation

Requirements:

- Python 3.10 or newer
- FFmpeg and FFprobe on `PATH`, or a selected directory containing both

The FFmpeg selector and `--ffmpeg-dir` accept common Chocolatey package roots.
For example, this package root is resolved to its nested `ffmpeg\bin` folder:

```text
C:\ProgramData\chocolatey\lib\ffmpeg-full\tools
```

Install in a virtual environment:

```powershell
python -m pip install .
```

For development tools:

```powershell
python -m pip install -e ".[dev]"
```

## Python command line and GUI

Installed CLI:

```powershell
insta-split myvideo.mp4 --duration 60 --output-dir output
```

From a source checkout:

```powershell
python instavideosplitter.py myvideo.mp4 -d 60 -o output
python instavideosplitter_gui.py
```

Useful CLI options include:

- `--offset SECONDS` shifts internal cuts after keyframe alignment.
- `--allow-long-last` keeps a final part up to 10% longer than requested.
- `--ffmpeg-dir PATH` selects a directory containing FFmpeg and FFprobe.
- `--overwrite` replaces existing output parts.
- `--workers N` controls concurrent exports.

Install `customtkinter` through the project package before launching the GUI;
running it from a virtual environment with missing dependencies raises
`ModuleNotFoundError`.

## Tests

Python tests do not require FFmpeg or a display:

```powershell
python -m unittest discover -s tests -v
```

Web tests do not read or upload media:

```powershell
cd web
npm test
```

## License

Copyright (c) 2024-2026 Edwin Kestler. Released under the [MIT License](LICENSE).
