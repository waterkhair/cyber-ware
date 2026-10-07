import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wave import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "HOME": self.temp.name,
            "XDG_CONFIG_HOME": str(Path(self.temp.name) / "config"),
            "XDG_DATA_HOME": str(Path(self.temp.name) / "data"),
            "XDG_RUNTIME_DIR": str(Path(self.temp.name) / "runtime"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_station_is_esoterica_s3(self):
        station = config.load_config()["stations"][0]
        self.assertEqual(station["name"], "Esoterica Radio S3")
        self.assertTrue(station["url"].startswith("https://"))

    def test_invalid_station_url_is_rejected(self):
        path = config.paths()["config"]
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"stations": [{"name": "bad", "url": "file:///etc/passwd"}]}))
        with self.assertRaisesRegex(ValueError, r"HTTP\(S\)"):
            config.load_config()

    def test_duplicate_url_is_only_kept_once(self):
        path = config.paths()["config"]
        path.parent.mkdir(parents=True)
        config_data = {"stations": [config.DEFAULT["stations"][0], config.DEFAULT["stations"][0]]}
        path.write_text(json.dumps(config_data))
        self.assertEqual(len(config.load_config()["stations"]), 1)

    def test_empty_list_can_be_saved_for_readding_stations_later(self):
        path = config.paths()["config"]
        path.parent.mkdir(parents=True)
        config.save_config({"theme": "husky", "stations": []})
        self.assertEqual(config.load_config()["stations"], [])
        self.assertEqual(config.load_config()["theme"], "husky")

    def test_save_config_preserves_additional_settings(self):
        path = config.paths()["config"]
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"theme": "greenline", "custom": "keep", "stations": []}))
        data = config.load_config()
        data["stations"].append({"name": "Test radio", "url": "https://radio.example/stream"})
        config.save_config(data)
        saved = json.loads(path.read_text())
        self.assertEqual(saved["custom"], "keep")
        self.assertEqual(saved["stations"][0]["name"], "Test radio")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
