"""Compatibility helpers for callers using the original module API."""

import json
import subprocess
from typing import Any, Optional

from instagram_story_parts.media import MediaToolNotFound, default_locator


def get_ffprobe_path() -> Optional[str]:
    try:
        return str(default_locator.ffprobe())
    except MediaToolNotFound:
        return None


def run_ffprobe(
    ffprobe_path: str, args: list[str], video_path: str
) -> Optional[dict[str, Any]]:
    if not ffprobe_path:
        return None
    command = [ffprobe_path, "-loglevel", "error", *args, "-of", "json", video_path]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None
