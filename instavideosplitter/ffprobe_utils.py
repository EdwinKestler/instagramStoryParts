"""Utilities for running ffprobe and parsing its JSON output."""

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from .ffmpeg_config import get_ffprobe_path

logger = logging.getLogger(__name__)


def run_ffprobe(args: List[str], video_path: str) -> Optional[Dict[str, Any]]:
    """Execute ffprobe with *args* against *video_path* and return parsed JSON.

    Args:
        args: Extra ffprobe arguments inserted before the output format flags.
        video_path: Path to the video file to probe.

    Returns:
        Parsed JSON dict, or ``None`` on any failure.
    """
    ffprobe = get_ffprobe_path()
    if not ffprobe:
        logger.error("Cannot run ffprobe: binary not found.")
        return None

    cmd = [ffprobe, "-loglevel", "error"] + args + ["-of", "json", video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error("ffprobe failed: %s", exc.stderr.strip() if exc.stderr else exc)
    except json.JSONDecodeError as exc:
        logger.error("Could not parse ffprobe output: %s", exc)
    except OSError as exc:
        logger.error("Could not execute ffprobe (%s): %s", ffprobe, exc)
    return None
