"""Core video-splitting logic.

Public surface
--------------
trim_video_to_parts()   Split a video file into equal-length segments.
get_keyframes()         Extract I-frame timestamps via ffprobe.
adjust_to_keyframe()    Snap a time value to the nearest keyframe.
"""

import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

import numpy as np
from moviepy.editor import AudioClip, ColorClip, VideoFileClip, concatenate_videoclips

from .constants import (
    AUDIO_BITRATE,
    AUDIO_CHANNELS,
    AUDIO_CODEC,
    ENCODE_PRESET,
    ENCODE_THREADS,
    HW_ENCODE_PRESET,
    HW_VIDEO_CODEC,
    LONG_LAST_THRESHOLD,
    MAX_WORKERS,
    SEGMENT_DURATION_DEFAULT,
)
from .ffmpeg_config import get_ffmpeg_path, get_ffprobe_path, get_use_cuda
from .ffprobe_utils import run_ffprobe

logger = logging.getLogger(__name__)


# ── Keyframe helpers ──────────────────────────────────────────────────────────

def get_keyframes(video_path: str) -> List[float]:
    """Return I-frame timestamps (seconds) for *video_path*.

    Args:
        video_path: Path to the video file.

    Returns:
        Sorted list of keyframe timestamps in seconds.
        Returns an empty list if detection fails.
    """
    data = run_ffprobe(
        [
            "-select_streams", "v:0",
            "-show_entries", "frame=pkt_pts_time,pts_time,pict_type",
        ],
        video_path,
    )
    if not data or "frames" not in data:
        logger.warning("No keyframe data found in %s", video_path)
        return []

    keyframes = []
    for f in data["frames"]:
        if f.get("pict_type") == "I":
            ts = f.get("pkt_pts_time") or f.get("pts_time")
            if ts is not None:
                keyframes.append(float(ts))

    logger.debug("Found %d keyframes in %s", len(keyframes), video_path)
    return keyframes


def adjust_to_keyframe(time: float, keyframes: List[float]) -> float:
    """Return the keyframe timestamp nearest to *time*.

    Args:
        time: Desired time in seconds.
        keyframes: List of available keyframe timestamps.

    Returns:
        Nearest keyframe timestamp, or *time* unchanged if *keyframes* is empty.
    """
    if not keyframes:
        return time
    nearest = min(keyframes, key=lambda k: abs(k - time))
    logger.debug("Snapped %.3fs → %.3fs (keyframe)", time, nearest)
    return nearest


# ── Segment export helpers ────────────────────────────────────────────────────

def _stream_copy(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> Tuple[str, bool, Optional[str]]:
    """Copy a time range from *video_path* without re-encoding.

    Returns:
        ``(output_path, success, error_message)``
    """
    duration = max(end - start, 0.0)
    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c", "copy",
        output_path,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path, True, None
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode(errors="replace").strip() if exc.stderr else str(exc)
        return output_path, False, msg


def _pad_with_black(video_path: str, pad_duration: float) -> Tuple[bool, Optional[str]]:
    """Append *pad_duration* seconds of black frames (+ silence) to *video_path* in-place."""
    try:
        clip = VideoFileClip(video_path)
        w, h = clip.size
        audio = clip.audio

        black = ColorClip(size=(w, h), color=(0, 0, 0), duration=pad_duration)
        if audio:
            silence = AudioClip(
                lambda t: np.zeros_like(t),
                duration=pad_duration,
                fps=int(audio.fps),
            )
            black = black.set_audio(silence)

        final = concatenate_videoclips([clip, black])
        temp = video_path + ".tmp.mp4"

        use_cuda = get_use_cuda()
        vcodec = HW_VIDEO_CODEC if use_cuda else "libx264"
        vpreset = HW_ENCODE_PRESET if use_cuda else ENCODE_PRESET
        write_kwargs: dict = dict(
            codec=vcodec,
            audio=audio is not None,
            audio_codec=AUDIO_CODEC if audio else None,
            audio_bitrate=AUDIO_BITRATE if audio else None,
            audio_fps=int(audio.fps) if audio else None,
            verbose=False,
            preset=vpreset,
            ffmpeg_params=["-ac", str(AUDIO_CHANNELS)] if audio else [],
        )
        if not use_cuda:
            write_kwargs["threads"] = ENCODE_THREADS

        final.write_videofile(temp, **write_kwargs)
        final.close()
        clip.close()
        os.replace(temp, video_path)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _export_and_pad(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
    pad: float,
) -> Tuple[str, bool, Optional[str]]:
    """Stream-copy a segment then optionally pad it with black frames."""
    out, ok, err = _stream_copy(video_path, start, end, output_path)
    if ok and pad > 0:
        ok, err = _pad_with_black(output_path, pad)
    return out, ok, err


# ── Public splitting API ──────────────────────────────────────────────────────

def trim_video_to_parts(
    video_path: str,
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    segment_duration: int = SEGMENT_DURATION_DEFAULT,
    offset: float = 0.0,
    workers: int = MAX_WORKERS,
    ask_allow_long_last_part: Optional[Callable[[float], bool]] = None,
) -> int:
    """Split *video_path* into equal-length segments.

    Cuts are aligned to the nearest I-frame to avoid visual artefacts.
    The last segment is padded with black frames when shorter than
    *segment_duration*, or the user is prompted when it is slightly longer.

    Args:
        video_path: Path to the input video file.
        output_dir: Directory for output files. Defaults to the video's directory.
        progress_callback: Called as ``callback(completed, total)`` after each part.
        segment_duration: Target length of each segment in seconds.
        offset: Seconds added to every keyframe-aligned cut point (may be negative).
        workers: Maximum number of parallel export processes.
        ask_allow_long_last_part: Callback receiving the actual length (seconds)
            of the last segment; return ``True`` to keep it, ``False`` to trim.

    Returns:
        Total number of output parts (including any that already existed).

    Raises:
        FileNotFoundError: If *video_path* does not exist.
        ValueError: If the video cannot be opened or has no duration.
    """
    video = VideoFileClip(video_path)
    duration = video.duration
    video.close()

    if not duration:
        raise ValueError(f"Could not read duration from {video_path}")

    base = os.path.splitext(os.path.basename(video_path))[0]
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(video_path))
    os.makedirs(output_dir, exist_ok=True)

    num_parts = int(duration // segment_duration) + (1 if duration % segment_duration else 0)

    logger.info(
        "Video: %.2fs  |  segment: %ds  |  parts: %d",
        duration, segment_duration, num_parts,
    )

    keyframes = get_keyframes(video_path)
    ffprobe_path = get_ffprobe_path()  # noqa: F841 — kept for future per-segment probing

    tasks: List = []
    task_meta: List[Tuple[int, str]] = []  # (part_index, output_path)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(num_parts):
            nominal_start = i * segment_duration
            start = max(0.0, min(adjust_to_keyframe(nominal_start, keyframes) + offset, duration))
            end = min(start + segment_duration, duration)
            pad = 0.0

            if i == num_parts - 1:
                actual = duration - start
                if actual < segment_duration:
                    pad = segment_duration - actual
                    end = duration
                elif actual <= segment_duration * LONG_LAST_THRESHOLD:
                    if ask_allow_long_last_part and ask_allow_long_last_part(actual):
                        end = duration
                # else: trim to exactly segment_duration (end already set)

            out_name = f"{base}-part{i + 1}.mp4"
            out_path = os.path.join(output_dir, out_name)

            if os.path.exists(out_path):
                logger.info("Skipping existing: %s", out_name)
                continue

            tasks.append(pool.submit(_export_and_pad, video_path, start, end, out_path, pad))
            task_meta.append((i + 1, out_path))

        completed = 0
        for future in as_completed(tasks):
            out_path, ok, err = future.result()
            completed += 1
            if progress_callback:
                progress_callback(completed, len(tasks))
            if ok:
                logger.info("✓ %s", os.path.basename(out_path))
            else:
                logger.error("✗ %s — %s", os.path.basename(out_path), err)

    return num_parts
