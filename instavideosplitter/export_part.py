"""Audio-aware single-segment export with pre/post stream verification."""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from moviepy.editor import VideoFileClip

from .constants import (
    AUDIO_BITRATE,
    AUDIO_CHANNELS,
    AUDIO_CODEC,
    AUDIO_FPS,
    ENCODE_PRESET,
    ENCODE_THREADS,
    HW_ENCODE_PRESET,
    HW_VIDEO_CODEC,
    VIDEO_CODEC,
)
from .ffmpeg_config import get_use_cuda
from .ffprobe_utils import run_ffprobe

logger = logging.getLogger(__name__)


# ── Audio stream helpers ──────────────────────────────────────────────────────

def check_audio_stream(
    video_path: str,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Return ``(has_audio, stream_info)`` for the first audio stream.

    Args:
        video_path: Path to the video file.

    Returns:
        ``(True, dict)`` when an audio stream is found, ``(False, None)`` otherwise.
    """
    data = run_ffprobe(["-show_streams", "-select_streams", "a"], video_path)
    if not data or not data.get("streams"):
        logger.warning("No audio stream in %s", video_path)
        return False, None
    info = data["streams"][0]
    logger.debug(
        "Audio stream in %s: codec=%s sample_rate=%s",
        video_path,
        info.get("codec_name", "?"),
        info.get("sample_rate", "?"),
    )
    return True, info


def verify_output_audio(output_path: str) -> bool:
    """Return ``True`` if *output_path* contains an audio stream."""
    data = run_ffprobe(["-show_streams", "-select_streams", "a"], output_path)
    has = bool(data and data.get("streams"))
    if not has:
        logger.warning("No audio stream found in output %s", output_path)
    return has


# ── Segment export ────────────────────────────────────────────────────────────

def export_segment(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> None:
    """Export a single video segment with full re-encode and audio verification.

    Unlike the stream-copy path in :mod:`core`, this function always re-encodes
    using ``libx264`` / AAC and verifies that audio survived.

    Args:
        video_path: Input video file.
        start: Start time in seconds.
        end: End time in seconds.
        output_path: Destination file path.

    Raises:
        FileNotFoundError: If *video_path* does not exist.
        ValueError: If the time range is invalid.
        RuntimeError: If the export fails for any other reason.
    """
    has_audio, audio_info = check_audio_stream(video_path)
    audio_fps = (
        int(audio_info.get("sample_rate", AUDIO_FPS))
        if has_audio and audio_info
        else AUDIO_FPS
    )

    base = os.path.splitext(os.path.basename(output_path))[0]
    temp_audio = os.path.join(os.path.dirname(output_path) or ".", f"_tmp_audio_{base}.m4a")

    use_cuda = get_use_cuda()
    vcodec = HW_VIDEO_CODEC if use_cuda else VIDEO_CODEC
    vpreset = HW_ENCODE_PRESET if use_cuda else ENCODE_PRESET

    logger.info(
        "Exporting segment %.1fs–%.1fs → %s [%s]",
        start, end, output_path, vcodec,
    )
    try:
        clip = VideoFileClip(video_path).subclip(start, end)
        write_kwargs: dict = dict(
            codec=vcodec,
            audio=has_audio,
            audio_codec=AUDIO_CODEC if has_audio else None,
            audio_bitrate=AUDIO_BITRATE if has_audio else None,
            audio_fps=audio_fps if has_audio else None,
            temp_audiofile=temp_audio if has_audio else None,
            remove_temp=True,
            verbose=False,
            preset=vpreset,
            ffmpeg_params=["-ac", str(AUDIO_CHANNELS)] if has_audio else [],
        )
        if not use_cuda:
            write_kwargs["threads"] = ENCODE_THREADS
        clip.write_videofile(output_path, **write_kwargs)
        clip.reader.close()
        if clip.audio:
            clip.audio.reader.close_proc()
        clip.close()
    except Exception as exc:
        raise RuntimeError(f"Export failed for {output_path}: {exc}") from exc
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except OSError:
                pass

    if has_audio and not verify_output_audio(output_path):
        logger.warning("Audio verification failed for %s", output_path)
