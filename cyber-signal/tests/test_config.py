import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_signal.config import load_config, validate_config
from cyber_signal.checks import disk_status, updates_result
from cyber_signal import cli


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

    def test_theme_sync_appends_valid_managed_mako_rules(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}), \
             patch.object(cli.shutil, "which", return_value="/usr/bin/mako"):
            mako_config = Path(directory) / "mako/config"
            mako_config.parent.mkdir()
            mako_config.write_text("[urgency=normal]\nborder-color=#ff00ff\n")
            self.assertTrue(cli._write_mako_styles("[app-name=\"cyber-signal\"]\ntext-color=#b7f7c0\n"))
            result = mako_config.read_text()
            self.assertIn("# END cyber-signal managed theme\n", result)
            self.assertGreater(result.index("[app-name=\"cyber-signal\"]"), result.index("[urgency=normal]"))
            self.assertNotIn("include=", result)

    def test_theme_can_be_saved_without_requiring_a_running_mako_daemon(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}), \
             patch.object(cli, "_write_mako_styles", return_value=True), \
             patch.object(cli.shutil, "which", return_value="/usr/bin/makoctl"), \
             patch.object(cli.subprocess, "run") as run:
            self.assertEqual(cli._theme("greenline", reload_mako=False), 0)
            run.assert_not_called()
            config = json.loads((Path(directory) / "cyber-signal/config.json").read_text())
            self.assertEqual(config["theme"], "greenline")

    def test_uninstall_removes_only_managed_mako_block(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}), \
             patch.object(cli.shutil, "which", return_value=None):
            mako_config = Path(directory) / "mako/config"
            mako_config.parent.mkdir()
            mako_config.write_text(
                "background-color=#111111\n"
                "# BEGIN cyber-signal managed theme\n"
                "include=/tmp/cyber-signal/active.mako\n"
                "# END cyber-signal managed theme\n"
                "text-color=#ffffff\n"
            )
            self.assertTrue(cli._remove_mako_block())
            self.assertEqual(mako_config.read_text(), "background-color=#111111\ntext-color=#ffffff\n")


if __name__ == "__main__":
    unittest.main()
