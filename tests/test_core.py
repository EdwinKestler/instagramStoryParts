"""Tests for instavideosplitter.core helpers."""

from instavideosplitter.constants import (
    LONG_LAST_THRESHOLD,
    MAX_WORKERS,
    SEGMENT_DURATION_DEFAULT,
)
from instavideosplitter.core import adjust_to_keyframe


# ── adjust_to_keyframe ────────────────────────────────────────────────────────

def test_adjust_exact_match():
    assert adjust_to_keyframe(2.0, [0.0, 2.0, 4.0, 6.0]) == 2.0


def test_adjust_rounds_down():
    assert adjust_to_keyframe(2.9, [0.0, 2.0, 4.0, 6.0]) == 2.0


def test_adjust_rounds_up():
    assert adjust_to_keyframe(3.1, [0.0, 2.0, 4.0, 6.0]) == 4.0


def test_adjust_midpoint_picks_first():
    # 3.0 is equidistant; min() picks the earlier keyframe
    assert adjust_to_keyframe(3.0, [0.0, 2.0, 4.0]) == 2.0


def test_adjust_empty_keyframes_returns_original():
    assert adjust_to_keyframe(5.5, []) == 5.5


def test_adjust_single_keyframe():
    assert adjust_to_keyframe(100.0, [1.5]) == 1.5


# ── Constants sanity ──────────────────────────────────────────────────────────

def test_segment_duration_default():
    assert SEGMENT_DURATION_DEFAULT == 60


def test_max_workers_positive():
    assert MAX_WORKERS >= 1


def test_long_last_threshold_above_one():
    assert LONG_LAST_THRESHOLD > 1.0
