import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wave import installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            "HOME": str(self.root),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_RUNTIME_DIR": str(self.root / "runtime"),
            "PREFIX": str(self.root / "prefix"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.source = Path(__file__).resolve().parents[1]

    def test_install_and_upgrade_preserve_station_edits(self):
        with patch("sys.argv", ["installer", str(self.source)]):
            self.assertEqual(installer.main(), 0)
        config = self.root / "config/cyber-wave/config.json"
        edited = json.loads(config.read_text())
        edited["stations"].append({"name": "My Station", "url": "https://radio.example/stream"})
        config.write_text(json.dumps(edited))
        with patch("sys.argv", ["installer", str(self.source)]):
            self.assertEqual(installer.main(), 0)
        stations = json.loads(config.read_text())["stations"]
        self.assertEqual(len(stations), 4)
        self.assertEqual(stations[-1]["name"], "My Station")
        command = self.root / "prefix/bin/cyber-wave"
        self.assertIn("cyber-wave-managed-command", command.read_text())
        installed_themes = self.root / "data/cyber-wave/src/cyber_wave/themes"
        self.assertTrue((installed_themes / "synthwave.css").is_file())
        self.assertTrue((installed_themes / "greenline.css").is_file())
        self.assertTrue((installed_themes / "husky.css").is_file())
        environment = dict(os.environ)
        environment["CYBER_WAVE_COMMAND"] = str(command)
        result = subprocess.run([str(command), "--theme", "husky"], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "config/cyber-wave/theme").read_text().strip(), "husky")

    def test_unowned_command_is_not_overwritten(self):
        command = self.root / "prefix/bin/cyber-wave"
        command.parent.mkdir(parents=True)
        command.write_text("user data\n")
        with patch("sys.argv", ["installer", str(self.source)]):
            self.assertEqual(installer.main(), 1)
        self.assertEqual(command.read_text(), "user data\n")


if __name__ == "__main__":
    unittest.main()
