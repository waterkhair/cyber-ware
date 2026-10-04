"""Tests for explicit Hyprlock wallpaper synchronization."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_wall.lock_wallpaper import sync_lock_wallpaper, validate_purge


class LockSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        state = self.root / "state/cyber-wall"
        config = self.root / "config/hypr/hyprlock.conf"
        source = self.root / "wallpapers/current.png"
        state.mkdir(parents=True)
        config.parent.mkdir(parents=True)
        source.parent.mkdir()
        source.write_bytes(b"image bytes")
        config.write_text("general {\n    hide_cursor = true\n}\n\nbackground {\n    color = black\n}\n")
        self.state, self.config, self.source = state, config, source
        (state / "current").write_text(str(source) + "\n")
        environment = patch.dict(os.environ, {
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_image_sync_updates_background_and_purge_restores_original(self):
        original = self.config.read_bytes()
        wallpaper = sync_lock_wallpaper()
        self.assertEqual(wallpaper.read_bytes(), b"image bytes")
        self.assertIn(f"path = {wallpaper}", self.config.read_text())
        self.assertIn("hide_cursor = true", self.config.read_text())
        self.assertEqual(validate_purge(), (self.config, original))

    def test_video_sync_creates_a_still_and_detects_edits(self):
        video = self.root / "wallpapers/loop.mp4"
        video.write_bytes(b"video bytes")
        (self.state / "current").write_text(str(video) + "\n")

        def fake_ffmpeg(args, **kwargs):
            Path(args[-1]).write_bytes(b"still frame")

        with patch("cyber_wall.lock_wallpaper.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("cyber_wall.lock_wallpaper.subprocess.run", side_effect=fake_ffmpeg):
            wallpaper = sync_lock_wallpaper()
        self.assertEqual(wallpaper.suffix, ".jpg")
        self.assertEqual(wallpaper.read_bytes(), b"still frame")
        self.config.write_text(self.config.read_text() + "# user edit\n")
        with self.assertRaisesRegex(RuntimeError, "changes since wallpaper sync"):
            validate_purge()

    def test_repeated_sync_keeps_original_and_records_user_edits(self):
        original = self.config.read_bytes()
        sync_lock_wallpaper()
        backup = self.state / "lock-sync/original-hyprlock.conf"
        self.config.write_text(self.config.read_text() + "# user edit\n")
        sync_lock_wallpaper()
        self.assertEqual(backup.read_bytes(), original)
        metadata = json.loads((backup.parent / "metadata.json").read_text())
        self.assertTrue(metadata["user_modified"])
        with self.assertRaisesRegex(RuntimeError, "changes since wallpaper sync"):
            validate_purge()


if __name__ == "__main__":
    unittest.main()
