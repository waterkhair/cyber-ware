"""Tests for explicit Hyprlock wallpaper synchronization."""

import json
import hashlib
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
        self.include = config.parent / "hyprlock-wallpaper.conf"
        config.write_text(f"source = {self.include}\nbackground {{\n    path = $CYBER_WALLPAPER\n}}\ngeneral {{\n    hide_cursor = true\n}}\n")
        (state / "current").write_text(str(source) + "\n")
        environment = patch.dict(os.environ, {
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_image_sync_writes_include_without_editing_hyprlock_and_purge_restores_original(self):
        original = self.config.read_bytes()
        wallpaper = sync_lock_wallpaper()
        self.assertEqual(wallpaper.read_bytes(), b"image bytes")
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.include.read_text(), f"$CYBER_WALLPAPER = {wallpaper}\n")
        self.assertIn("hide_cursor = true", self.config.read_text())
        self.assertEqual(validate_purge(), (self.include, b"$CYBER_WALLPAPER = /dev/null\n"))

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
        self.include.write_text(self.include.read_text() + "# user edit\n")
        with self.assertRaisesRegex(RuntimeError, "changes since wallpaper sync"):
            validate_purge()

    def test_repeated_sync_keeps_original_and_records_user_edits(self):
        sync_lock_wallpaper()
        backup = self.state / "lock-sync/original-wallpaper-include.conf"
        self.include.write_text(self.include.read_text() + "# user edit\n")
        sync_lock_wallpaper()
        self.assertEqual(backup.read_bytes(), b"")
        metadata = json.loads((backup.parent / "metadata.json").read_text())
        self.assertTrue(metadata["user_modified"])
        with self.assertRaisesRegex(RuntimeError, "changes since wallpaper sync"):
            validate_purge()

    def prepare_legacy(self):
        original = b"background {\n    color = black\n}\n"
        current = b"background {\n    path = /old/wallpaper.jpg\n}\n"
        self.config.write_bytes(current)
        sync = self.state / "lock-sync"
        sync.mkdir()
        (sync / "original-hyprlock.conf").write_bytes(original)
        metadata = sync / "metadata.json"
        metadata.write_text(json.dumps({"config_path": str(self.config), "managed_config_sha256": hashlib.sha256(current).hexdigest()}))
        return metadata, current

    def test_failed_render_does_not_publish_migration_and_can_retry(self):
        metadata, current = self.prepare_legacy()
        before = metadata.read_bytes()
        with patch("cyber_wall.lock_wallpaper._render_lock_image", side_effect=RuntimeError("render failed")):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                sync_lock_wallpaper()
        self.assertEqual(self.config.read_bytes(), current)
        self.assertEqual(metadata.read_bytes(), before)
        self.assertFalse(self.include.exists())
        sync_lock_wallpaper()
        self.assertIn(f"source = {self.include}", self.config.read_text())

    def test_publication_failure_rolls_back_migration(self):
        from cyber_wall.lock_wallpaper import _atomic_write
        metadata, current = self.prepare_legacy()
        before = metadata.read_bytes()
        def fail_metadata(path, data, mode=0o600):
            if path == metadata:
                raise OSError("publication failed")
            _atomic_write(path, data, mode)
        with patch("cyber_wall.lock_wallpaper._atomic_write", side_effect=fail_metadata):
            with self.assertRaisesRegex(OSError, "publication failed"):
                sync_lock_wallpaper()
        self.assertEqual(self.config.read_bytes(), current)
        self.assertEqual(metadata.read_bytes(), before)
        self.assertFalse(self.include.exists())
        sync_lock_wallpaper()

    def test_missing_integration_reports_error_without_changes(self):
        self.config.write_text("background {\n    color = black\n}\n")
        with self.assertRaisesRegex(RuntimeError, "does not use"):
            sync_lock_wallpaper()
        self.assertFalse(self.include.exists())


if __name__ == "__main__":
    unittest.main()
