from moviepy.editor import VideoFileClip
import os
import sys
import subprocess
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import imageio_ffmpeg
import moviepy.config as mpy_config

mpy_config.change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})


def export_part(video_path, start_time, end_time, output_path):
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
    try:
        video = VideoFileClip(video_path)
        video_duration = video.duration

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        if output_dir is None:
            output_dir = os.path.dirname(video_path)

        num_parts = int(video_duration // segment_duration)
        if video_duration % segment_duration != 0:
            num_parts += 1

        print(f"Video duration: {video_duration:.2f} seconds")
        print(f"Segment duration: {segment_duration} seconds")
        print(f"Total parts: {num_parts}")

        tasks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            for i in range(num_parts):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, video_duration)
                output_filename = f"{base_name}-part{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"Skipping existing file: {output_filename}")
                    continue

                tasks.append(executor.submit(export_part, video_path, start_time, end_time, output_path))

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
