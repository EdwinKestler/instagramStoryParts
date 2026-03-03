# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [Semantic Versioning](https://semver.org/).

---

## [1.0.0-rc2] — 2026-03-02

### Added

- **CUDA / NVENC acceleration** — `--cuda` CLI flag and "Use CUDA / NVENC" GUI checkbox
  enable `h264_nvenc` (preset `p4`) for re-encoding operations; error if unavailable
- `nvenc_available()`, `set_use_cuda()`, `get_use_cuda()` in `ffmpeg_config.py`
- `HW_VIDEO_CODEC` and `HW_ENCODE_PRESET` constants in `constants.py`
- Workers slider in the GUI (1–8 parallel processes) with a live label
- Video metadata display in the GUI: resolution, fps, and duration shown after video selection
- Live log panel during trimming via `_GUILogHandler` (thread-safe `logging.Handler` → `CTkTextbox`)
- "Open Output Folder" button that persists after a successful trim
- GUI section headers ("FILES", "SETTINGS", "ACTIONS") for visual hierarchy
- Monospaced log font (Consolas 12) for aligned technical output
- Tinted thumbnail frame — preview area is always visible even before a file is loaded
- Bold, larger "Trim Video" primary button; ghost-style "Close" button
- Automated release workflow (`.github/workflows/release.yml`) — triggered by `v*.*.*` tags,
  builds Windows and Linux binaries with PyInstaller and publishes them as GitHub Release assets

### Changed

- `_pad_with_black()` and `export_segment()` now auto-select `h264_nvenc` / `libx264` based on the CUDA flag; `-threads` is omitted for NVENC
- Window geometry bumped to 940×640, minimum size 720×520
- `Trim Video` button disabled while processing and re-enabled in the `finally` block
- All background-thread UI updates use `self.after(0, …)` for thread safety
- `_ask_allow_longer()` uses a `queue.Queue` round-trip to run `messagebox` on the main thread
- Thumbnail loading and video metadata probing both offloaded to daemon threads

### Fixed

- `messagebox` / `progress.set()` called from background thread (Tkinter not thread-safe) — now routed through `self.after()`
- `_show_thumbnail()` blocking the main thread — moved to a daemon thread
- Workers setting not forwarded to `trim_video_to_parts()` — now passed correctly

---

## [1.0.0-rc1] — 2026-03-02

### Added

- GUI with CustomTkinter: video browser, output directory selector, custom ffmpeg folder button
- Segment duration selector: 15, 30, 60, 90 seconds
- Offset slider (±5 s) to fine-tune each cut relative to the nearest keyframe
- Keyframe-aligned cuts via ffprobe — stream copy, no re-encoding
- Multi-threaded export (up to 4 parallel workers)
- Short segment padding with black frames and silence
- Optional keep-longer-last-segment prompt (GUI dialog / `--allow-long-last` CLI flag)
- Video thumbnail preview in the GUI
- Dark / Light mode toggle
- Cross-platform output folder auto-open (Windows, macOS, Linux)
- CLI interface (`instavideosplitter`) with `-d`, `-o`, `-f`, `-w`, `--ffmpeg-dir`, `--allow-long-last`, `--gui`, `--version` flags
- `pyproject.toml` with `instavideosplitter` and `instavideosplitter-gui` entry points
- `constants.py` as single source of truth for all shared defaults
- PyInstaller spec for standalone GUI executable
- GitHub Actions CI: ruff lint + pytest on Windows / macOS / Linux × Python 3.10–3.12
- Issue templates and PR template

### Changed

- Source reorganised into `instavideosplitter/` Python package
  (`__main__.py`, `constants.py`, `core.py`, `gui.py`, `export_part.py`, `ffmpeg_config.py`, `ffprobe_utils.py`)
- `requirements.txt` re-encoded to UTF-8 and deduplicated
- ffmpeg binary resolution made lazy with `FFMPEG_DIR` environment variable support

### Fixed

- `output/` typo in `.gitignore` (was `ouput/`)
