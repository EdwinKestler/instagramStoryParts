from moviepy.editor import VideoFileClip
import os
import sys
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg
import moviepy.config as mpy_config
from ffprobe_utils import get_ffprobe_path, run_ffprobe
from typing import Tuple, Optional, Dict, Any, List
from logger_config import get_logger

# Constants for configuration
FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
SEGMENT_DURATION_DEFAULT = 60
MAX_WORKERS = 4

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": FFMPEG_BINARY})

logger = get_logger(__name__)


def get_keyframes(video_path: str, ffprobe_path: str) -> List[float]:
    """Extract keyframes (I-frames) from the video using ffprobe.
    
    Args:
        video_path: Path to the video file.
        ffprobe_path: Path to ffprobe binary.
    
    Returns:
        List[float]: List of keyframe timestamps in seconds.
    """
    data = run_ffprobe(
        ffprobe_path,
        ["-select_streams", "v:0", "-show_entries", "frame=pkt_pts_time,pts_time,pict_type"],
        video_path,
    )
    if not data or "frames" not in data:
        logger.warning("No keyframes detected in %s", video_path)
        return []
    keyframes = []
    for f in data["frames"]:
        if f.get("pict_type") == "I":
            time = f.get("pkt_pts_time") or f.get("pts_time")
            if time is not None:
                keyframes.append(float(time))
    logger.info("Found %d keyframes in %s", len(keyframes), video_path)
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
        logger.info("No keyframes found, using original time: %s", time)
        return time
    closest_keyframe = min(keyframes, key=lambda x: abs(x - time))
    logger.info("Adjusted time %s to keyframe at %s", time, closest_keyframe)
    return closest_keyframe

def export_part(video_path: str, start_time: float, end_time: float, output_path: str) -> Tuple[str, bool, Optional[str]]:
    """Export a video segment by calling export_part.py.
    
    Args:
        video_path: Path to the input video.
        start_time: Start time in seconds.
        end_time: End time in seconds.
        output_path: Path for the output video.
    
    Returns:
        Tuple[str, bool, Optional[str]]: (output_path, success, error_message)
    """
    command = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "export_part.py"),
        video_path,
        str(start_time),
        str(end_time),
        output_path
    ]
    try:
        subprocess.run(command, check=True)
        return output_path, True, None
    except subprocess.CalledProcessError as e:
        return output_path, False, str(e)

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

        logger.info("Video duration: %.2f seconds", video_duration)
        logger.info("Segment duration: %d seconds", segment_duration)
        logger.info("Total parts: %d", num_parts)

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
                    logger.warning(
                        "Invalid time range after adjustment: %s to %s, using original",
                        adjusted_start,
                        adjusted_end,
                    )
                    adjusted_start = start_time
                    adjusted_end = end_time
                
                output_filename = f"{base_name}-part{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    logger.info("Skipping existing file: %s", output_filename)
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
                    logger.info("Exported: %s", output_path)
                else:
                    logger.error("Failed: %s - %s", output_path, error)

        video.close()
        return num_parts

    except FileNotFoundError as e:
        logger.error("Video file not found: %s", e)
        raise
    except ValueError as e:
        logger.error("Invalid video data or time range: %s", e)
        raise
    except Exception as e:
        logger.error("Exception in trim_video_to_parts: %s", e)
        raise

if __name__ == "__main__":
    # Example usage for testing
    video_path = "sample_video.mp4"
    trim_video_to_parts(video_path, segment_duration=SEGMENT_DURATION_DEFAULT)