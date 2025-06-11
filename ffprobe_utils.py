import os
import json
import subprocess
import shutil
from typing import Optional, Dict, Any
import imageio_ffmpeg
from logger_config import get_logger

FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()

logger = get_logger(__name__)


def get_ffprobe_path() -> Optional[str]:
    """Locate the ffprobe binary in FFMPEG directory or system PATH.

    Returns:
        Optional[str]: Path to ffprobe if found, None otherwise.
    """
    try:
        ffmpeg_path = FFMPEG_BINARY
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
        if os.path.exists(ffprobe_path):
            logger.info("ffprobe found at %s", ffprobe_path)
            return ffprobe_path
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            logger.info("ffprobe found in PATH at %s", ffprobe_path)
            return ffprobe_path
        logger.error("ffprobe not found in FFMPEG directory or system PATH")
        return None
    except OSError as e:
        logger.error("Failed to locate ffprobe: %s", e)
        return None


def run_ffprobe(ffprobe_path: str, args: list[str], video_path: str) -> Optional[Dict[str, Any]]:
    """Run ffprobe with given arguments and parse JSON output.

    Args:
        ffprobe_path: Path to ffprobe binary.
        args: List of ffprobe command arguments.
        video_path: Path to the video file.

    Returns:
        Optional[Dict[str, Any]]: Parsed JSON output or None if failed.
    """
    if not ffprobe_path:
        logger.error("Cannot run ffprobe: binary not available")
        return None
    try:
        cmd = [ffprobe_path, "-loglevel", "error"] + args + ["-of", "json", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("ffprobe command failed: %s", e)
        return None
    except json.JSONDecodeError as e:
        logger.error("Failed to parse ffprobe output: %s", e)
        return None
    except OSError as e:
        logger.error("Failed to execute ffprobe: %s", e)
        return None
