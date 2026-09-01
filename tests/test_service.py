import tempfile
import unittest
from pathlib import Path

from instagram_story_parts.domain import MediaInfo, SplitRequest
from instagram_story_parts.fsm import SplitState
from instagram_story_parts.service import VideoSplitService


class FakeProbe:
    def __init__(self, media=MediaInfo(125)):
        self.media = media
        self.calls = []

    def probe(self, video_path):
        self.calls.append(video_path)
        return self.media


class FakeExporter:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def export(self, request, segment, media):
        self.calls.append(segment)
        if self.error:
            raise self.error
        segment.output_path.write_bytes(b"video")


class VideoSplitServiceTests(unittest.TestCase):
    def test_service_runs_dependencies_and_reaches_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.touch()
            progress = []
            probe = FakeProbe()
            exporter = FakeExporter()
            service = VideoSplitService(probe, exporter)

            result = service.split(
                SplitRequest(source, root / "output", 60, max_workers=2),
                progress.append,
            )

            self.assertEqual(service.state_machine.state, SplitState.COMPLETED)
            self.assertEqual(result.completed_count, 3)
            self.assertEqual(len(exporter.calls), 3)
            self.assertEqual(progress[-1].completed, progress[-1].total)
            self.assertEqual(probe.calls, [source])

    def test_existing_outputs_are_reported_as_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.touch()
            output = root / "output"
            output.mkdir()
            existing = output / "source-part1.mp4"
            existing.touch()
            progress = []
            exporter = FakeExporter()
            service = VideoSplitService(FakeProbe(MediaInfo(30)), exporter)

            result = service.split(
                SplitRequest(source, output, 60),
                progress.append,
            )

            self.assertEqual(result.skipped, (existing,))
            self.assertEqual(exporter.calls, [])
            self.assertTrue(progress[0].skipped)

    def test_export_failure_moves_machine_to_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.touch()
            service = VideoSplitService(
                FakeProbe(MediaInfo(30)), FakeExporter(RuntimeError("boom"))
            )

            with self.assertRaisesRegex(RuntimeError, "boom"):
                service.split(SplitRequest(source, root / "output"))

            self.assertEqual(service.state_machine.state, SplitState.FAILED)

    def test_validation_failure_is_part_of_the_state_machine(self):
        service = VideoSplitService(FakeProbe(), FakeExporter())

        with self.assertRaises(FileNotFoundError):
            service.split(SplitRequest(Path("missing.mp4")))

        self.assertEqual(service.state_machine.state, SplitState.FAILED)


if __name__ == "__main__":
    unittest.main()
