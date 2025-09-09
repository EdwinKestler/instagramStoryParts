# export_part.py
import sys
import os
from typing import Tuple, Optional, Dict, Any
from moviepy.editor import VideoFileClip
import moviepy.config as mpy_config
from ffprobe_utils import get_ffprobe_path, run_ffprobe
from ffmpeg_config import get_ffmpeg_path

# Constants for configuration
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"
AUDIO_FPS = 44100
PRESET = "medium"
THREADS = 4
AUDIO_CHANNELS = 2

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": get_ffmpeg_path()})


def check_audio_stream(video_path: str, ffprobe_path: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if the input video has an audio stream.
    
    Args:
        video_path: Path to the video file.
        ffprobe_path: Path to ffprobe binary.
    
    Returns:
        Tuple[bool, Optional[Dict]]: (has_audio, audio_info) where audio_info has codec and sample rate.
    """
    data = run_ffprobe(ffprobe_path, ["-show_streams", "-select_streams", "a"], video_path)
    if not data or "streams" not in data or not data["streams"]:
        print(f"[WARNING] No audio stream detected in {video_path}")
        return False, None
    audio_info = data["streams"][0]
    print(f"[INFO] Audio stream detected in {video_path}: "
          f"codec={audio_info.get('codec_name', 'unknown')}, "
          f"sample_rate={audio_info.get('sample_rate', 'unknown')}")
    return True, audio_info

def verify_output_audio(output_path: str, ffprobe_path: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Verify if the output video has an audio stream.
    
    Args:
        output_path: Path to the output video file.
        ffprobe_path: Path to ffprobe binary.
    
    Returns:
        Tuple[bool, Optional[Dict]]: (has_audio, audio_info) where audio_info has codec and sample rate.
    """
    data = run_ffprobe(ffprobe_path, ["-show_streams", "-select_streams", "a"], output_path)
    if not data or "streams" not in data or not data["streams"]:
        print(f"[WARNING] No audio stream detected in output {output_path}")
        return False, None
    audio_info = data["streams"][0]
    print(f"[INFO] Audio stream verified in {output_path}: "
          f"codec={audio_info.get('codec_name', 'unknown')}, "
          f"sample_rate={audio_info.get('sample_rate', 'unknown')}")
    return True, audio_info

def main():
    """Main function to trim a video segment and export it with audio."""
    # Parse arguments
    try:
        video_path, start, end, output_path = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    except (IndexError, ValueError) as e:
        print(f"[ERROR] Invalid arguments: {e}")
        sys.exit(1)

    # Generate unique temp audio file name
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    temp_audio_file = f"temp-audio-{base_name}.m4a"

    print(f"[INFO] Trimming {video_path} from {start}s to {end}s into {output_path}")
    
    # Locate ffprobe once
    ffprobe_path = get_ffprobe_path()
    has_audio = False

    try:
        # Check for audio stream in input
        has_audio, audio_info = check_audio_stream(video_path, ffprobe_path)

        # Load and trim the video
        with VideoFileClip(video_path).subclip(start, end) as clip:
            # Adjust audio settings based on input
            audio_codec = AUDIO_CODEC if has_audio else None
            audio_bitrate = AUDIO_BITRATE if has_audio else None
            audio_fps = int(audio_info.get("sample_rate", AUDIO_FPS)) if has_audio and audio_info else AUDIO_FPS

            # Write the output video
            clip.write_videofile(
                output_path,
                codec=VIDEO_CODEC,
                audio=has_audio,
                audio_codec=audio_codec,
                temp_audiofile=temp_audio_file if has_audio else None,
                remove_temp=False,  # Keep for debugging
                verbose=False,
                audio_bitrate=audio_bitrate,
                audio_fps=audio_fps,
                preset=PRESET,
                threads=THREADS,
                ffmpeg_params=["-ac", str(AUDIO_CHANNELS)]  # Force stereo
            )

        # Verify audio in output
        if has_audio:
            output_has_audio, output_audio_info = verify_output_audio(output_path, ffprobe_path)
            if not output_has_audio:
                print(f"[WARNING] Audio export failed for {output_path}")

        # Clean up temp file
        if has_audio and os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
                print(f"[INFO] Cleaned up temporary audio file: {temp_audio_file}")
            except OSError as e:
                print(f"[WARNING] Failed to remove temp audio file {temp_audio_file}: {e}")
                
    except FileNotFoundError as e:
        print(f"[ERROR] Video file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] Invalid time range or video data: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error trimming video: {e}")
        if has_audio and os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
                print(f"[INFO] Cleaned up temporary audio file on error: {temp_audio_file}")
            except OSError as e:
                print(f"[WARNING] Failed to remove temp audio file on error {temp_audio_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
