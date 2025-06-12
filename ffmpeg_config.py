import imageio_ffmpeg
import moviepy.config as mpy_config

_ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
mpy_config.change_settings({"FFMPEG_BINARY": _ffmpeg_path})


def set_ffmpeg_path(path: str) -> None:
    """Set the path to the ffmpeg binary used by the application."""
    global _ffmpeg_path
    if path:
        _ffmpeg_path = path
        mpy_config.change_settings({"FFMPEG_BINARY": _ffmpeg_path})


def get_ffmpeg_path() -> str:
    """Get the currently configured ffmpeg binary path."""
    return _ffmpeg_path
