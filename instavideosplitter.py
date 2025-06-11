from moviepy.editor import VideoFileClip, ColorClip, AudioClip, concatenate_videoclips
import numpy as np
import os
import sys
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg
import moviepy.config as mpy_config
from ffprobe_utils import get_ffprobe_path, run_ffprobe
from typing import Tuple, Optional, Dict, Any, List

# Constants for configuration
FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
SEGMENT_DURATION_DEFAULT = 60
MAX_WORKERS = 4

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": FFMPEG_BINARY})


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

def pad_with_black(video_path: str, pad_duration: float) -> Tuple[bool, Optional[str]]:
    """Append black frames to a video using moviepy."""
    try:
        clip = VideoFileClip(video_path)
        w, h = clip.size
        fps = clip.fps or 24
        audio = clip.audio

        black = ColorClip(size=(w, h), color=(0, 0, 0), duration=pad_duration)
        if audio:
            sr = int(audio.fps)
            silence = AudioClip(lambda t: np.zeros_like(t), duration=pad_duration, fps=sr)
            black = black.set_audio(silence)

        final = concatenate_videoclips([clip, black])
        temp_path = video_path + ".tmp"
        final.write_videofile(
            temp_path,
            codec="libx264",
            audio=audio is not None,
            audio_codec=AUDIO_CODEC if audio else None,
            audio_bitrate=AUDIO_BITRATE if audio else None,
            audio_fps=int(audio.fps) if audio else None,
            verbose=False,
            preset=PRESET,
            threads=THREADS,
            ffmpeg_params=["-ac", str(AUDIO_CHANNELS)]
        )
        final.close()
        clip.close()
        os.replace(temp_path, video_path)
        return True, None
    except Exception as e:
        return False, str(e)

def export_and_pad(video_path: str, start_time: float, end_time: float, output_path: str, pad_time: float) -> Tuple[str, bool, Optional[str]]:
    """Export a segment and optionally pad with black frames."""
    out, success, err = export_part(video_path, start_time, end_time, output_path)
    if success and pad_time > 0:
        ok, perr = pad_with_black(output_path, pad_time)
        if not ok:
            return output_path, False, perr
    return out, success, err

def trim_video_to_parts(video_path: str, output_dir: Optional[str] = None,
                        progress_callback: Optional[callable] = None,
                        segment_duration: int = SEGMENT_DURATION_DEFAULT,
                        offset: float = 0.0,
                        ask_allow_long_last_part: Optional[callable] = None) -> int:
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
                part_start_nominal = i * segment_duration
                part_start = adjust_to_keyframe(part_start_nominal, keyframes) + offset
                part_start = max(0, min(part_start, video_duration))
                part_end = min(part_start + segment_duration, video_duration)

                if i == num_parts - 1:
                    actual_length = video_duration - part_start
                    if actual_length < segment_duration:
                        pad_time = segment_duration - actual_length
                    else:
                        pad_time = 0
                        if actual_length > segment_duration and actual_length <= segment_duration * 1.1:
                            if ask_allow_long_last_part and ask_allow_long_last_part(actual_length):
                                part_end = video_duration
                            else:
                                part_end = min(part_start + segment_duration, video_duration)
                        else:
                            part_end = min(part_start + segment_duration, video_duration)
                else:
                    pad_time = 0

                output_filename = f"{base_name}-part{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"[INFO] Skipping existing file: {output_filename}")
                    continue

                tasks.append(executor.submit(export_and_pad, video_path, part_start, part_end, output_path, pad_time))

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
    import argparse

    parser = argparse.ArgumentParser(
        description="Split a video into Instagram story sized segments")
    parser.add_argument(
        "video",
        help="Path to the input video file")
    parser.add_argument(
        "-o", "--output-dir",
        help="Directory to save the segments (defaults to the video folder)")
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=SEGMENT_DURATION_DEFAULT,
        help="Length of each segment in seconds")
    parser.add_argument(
        "-f", "--offset",
        type=float,
        default=0.0,
        help="Offset applied after keyframe alignment in seconds")
    parser.add_argument(
        "--allow-long-last",
        action="store_true",
        help="Allow the last part to exceed the duration if it is only slightly longer")
    args = parser.parse_args()

    def cli_allow(length: float) -> bool:
        if args.allow_long_last:
            return True
        try:
            resp = input(
                f"The last part will be {length:.1f}s (>{args.duration}s). Allow? [y/N] ")
            return resp.strip().lower().startswith("y")
        except EOFError:
            return False

    def cli_progress(completed: int, total: int):
        percent = int(completed / total * 100)
        print(f"\rProgress: {completed}/{total} ({percent}%)", end="")

    trim_video_to_parts(
        args.video,
        output_dir=args.output_dir,
        progress_callback=cli_progress,
        segment_duration=args.duration,
        offset=args.offset,
        ask_allow_long_last_part=cli_allow,
    )
    print()
