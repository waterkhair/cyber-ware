import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_console import cli, installer


ROOT = Path(__file__).resolve().parents[1]


class CyberConsoleTests(unittest.TestCase):
    def test_default_configuration_lists_five_tools_with_distinct_classes(self):
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        apps = config["applications"]
        self.assertEqual(set(apps), {"impala", "wiremix", "bluetui", "btop", "yazi"})
        classes = [app["class"] for app in apps.values()]
        self.assertEqual(len(classes), len(set(classes)))
        self.assertEqual(apps["wiremix"]["command"], ["wiremix", "--mouse", "--theme", "default"])

    def test_cli_lists_tools_without_launching_anything(self):
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(cli.list_apps(config), 0)

    def test_existing_client_closes_without_starting_a_second_terminal(self):
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        with patch.object(cli, "close_window", return_value=True), patch.object(cli.os, "execvp") as execvp:
            self.assertEqual(cli.toggle("impala", config), 0)
        execvp.assert_not_called()

    def test_new_client_uses_dedicated_ghostty_class_and_app_arguments(self):
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        with (
            patch.object(cli, "close_window", return_value=False),
            patch.object(cli.shutil, "which", return_value="/usr/bin/found"),
            patch.object(cli.os, "execvp", side_effect=OSError("test stop")) as execvp,
        ):
            self.assertEqual(cli.toggle("wiremix", config), 1)
        executable, argv = execvp.call_args.args
        self.assertEqual(executable, "ghostty")
        self.assertIn("--class=org.cyber-ware.cyber-console.wiremix", argv)
        self.assertEqual(argv[-4:], ["wiremix", "--mouse", "--theme", "default"])

    def test_installer_creates_user_local_command_and_preserves_existing_config(self):
        with tempfile.TemporaryDirectory(prefix="cyber-console-test-") as temp:
            root = Path(temp)
            config_dir = root / "config/cyber-console"
            config_dir.mkdir(parents=True)
            customized = '{"terminal":"ghostty","applications":{"btop":{"class":"custom.btop","title":"btop","command":["btop"]}}}\n'
            (config_dir / "config.json").write_text(customized, encoding="utf-8")
            env = {
                "HOME": str(root),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "PREFIX": str(root / "local"),
            }
            which = lambda name: f"/usr/bin/{name}"
            with patch.dict(os.environ, env, clear=False), patch("cyber_console.installer.shutil.which", side_effect=which):
                self.assertEqual(installer.main(), 0)
                self.assertTrue((root / "local/bin/cyber-console").is_file())
                self.assertEqual((config_dir / "config.json").read_text(encoding="utf-8"), customized)
                self.assertEqual(cli.uninstall(False), 0)
            self.assertTrue((config_dir / "config.json").is_file())
            self.assertFalse((root / "local/bin/cyber-console").exists())

    def test_installer_reports_required_dependency_before_writing_config(self):
        with tempfile.TemporaryDirectory(prefix="cyber-console-missing-dep-") as temp:
            root = Path(temp)
            env = {
                "HOME": str(root),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "PREFIX": str(root / "local"),
            }
            which = lambda name: None if name == "ghostty" else f"/usr/bin/{name}"
            with patch.dict(os.environ, env, clear=False), patch("cyber_console.installer.shutil.which", side_effect=which):
                self.assertEqual(installer.main(), 1)
            self.assertFalse((root / "config/cyber-console/config.json").exists())


if __name__ == "__main__":
    unittest.main()
