"""Base profile ownership, restoration, theme changes, and config validation."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'desktop/manage.py'
spec = importlib.util.spec_from_file_location('desktop', SOURCE)
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = self.root / 'config'
        self.state = self.root / 'state'
        env = patch.dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.config),
                         XDG_STATE_HOME=str(self.state), GSETTINGS_BACKEND='memory')
        env.start()
        self.addCleanup(env.stop)

    def test_install_reinstall_theme_uninstall_restores_original(self):
        original = self.config / 'ghostty/config'
        original.parent.mkdir(parents=True)
        original.write_text('font-size = 15\n')
        original.chmod(0o640)
        desktop.manage('install')
        desktop.manage('install')
        desktop.manage('theme', 'greenline')
        self.assertIn('background = #080d09', original.read_text())
        desktop.manage('uninstall')
        self.assertEqual(original.read_text(), 'font-size = 15\n')
        self.assertEqual(original.stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.config / 'yazi/yazi.toml').exists())
        self.assertFalse((self.state / 'cyber-ware/desktop.json').exists())

    def test_edited_files_and_personal_functions_survive(self):
        personal = self.config / 'fish/functions/personal.fish'
        personal.parent.mkdir(parents=True)
        personal.write_text('function personal; end\n')
        desktop.manage('install')
        target = self.config / 'fish/config.fish'
        target.write_text('# my edited settings\n')
        desktop.manage('theme', 'husky')
        desktop.manage('uninstall')
        self.assertEqual(target.read_text(), '# my edited settings\n')
        self.assertEqual(personal.read_text(), 'function personal; end\n')
        self.assertTrue((self.config / 'cyber-ware/desktop/manage.py').is_file())

    def test_symlink_is_refused_before_any_config_is_written(self):
        self.config.mkdir()
        unrelated = self.root / 'unrelated'
        unrelated.mkdir()
        (self.config / 'qt6ct').symlink_to(unrelated)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            desktop.manage('install')
        self.assertFalse((self.config / 'ghostty').exists())
        self.assertEqual(list(unrelated.iterdir()), [])

    def test_failed_publication_restores_previous_files(self):
        original = self.config / 'ghostty/config'
        original.parent.mkdir(parents=True)
        original.write_text('font-size = 17\n')
        atomic = desktop.atomic
        count = 0
        def fail_once(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('injected write failure')
            return atomic(*args, **kwargs)
        with patch.object(desktop, 'atomic', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                desktop.manage('install')
        self.assertEqual(original.read_text(), 'font-size = 17\n')
        self.assertFalse((self.config / 'ghostty/config.ghostty').exists())
        self.assertFalse((self.state / 'cyber-ware/desktop.json').exists())

    def test_generated_configs_and_installed_helper(self):
        desktop.manage('install', 'husky')
        tomllib.loads((self.config / 'yazi/yazi.toml').read_text())
        for path in self.config.glob('fish/**/*.fish'):
            if shutil.which('fish'):
                subprocess.run(['fish', '--no-execute', str(path)], check=True)
        if shutil.which('ghostty'):
            subprocess.run(['ghostty', '+validate-config'], check=True,
                           capture_output=True, text=True)
        helper = self.config / 'cyber-ware/desktop/manage.py'
        subprocess.run(['python3', str(helper), 'theme', 'greenline'], check=True,
                       capture_output=True)
        self.assertIn('#080d09', (self.config / 'ghostty/config').read_text())
        for content in desktop.render('synthwave').values():
            self.assertNotIn(b'/home/waterkhair', content)
        self.assertNotIn('waylandvk', (self.config / 'yazi/yazi.toml').read_text())

    def test_interface_settings_keep_original_and_user_edits(self):
        values = {key: "'original'" for key in ('color-scheme', 'gtk-theme', 'icon-theme',
                                               'cursor-theme', 'cursor-size', 'font-name')}
        def get(args, **kwargs):
            return values[args[-1]] + '\n'
        def set_value(args, **kwargs):
            values[args[-2]] = args[-1]
        with patch.object(desktop.subprocess, 'check_output', side_effect=get), \
             patch.object(desktop.subprocess, 'run', side_effect=set_value), \
             patch.object(desktop.shutil, 'which', return_value='/usr/bin/gsettings'):
            desktop.settings()
            desktop.settings()
            values['cursor-theme'] = "'personal'"
            desktop.settings(remove=True)
        self.assertEqual(values['color-scheme'], "'original'")
        self.assertEqual(values['cursor-theme'], "'personal'")
