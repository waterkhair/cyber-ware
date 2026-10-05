import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cyber_panel import cli, installer


ROOT = Path(__file__).resolve().parents[1]


class CyberPanelAssetsTests(unittest.TestCase):
    def test_waybar_config_is_valid_json_and_has_current_module_layout(self):
        config = json.loads((ROOT / "config.jsonc").read_text(encoding="utf-8"))
        self.assertEqual(config[0]["modules-left"], ["ext/workspaces"])
        self.assertEqual(config[0]["modules-right"], ["mpris", "tray", "network", "pulseaudio", "clock"])
        self.assertEqual(config[0]["ext/workspaces"]["sort-by-id"], True)

    def test_themes_are_distinct_and_present(self):
        synthwave = (ROOT / "themes/synthwave.css").read_text(encoding="utf-8")
        greenline = (ROOT / "themes/greenline.css").read_text(encoding="utf-8")
        self.assertIn("#8b5cf6", synthwave)
        self.assertIn("#8df0a6", greenline)
        self.assertNotEqual(synthwave, greenline)

    def test_install_then_uninstall_restores_original_waybar_files(self):
        with tempfile.TemporaryDirectory(prefix="cyber-panel-test-") as temp:
            root = Path(temp)
            waybar = root / "config/waybar"
            waybar.mkdir(parents=True)
            original_config = b"[{}]\n/* personal config */\n"
            original_style = b"/* personal stylesheet */\n"
            (waybar / "config.jsonc").write_bytes(original_config)
            (waybar / "style.css").write_bytes(original_style)
            env = {
                "HOME": str(root),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "PREFIX": str(root / "local"),
            }
            with patch.dict(os.environ, env, clear=False), redirect_stdout(StringIO()):
                self.assertEqual(installer.main(), 0)
                installed_config = json.loads((waybar / "config.jsonc").read_text(encoding="utf-8"))
                self.assertEqual(installed_config[0]["pulseaudio"]["on-click"], f"{root}/local/bin/cyber-console wiremix")
                self.assertEqual(installed_config[0]["network"]["on-click"], f"{root}/local/bin/cyber-console impala")
                self.assertNotEqual((waybar / "style.css").read_bytes(), original_style)
                self.assertEqual(cli.main(["--uninstall"]), 0)
            self.assertEqual((waybar / "config.jsonc").read_bytes(), original_config)
            self.assertEqual((waybar / "style.css").read_bytes(), original_style)
            self.assertFalse((root / "local/bin/cyber-panel").exists())

    def test_installer_refuses_symlinked_waybar_config(self):
        with tempfile.TemporaryDirectory(prefix="cyber-panel-symlink-test-") as temp:
            root = Path(temp)
            waybar = root / "config/waybar"
            waybar.mkdir(parents=True)
            target = root / "unrelated-config"
            target.write_text("user-owned config\n", encoding="utf-8")
            (waybar / "config.jsonc").symlink_to(target)
            env = {
                "HOME": str(root), "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"),
                "PREFIX": str(root / "local"),
            }
            with patch.dict(os.environ, env, clear=False), redirect_stdout(StringIO()):
                self.assertEqual(installer.main(), 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "user-owned config\n")

    def test_theme_command_switches_css_and_persists_lowercase_name(self):
        with tempfile.TemporaryDirectory(prefix="cyber-panel-theme-test-") as temp:
            root = Path(temp)
            (root / "themes").mkdir()
            for name in ("synthwave", "greenline", "husky"):
                shutil.copy2(ROOT / "themes" / f"{name}.css", root / "themes" / f"{name}.css")
            env = {
                "HOME": str(root),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "CYBER_PANEL_APP_DIR": str(root),
            }
            with patch.dict(os.environ, env, clear=False), patch.object(cli, "reload_waybar"), redirect_stdout(StringIO()):
                self.assertEqual(cli.main(["--theme", "greenline"]), 0)
            self.assertEqual((root / "config/waybar/style.css").read_text(), (root / "themes/greenline.css").read_text())
            self.assertEqual(json.loads((root / "config/cyber-panel/config.json").read_text())["theme"], "greenline")


if __name__ == "__main__":
    unittest.main()
