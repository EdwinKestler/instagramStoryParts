# export_part.py
import sys
from moviepy.editor import VideoFileClip
import imageio_ffmpeg
import moviepy.config as mpy_config

# Set FFMPEG binary for stability
mpy_config.change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})

# Parse arguments
video_path, start, end, output_path = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]

print(f"Trimming {video_path} from {start}s to {end}s into {output_path}")
try:
    clip = VideoFileClip(video_path).subclip(start, end)
    clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        verbose=False
    )
    clip.reader.close()
    if clip.audio:
        clip.audio.reader.close_proc()
    clip.close()
except Exception as e:
    print(f"Error trimming video: {e}")
    sys.exit(1)
