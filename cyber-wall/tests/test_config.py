from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wall.config import DEFAULTS, config_path, load_config, set_theme


class ConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/nonexistent/cyber-wall-test"}):
            config = load_config()
        self.assertEqual(config["directories"], DEFAULTS["directories"])
        self.assertEqual(config["output"], "auto")
        self.assertEqual(config["theme"], "synthwave")
        self.assertIn("--load-scripts=no", config["mpvpaper_options"])

    def test_user_values_override_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"output": "DP-1", "preview_timeout_seconds": 3}))
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                config = load_config()
        self.assertEqual(config["output"], "DP-1")
        self.assertEqual(config["preview_timeout_seconds"], 3)
        self.assertEqual(config["directories"], DEFAULTS["directories"])

    def test_greenline_theme_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"theme": "greenline"}))
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                config = load_config()
        self.assertEqual(config["theme"], "greenline")

    def test_set_theme_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"directories": ["~/Wallpapers"], "output": "DP-1"}))
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                set_theme("greenline")
            config = json.loads(path.read_text())
        self.assertEqual(config["theme"], "greenline")
        self.assertEqual(config["directories"], ["~/Wallpapers"])
        self.assertEqual(config["output"], "DP-1")

    def test_set_theme_rejects_unknown_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"theme": "synthwave"}))
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                with self.assertRaisesRegex(ValueError, "theme"):
                    set_theme("unknown")
            self.assertEqual(json.loads(path.read_text())["theme"], "synthwave")

    def test_rejects_invalid_directory_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"directories": "not-an-array"}')
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                with self.assertRaisesRegex(ValueError, "directories"):
                    load_config()

    def test_rejects_unknown_theme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"theme": "not-a-template"}')
            with patch.dict(os.environ, {"CYBER_WALL_CONFIG": str(path)}):
                with self.assertRaisesRegex(ValueError, "theme"):
                    load_config()

    def test_config_override_path(self) -> None:
        with patch.dict(os.environ, {"CYBER_WALL_CONFIG": "/tmp/my-cyber-wall.json"}):
            self.assertEqual(config_path(), Path("/tmp/my-cyber-wall.json"))


if __name__ == "__main__":
    unittest.main()
