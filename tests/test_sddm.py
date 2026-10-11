import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cyber_ware_sddm", ROOT / "sddm" / "install.py")
SDDM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDDM)


class SddmTests(unittest.TestCase):
    def test_updates_theme_without_changing_other_sddm_settings_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sddm.conf"
            original = "[General]\nDisplayServer=x11\n\n[Theme]\nCurrent=old-theme\n\n[Wayland]\nCompositorCommand=example\n"
            config.write_text(original)

            self.assertTrue(SDDM.configure_default(config))
            updated = config.read_text()
            self.assertIn("DisplayServer=x11", updated)
            self.assertIn("Current=monochrome", updated)
            self.assertIn("CompositorCommand=example", updated)
            self.assertEqual(config.with_name("sddm.conf.cyber-ware-backup").read_text(), original)
            self.assertFalse(SDDM.configure_default(config))
            self.assertEqual(config.with_name("sddm.conf.cyber-ware-backup").read_text(), original)

    def test_creates_theme_config_when_none_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sddm.conf"
            self.assertTrue(SDDM.configure_default(config))
            self.assertIn("[Theme]\n", config.read_text())
            self.assertIn("Current=monochrome", config.read_text())

    def test_does_not_modify_already_selected_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sddm.conf"
            original = "[Theme]\nCurrent=monochrome\n"
            config.write_text(original)
            self.assertFalse(SDDM.configure_default(config))
            self.assertEqual(config.read_text(), original)
            self.assertFalse(config.with_name("sddm.conf.cyber-ware-backup").exists())

    def test_installs_upstream_theme_and_preserves_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "upstream" / "sddm" / "themes" / "monochrome"
            source.mkdir(parents=True)
            (source / "metadata.desktop").write_text("Theme-Id=monochrome\n")
            (source / "theme.conf").write_text(
                '[General]\nCustomBackground="false"\nBackground="backgrounds/wallpaper.jpg"\n'
            )
            target = Path(directory) / "themes" / "monochrome"
            self.assertTrue(SDDM.install_theme(source, target))
            self.assertTrue((target / "theme.conf").is_file())
            (target / "user-file").write_text("preserve")
            self.assertFalse(SDDM.install_theme(source, target))
            self.assertEqual((target / "user-file").read_text(), "preserve")

    def test_custom_wallpaper_is_enabled_and_theme_config_backup_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "monochrome"
            theme.mkdir()
            config = theme / "theme.conf"
            original = '[General]\nCustomBackground="false"\nBackground="backgrounds/wallpaper.jpg"\n'
            config.write_text(original)
            wallpaper = Path(directory) / "wallpaper.png"
            wallpaper.write_bytes(b"test wallpaper asset")

            self.assertTrue(SDDM.configure_wallpaper(theme, wallpaper))
            self.assertEqual((theme / "wallpaper.png").read_bytes(), wallpaper.read_bytes())
            updated = config.read_text()
            self.assertIn('CustomBackground="true"', updated)
            self.assertIn('Background="wallpaper.png"', updated)
            self.assertEqual(config.with_name("theme.conf.cyber-ware-backup").read_text(), original)
            self.assertTrue(SDDM.configure_wallpaper(theme, wallpaper))


if __name__ == "__main__":
    unittest.main()
