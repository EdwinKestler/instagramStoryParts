import unittest
from pathlib import Path

from instagram_story_parts.domain import MediaInfo, SplitRequest
from instagram_story_parts.planner import SegmentPlanner


class SegmentPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = SegmentPlanner()

    def test_plan_is_continuous_and_pads_only_final_short_segment(self):
        request = SplitRequest(Path("movie.mp4"), Path("parts"), 60)
        media = MediaInfo(125, (0, 59, 121))

        segments = self.planner.plan(request, media)

        self.assertEqual([(item.start, item.end) for item in segments], [
            (0.0, 59.0),
            (59.0, 121.0),
            (121.0, 125),
        ])
        self.assertEqual(segments[-1].pad_duration, 56)
        self.assertTrue(all(
            left.end == right.start
            for left, right in zip(segments, segments[1:])
        ))

    def test_positive_offset_never_discards_the_start_of_the_video(self):
        request = SplitRequest(Path("movie.mp4"), segment_duration=60, offset=3)
        media = MediaInfo(100, (0, 62))

        segments = self.planner.plan(request, media)

        self.assertEqual(segments[0].start, 0)
        self.assertEqual(segments[0].end, 65)
        self.assertEqual(segments[-1].end, 100)

    def test_policy_can_keep_a_slightly_long_final_segment(self):
        request = SplitRequest(Path("movie.mp4"), segment_duration=60)
        media = MediaInfo(165, (0, 60, 100))

        kept = self.planner.plan(request, media, lambda _length: True)
        split = self.planner.plan(request, media, lambda _length: False)

        self.assertEqual(kept[-1].duration, 65)
        self.assertEqual([item.duration for item in split[-2:]], [60, 5])
        self.assertEqual(split[-1].pad_duration, 55)

    def test_invalid_duration_is_rejected(self):
        request = SplitRequest(Path("movie.mp4"), segment_duration=0)

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            self.planner.plan(request, MediaInfo(10))


if __name__ == "__main__":
    unittest.main()
