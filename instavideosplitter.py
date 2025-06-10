from moviepy.editor import VideoFileClip
import os
import sys
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg
import moviepy.config as mpy_config
import json

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})

def get_ffprobe_path():
    """
    Derive the ffprobe path from the FFMPEG binary path provided by imageio_ffmpeg.
    """
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
        if os.path.exists(ffprobe_path):
            return ffprobe_path
        else:
            print(f"ffprobe not found at {ffprobe_path}")
            return None
    except Exception as e:
        print(f"Error locating ffprobe: {e}")
        return None

def get_keyframes(video_path):
    """
    Extract keyframes (I-frames) from the video using ffprobe.
    Returns a list of timestamps (in seconds) for keyframes.
    """
    ffprobe_path = get_ffprobe_path()
    if not ffprobe_path:
        print("Cannot detect keyframes: ffprobe not available")
        return []
    
    try:
        cmd = [
            ffprobe_path, "-loglevel", "error", "-select_streams", "v:0",
            "-show_entries", "frame=pkt_pts_time,pict_type", "-of", "json", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frames = json.loads(result.stdout)["frames"]
        keyframes = [float(f["pkt_pts_time"]) for f in frames if f["pict_type"] == "I"]
        print(f"Found {len(keyframes)} keyframes in {video_path}")
        return keyframes
    except subprocess.CalledProcessError as e:
        print(f"Error detecting keyframes: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing ffprobe output: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in get_keyframes: {e}")
        return []

def adjust_to_keyframe(time, keyframes):
    """
    Adjust a given time to the nearest keyframe.
    If no keyframes are available, return the original time.
    """
    if not keyframes:
        print(f"No keyframes found, using original time: {time}")
        return time
    closest_keyframe = min(keyframes, key=lambda x: abs(x - time))
    print(f"Adjusted time {time} to keyframe at {closest_keyframe}")
    return closest_keyframe

def export_part(video_path, start_time, end_time, output_path):
    """
    Export a video segment by calling export_part.py.
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

def trim_video_to_parts(video_path, output_dir=None, progress_callback=None, segment_duration=60):
    """
    Trim a video into parts, aligning cuts with keyframes for better quality.
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

        print(f"Video duration: {video_duration:.2f} seconds")
        print(f"Segment duration: {segment_duration} seconds")
        print(f"Total parts: {num_parts}")

        # Get keyframes for alignment
        keyframes = get_keyframes(video_path)

        # Process each part
        tasks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            for i in range(num_parts):
                # Original start and end times
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, video_duration)
                
                # Adjust times to nearest keyframes
                adjusted_start = adjust_to_keyframe(start_time, keyframes)
                adjusted_end = adjust_to_keyframe(end_time, keyframes)
                
                # Ensure adjusted times are valid
                if adjusted_start >= adjusted_end or adjusted_end > video_duration:
                    print(f"Invalid time range after adjustment: {adjusted_start} to {adjusted_end}, using original")
                    adjusted_start = start_time
                    adjusted_end = end_time
                
                output_filename = f"{base_name}-part{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"Skipping existing file: {output_filename}")
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
                    print(f"Exported: {output_path}")
                else:
                    print(f"Failed: {output_path} - {error}")

        video.close()
        return num_parts

    except Exception as e:
        print(f"Exception: {e}")
        raise

if __name__ == "__main__":
    # Example usage for testing
    video_path = "sample_video.mp4"
    trim_video_to_parts(video_path, segment_duration=60)