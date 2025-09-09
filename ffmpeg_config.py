import os
import warnings
import imageio_ffmpeg
import moviepy.config as mpy_config

_ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())


def _apply_ffmpeg_dir() -> None:
    """Update moviepy and PATH to use the current ffmpeg directory."""
    ffmpeg_bin = os.path.join(_ffmpeg_dir, "ffmpeg")
    mpy_config.change_settings({"FFMPEG_BINARY": ffmpeg_bin})
    if _ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


_apply_ffmpeg_dir()


def set_ffmpeg_dir(path: str) -> None:
    """Set the directory containing the ffmpeg binaries."""
    global _ffmpeg_dir
    if not path:
        return

    ffmpeg_bin = os.path.join(path, "ffmpeg")
    ffprobe_bin = os.path.join(path, "ffprobe")

    if not os.path.isfile(ffmpeg_bin):
        raise FileNotFoundError(f"'ffmpeg' not found in '{path}'")

    if not os.path.isfile(ffprobe_bin):
        warnings.warn(f"'ffprobe' not found in '{path}'", RuntimeWarning)
        return

    _ffmpeg_dir = path
    _apply_ffmpeg_dir()


def set_ffmpeg_path(path: str) -> None:
    """Compatibility wrapper: accept a binary path or directory."""
    if path and not os.path.isdir(path):
        path = os.path.dirname(path)
    set_ffmpeg_dir(path)


def get_ffmpeg_dir() -> str:
    """Get the directory containing ffmpeg binaries."""
    return _ffmpeg_dir


def get_ffmpeg_path() -> str:
    """Get the full path to the ffmpeg executable."""
    return os.path.join(_ffmpeg_dir, "ffmpeg")

