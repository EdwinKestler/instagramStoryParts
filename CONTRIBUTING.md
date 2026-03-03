# Contributing to InstaVideoSplitter

Thank you for your interest in contributing! Here is everything you need to get started.

---

## Table of Contents

- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)
- [Development Setup](#development-setup)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Code Style](#code-style)
- [Project Structure](#project-structure)

---

## Reporting Bugs

1. Search [existing issues](https://github.com/EdwinKestler/instagramStoryParts/issues) first to avoid duplicates.
2. Open a new issue and include:
   - OS and Python version
   - ffmpeg version (`ffmpeg -version`)
   - Steps to reproduce
   - Expected vs actual behaviour
   - Any error messages or tracebacks

---

## Requesting Features

Open an issue with the `enhancement` label and describe:
- The problem you are trying to solve
- How the feature would work from the user's perspective
- Any alternatives you have considered

---

## Development Setup

```bash
# Fork and clone the repo
git clone https://github.com/<your-username>/instagramStoryParts.git
cd instagramStoryParts

# Create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install ruff
```

---

## Submitting a Pull Request

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```
2. Make your changes. Keep commits focused and write clear messages.
3. Lint your code before pushing:
   ```bash
   ruff check .
   ```
4. Push your branch and open a pull request against `main`.
5. Fill in the PR template and describe what changed and why.

PRs that break existing behaviour without a clear justification will not be merged.

---

## Code Style

- **Formatter / linter:** [Ruff](https://docs.astral.sh/ruff/) — run `ruff check .` before committing.
- **Type hints:** use them for all public functions (the existing codebase already does).
- **Docstrings:** follow the existing Google-style docstrings for public functions.
- **No breaking changes** to the CLI argument interface without a deprecation path.
- Keep GUI logic in `instavideosplitter_gui.py`; keep processing logic in `instavideosplitter.py` and helpers.

---

## Project Structure

```
instavideosplitter.py      # Core splitting logic + CLI
instavideosplitter_gui.py  # CustomTkinter GUI
export_part.py             # Audio-aware export & verification
ffmpeg_config.py           # ffmpeg/ffprobe binary management
ffprobe_utils.py           # ffprobe JSON wrapper
requirements.txt           # Runtime dependencies
```

---

By contributing you agree that your work will be released under the project's [MIT License](LICENSE).
