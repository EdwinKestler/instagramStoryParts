import os
import json
import subprocess
import shutil
from typing import Optional, Dict, Any
import imageio_ffmpeg

FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()


def get_ffprobe_path() -> Optional[str]:
    """Locate the ffprobe binary in FFMPEG directory or system PATH.

    Returns:
        Optional[str]: Path to ffprobe if found, None otherwise.
    """
    try:
        ffmpeg_path = FFMPEG_BINARY
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
        if os.path.exists(ffprobe_path):
            print(f"[INFO] ffprobe found at {ffprobe_path}")
            return ffprobe_path
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            print(f"[INFO] ffprobe found in PATH at {ffprobe_path}")
            return ffprobe_path
        print("[ERROR] ffprobe not found in FFMPEG directory or system PATH")
        return None
    except OSError as e:
        print(f"[ERROR] Failed to locate ffprobe: {e}")
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
        print("[ERROR] Cannot run ffprobe: binary not available")
        return None
    try:
        cmd = [ffprobe_path, "-loglevel", "error"] + args + ["-of", "json", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ffprobe command failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse ffprobe output: {e}")
        return None
    except OSError as e:
        print(f"[ERROR] Failed to execute ffprobe: {e}")
        return None
