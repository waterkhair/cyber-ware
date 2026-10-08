"""Wallpaper replacement must not lose ownership of a surviving process."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cyber_wall.wallpaper import _stop_managed


class WallpaperStopTests(unittest.TestCase):
    def test_surviving_process_keeps_tracking_files(self):
        with TemporaryDirectory() as directory:
            pid_file = Path(directory) / "mpvpaper.pid"
            socket_file = Path(directory) / "mpvpaper.sock"
            pid_file.write_text("123\n")
            socket_file.touch()
            with patch("cyber_wall.wallpaper._managed_pid", return_value=123), \
                 patch("cyber_wall.wallpaper.os.kill"), \
                 patch("cyber_wall.wallpaper.time.monotonic", side_effect=[0, 3]):
                with self.assertRaisesRegex(RuntimeError, "did not stop"):
                    _stop_managed(pid_file, socket_file)
            self.assertEqual(pid_file.read_text(), "123\n")
            self.assertTrue(socket_file.exists())

    def test_exited_process_cleans_tracking_files(self):
        with TemporaryDirectory() as directory:
            pid_file = Path(directory) / "mpvpaper.pid"
            socket_file = Path(directory) / "mpvpaper.sock"
            pid_file.write_text("123\n")
            socket_file.touch()
            with patch("cyber_wall.wallpaper._managed_pid", return_value=123), \
                 patch("cyber_wall.wallpaper.os.kill", side_effect=[None, ProcessLookupError]), \
                 patch("cyber_wall.wallpaper.time.monotonic", side_effect=[0, 3]):
                _stop_managed(pid_file, socket_file)
            self.assertFalse(pid_file.exists())
            self.assertFalse(socket_file.exists())
