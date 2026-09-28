import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_signal.config import load_config, validate_config
from cyber_signal.checks import disk_status, updates_result


class ConfigTests(unittest.TestCase):
    def test_defaults_load_without_config_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            config = load_config()
        self.assertEqual(config["theme"], "synthwave")
        self.assertEqual(config["checks"], {"network": True, "updates": True, "disk": True})

    def test_user_config_merges_check_flags(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            config_dir = Path(directory) / "cyber-signal"
            config_dir.mkdir()
            (config_dir / "config.json").write_text(json.dumps({"checks": {"updates": False}}))
            config = load_config()
        self.assertFalse(config["checks"]["updates"])
        self.assertTrue(config["checks"]["network"])

    def test_rejects_bad_threshold_order(self):
        from cyber_signal.config import DEFAULTS
        config = json.loads(json.dumps(DEFAULTS))
        config["disk_warning_percent"] = 95
        config["disk_critical_percent"] = 90
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_disk_usage_missing_mount_is_skipped(self):
        self.assertIsNone(disk_status("/definitely-not-a-cyber-signal-mount"))

    def test_first_update_snapshot_notifies_if_updates_are_available(self):
        from cyber_signal import checks
        from unittest.mock import MagicMock

        completed = MagicMock(returncode=0, stdout="pkg-a 1 -> 2\npkg-b 3 -> 4\n", stderr="")
        with patch.object(checks.shutil, "which", return_value="/usr/bin/checkupdates"), \
             patch.object(checks, "_run", return_value=completed), \
             patch.object(checks, "read_state", return_value=None), \
             patch.object(checks, "write_state"):
            result = updates_result()
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "2 package updates available")


if __name__ == "__main__":
    unittest.main()
