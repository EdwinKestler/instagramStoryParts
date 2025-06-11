from moviepy.editor import VideoFileClip
import os
import sys
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg
import moviepy.config as mpy_config
import json
import shutil
from typing import Tuple, Optional, Dict, Any, List

# Constants for configuration
FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
SEGMENT_DURATION_DEFAULT = 60
MAX_WORKERS = 4

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": FFMPEG_BINARY})

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

def get_keyframes(video_path: str, ffprobe_path: str) -> List[float]:
    """Extract keyframes (I-frames) from the video using ffprobe.
    
    Args:
        video_path: Path to the video file.
        ffprobe_path: Path to ffprobe binary.
    
    Returns:
        List[float]: List of keyframe timestamps in seconds.
    """
    data = run_ffprobe(ffprobe_path, ["-select_streams", "v:0", "-show_entries", "frame=pkt_pts_time,pts_time,pict_type"], video_path)
    if not data or "frames" not in data:
        print(f"[WARNING] No keyframes detected in {video_path}")
        return []
    keyframes = []
    for f in data["frames"]:
        if f.get("pict_type") == "I":
            time = f.get("pkt_pts_time") or f.get("pts_time")
            if time is not None:
                keyframes.append(float(time))
    print(f"[INFO] Found {len(keyframes)} keyframes in {video_path}")
    return keyframes

def adjust_to_keyframe(time: float, keyframes: List[float]) -> float:
    """Adjust a given time to the nearest keyframe.
    
    Args:
        time: Original time in seconds.
        keyframes: List of keyframe timestamps.
    
    Returns:
        float: Adjusted time aligned to the nearest keyframe.
    """
    if not keyframes:
        print(f"[INFO] No keyframes found, using original time: {time}")
        return time
    closest_keyframe = min(keyframes, key=lambda x: abs(x - time))
    print(f"[INFO] Adjusted time {time} to keyframe at {closest_keyframe}")
    return closest_keyframe

def export_part(video_path: str, start_time: float, end_time: float, output_path: str) -> Tuple[str, bool, Optional[str]]:
    """Export a segment using ffmpeg without re-encoding when possible.

    Args:
        video_path: Path to the input video.
        start_time: Start time in seconds.
        end_time: End time in seconds.
        output_path: Path for the output video.

    Returns:
        Tuple[str, bool, Optional[str]]: (output_path, success, error message)
    """

    duration = max(end_time - start_time, 0)

    command = [
        FFMPEG_BINARY,
        "-y",                 # overwrite output
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-c", "copy",
        output_path,
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path, True, None
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        return output_path, False, error_msg

def trim_video_to_parts(video_path: str, output_dir: Optional[str] = None, 
                        progress_callback: Optional[callable] = None, 
                        segment_duration: int = SEGMENT_DURATION_DEFAULT) -> int:
    """Trim a video into parts, aligning cuts with keyframes for better quality.
    
    Args:
        video_path: Path to the input video.
        output_dir: Directory for output files; defaults to video's directory.
        progress_callback: Function to report progress.
        segment_duration: Duration of each segment in seconds.
    
    Returns:
        int: Number of parts created.
    """
    try:
        # Load the video
        video = VideoFileClip(video_path)
        video_duration = video.duration

        # Get base name and output directory
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        if output_dir is None:
            output_dir = os.path.dirname(video_path)

        # Calculate number of parts
        num_parts = int(video_duration // segment_duration)
        if video_duration % segment_duration != 0:
            num_parts += 1

        print(f"[INFO] Video duration: {video_duration:.2f} seconds")
        print(f"[INFO] Segment duration: {segment_duration} seconds")
        print(f"[INFO] Total parts: {num_parts}")

        # Get keyframes for alignment
        ffprobe_path = get_ffprobe_path()
        keyframes = get_keyframes(video_path, ffprobe_path)

        # Process each part
        tasks = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i in range(num_parts):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, video_duration)
                
                # Adjust times to nearest keyframes
                adjusted_start = adjust_to_keyframe(start_time, keyframes)
                adjusted_end = adjust_to_keyframe(end_time, keyframes)
                
                # Ensure adjusted times are valid
                if adjusted_start >= adjusted_end or adjusted_end > video_duration:
                    print(f"[WARNING] Invalid time range after adjustment: {adjusted_start} to {adjusted_end}, using original")
                    adjusted_start = start_time
                    adjusted_end = end_time
                
                output_filename = f"{base_name}-part{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"[INFO] Skipping existing file: {output_filename}")
                    continue

                tasks.append(executor.submit(export_part, video_path, adjusted_start, adjusted_end, output_path))

            # Track progress
            completed_parts = 0
            for future in as_completed(tasks):
                output_path, success, error = future.result()
                completed_parts += 1
                if progress_callback:
                    progress_callback(completed_parts, num_parts)
                if success:
                    print(f"[INFO] Exported: {output_path}")
                else:
                    print(f"[ERROR] Failed: {output_path} - {error}")

        video.close()
        return num_parts

    except FileNotFoundError as e:
        print(f"[ERROR] Video file not found: {e}")
        raise
    except ValueError as e:
        print(f"[ERROR] Invalid video data or time range: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Exception in trim_video_to_parts: {e}")
        raise

if __name__ == "__main__":
    # Example usage for testing
    video_path = "sample_video.mp4"
    trim_video_to_parts(video_path, segment_duration=SEGMENT_DURATION_DEFAULT)