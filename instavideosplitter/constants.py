"""Shared configuration constants for instavideosplitter.

All tuneable defaults live here so every module stays in sync and
users have a single place to look when overriding behaviour.
"""

# ── Video encoding ────────────────────────────────────────────────────────────
VIDEO_CODEC: str = "libx264"
ENCODE_PRESET: str = "medium"   # ffmpeg preset: ultrafast … veryslow
ENCODE_THREADS: int = 4

# ── Audio encoding ────────────────────────────────────────────────────────────
AUDIO_CODEC: str = "aac"
AUDIO_BITRATE: str = "192k"
AUDIO_FPS: int = 44100          # sample rate used when padding silence
AUDIO_CHANNELS: int = 2         # force stereo output

# ── Splitting defaults ────────────────────────────────────────────────────────
SEGMENT_DURATION_DEFAULT: int = 60   # seconds
MAX_WORKERS: int = 4                 # parallel ffmpeg export processes

# ── Last-segment policy ───────────────────────────────────────────────────────
#: If the last segment is within this ratio of the requested duration it is
#: considered "slightly long" and the user is prompted (or --allow-long-last
#: accepted).  Value of 1.10 means up to 10 % over.
LONG_LAST_THRESHOLD: float = 1.10
