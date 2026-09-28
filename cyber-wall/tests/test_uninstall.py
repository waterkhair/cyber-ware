from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wall.uninstall import main


class UninstallTests(unittest.TestCase):
    def _environment(self, root: Path) -> dict[str, str]:
        return {
            "PREFIX": str(root / "prefix"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
        }

    def _seed_install(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        command = root / "prefix/bin/cyber-wall"
        app = root / "data/cyber-wall"
        config = root / "config/cyber-wall/config.json"
        state = root / "state/cyber-wall/current"
        cache = root / "cache/cyber-wall/preview.jpg"
        for path in (command, app / "src/module.py", config, state, cache):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test\n")
        return command, app, config, state, cache

    def test_default_uninstall_preserves_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command, app, config, state, cache = self._seed_install(root)
            with patch.dict("os.environ", self._environment(root), clear=False):
                with patch("cyber_wall.uninstall.stop_picker"), patch(
                    "cyber_wall.uninstall.stop_wallpaper"
                ):
                    self.assertEqual(main([]), 0)
            self.assertFalse(command.exists())
            self.assertFalse(app.exists())
            self.assertTrue(config.exists())
            self.assertTrue(state.exists())
            self.assertTrue(cache.exists())

    def test_purge_requires_confirmation_and_removes_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command, app, config, state, cache = self._seed_install(root)
            with patch.dict("os.environ", self._environment(root), clear=False):
                with patch("builtins.input", return_value="cyber-wall"):
                    with patch("cyber_wall.uninstall.stop_picker"), patch(
                        "cyber_wall.uninstall.stop_wallpaper"
                    ):
                        self.assertEqual(main(["--purge"]), 0)
            self.assertFalse(command.exists())
            self.assertFalse(app.exists())
            self.assertFalse(config.parent.exists())
            self.assertFalse(state.parent.exists())
            self.assertFalse(cache.parent.exists())


if __name__ == "__main__":
    unittest.main()
