"""FFmpeg/ffprobe binary location management.

Resolution priority:
1. Explicit ``set_ffmpeg_dir()`` call (e.g. from the GUI)
2. ``FFMPEG_DIR`` environment variable
3. ``imageio_ffmpeg`` bundled binary
4. System PATH (``shutil.which``)

All detection is lazy — nothing runs at import time.
"""

import logging
import os
import shutil
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Platform executable suffix
_EXE: str = ".exe" if sys.platform == "win32" else ""

# Module-level state — None means "not yet initialised"
_ffmpeg_dir: Optional[str] = None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _auto_detect() -> str:
    """Return the ffmpeg binary directory via imageio_ffmpeg or PATH."""
    try:
        import imageio_ffmpeg  # optional bundled binary
        path = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        logger.debug("ffmpeg detected via imageio_ffmpeg: %s", path)
        return path
    except Exception:
        pass

    found = shutil.which("ffmpeg")
    if found:
        path = os.path.dirname(found)
        logger.debug("ffmpeg detected via system PATH: %s", path)
        return path

    logger.warning(
        "ffmpeg not found. Set the FFMPEG_DIR environment variable or "
        "call set_ffmpeg_dir() before processing."
    )
    return ""


def _resolve() -> str:
    """Return (and cache) the ffmpeg directory, initialising on first call."""
    global _ffmpeg_dir
    if _ffmpeg_dir is None:
        env = os.environ.get("FFMPEG_DIR", "").strip()
        _ffmpeg_dir = env if env else _auto_detect()
        _sync_moviepy()
    return _ffmpeg_dir


def _sync_moviepy() -> None:
    """Keep moviepy's internal FFMPEG_BINARY setting in sync."""
    try:
        import moviepy.config as mpy_config
        mpy_config.change_settings({"FFMPEG_BINARY": get_ffmpeg_path()})
    except Exception:
        pass


# ── CUDA / NVENC state ────────────────────────────────────────────────────────

_use_nvenc: bool = False


def nvenc_available() -> bool:
    """Return ``True`` if the resolved ffmpeg binary supports ``h264_nvenc``.

    The result is not cached — call it once and store it yourself if needed.
    """
    import subprocess

    try:
        result = subprocess.run(
            [get_ffmpeg_path(), "-encoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def set_use_cuda(enabled: bool) -> None:
    """Enable or disable CUDA/NVENC hardware encoding for re-encode operations."""
    global _use_nvenc
    _use_nvenc = enabled
    logger.debug("CUDA/NVENC %s", "enabled" if enabled else "disabled")


def get_use_cuda() -> bool:
    """Return ``True`` if CUDA/NVENC hardware encoding is currently enabled."""
    return _use_nvenc


# ── Public API ────────────────────────────────────────────────────────────────

def set_ffmpeg_dir(path: str) -> None:
    """Set the directory that contains the ffmpeg/ffprobe binaries.

    Also prepends *path* to ``os.environ["PATH"]`` so that child processes
    (e.g. moviepy) can locate the binaries without further configuration.
    """
    global _ffmpeg_dir
    if not path:
        return
    _ffmpeg_dir = path
    if path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
    _sync_moviepy()
    logger.debug("ffmpeg directory set to: %s", path)


def set_ffmpeg_path(path: str) -> None:
    """Compatibility shim: accept either a binary path or a directory."""
    if path and not os.path.isdir(path):
        path = os.path.dirname(path)
    set_ffmpeg_dir(path)


def get_ffmpeg_dir() -> str:
    """Return the directory that contains the ffmpeg binaries."""
    return _resolve()


def get_ffmpeg_path() -> str:
    """Return the full path to the ``ffmpeg`` executable."""
    return os.path.join(_resolve(), "ffmpeg" + _EXE)


def get_ffprobe_path() -> str:
    """Return the full path to the ``ffprobe`` executable."""
    return os.path.join(_resolve(), "ffprobe" + _EXE)
