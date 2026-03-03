# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [Semantic Versioning](https://semver.org/).

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
- CLI interface (`instavideosplitter`) with `-d`, `-o`, `-f`, `--allow-long-last` flags
- `pyproject.toml` with `instavideosplitter` and `instavideosplitter-gui` entry points
- PyInstaller spec for standalone GUI executable
- GitHub Actions CI: ruff lint + import checks on Windows / macOS / Linux × Python 3.10–3.12
- Issue templates and PR template

### Changed
- Source reorganised into `instavideosplitter/` Python package
  (`core.py`, `gui.py`, `export_part.py`, `ffmpeg_config.py`, `ffprobe_utils.py`)
- `requirements.txt` re-encoded to UTF-8 and deduplicated

### Fixed
- `output/` typo in `.gitignore` (was `ouput/`)
