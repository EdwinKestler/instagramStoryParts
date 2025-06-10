# export_part.py
import sys
import os
from moviepy.editor import VideoFileClip
import imageio_ffmpeg
import moviepy.config as mpy_config

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})

# Parse arguments
video_path, start, end, output_path = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]

# Generate a unique temp audio file name based on output path
base_name = os.path.splitext(os.path.basename(output_path))[0]
temp_audio_file = f"temp-audio-{base_name}.m4a"

print(f"Trimming {video_path} from {start}s to {end}s into {output_path}")
try:
    clip = VideoFileClip(video_path).subclip(start, end)
    clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=temp_audio_file,
        remove_temp=False,  # Keep for debugging, remove manually if successful
        verbose=False
    )
    clip.reader.close()
    if clip.audio:
        clip.audio.reader.close_proc()
    clip.close()
    # Remove temp file only if successful
    if os.path.exists(temp_audio_file):
        os.remove(temp_audio_file)
except Exception as e:
    print(f"Error trimming video: {e}")
    sys.exit(1)