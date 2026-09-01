import tempfile
import unittest
from pathlib import Path

from instagram_story_parts.media import FFmpegLocator, MediaToolNotFound


class FFmpegLocatorTests(unittest.TestCase):
    def test_configured_directory_supports_windows_executable_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ffmpeg.exe").touch()
            (root / "ffprobe.exe").touch()
            locator = FFmpegLocator()

            locator.configure(root)

            self.assertEqual(locator.ffmpeg(), root / "ffmpeg.exe")
            self.assertEqual(locator.ffprobe(), root / "ffprobe.exe")

    def test_configure_rejects_incomplete_tool_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ffmpeg.exe").touch()

            with self.assertRaises(MediaToolNotFound):
                FFmpegLocator().configure(root)

    def test_configure_accepts_chocolatey_package_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_directory = root / "ffmpeg" / "bin"
            binary_directory.mkdir(parents=True)
            (binary_directory / "ffmpeg.exe").touch()
            (binary_directory / "ffprobe.exe").touch()
            locator = FFmpegLocator()

            locator.configure(root)

            self.assertEqual(locator.directory, binary_directory)
            self.assertEqual(locator.ffmpeg(), binary_directory / "ffmpeg.exe")
            self.assertEqual(locator.ffprobe(), binary_directory / "ffprobe.exe")


if __name__ == "__main__":
    unittest.main()
