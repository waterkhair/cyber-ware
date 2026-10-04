"""Exercise lock installation without contacting the desktop or locking."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

COMMAND = Path(__file__).resolve().parents[1] / 'cyber-jackout/bin/cyber-jackout'


class LockIncludeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='cyber-lock-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = self.root / 'custom-config/hypr'
        self.config.mkdir(parents=True)
        self.state = self.root / 'state/cyber-jackout'
        self.state.mkdir(parents=True)
        (self.state / 'installed').touch()
        self.include = self.config / 'hyprlock-wallpaper.conf'
        self.lock = self.config / 'hyprlock.conf'
        mocks = self.root / 'bin'
        mocks.mkdir()
        for name in ('hypridle', 'hyprlock', 'hyprctl', 'loginctl'):
            path = mocks / name
            path.write_text('#!/bin/sh\nexit 99\n')
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root),
                        XDG_CONFIG_HOME=str(self.config.parent),
                        XDG_STATE_HOME=str(self.state.parent),
                        HYPRLAND_INSTANCE_SIGNATURE='',
                        PATH=str(mocks) + ':/usr/bin:/bin')

    def run_command(self, *args):
        return subprocess.run(['bash', str(COMMAND), *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_install_custom_config_directory(self):
        result = self.run_command('--enable-idle')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'source = {self.include}', self.lock.read_text())
        self.assertTrue(self.include.is_file())

    def test_theme_upgrade_creates_missing_include(self):
        self.lock.write_text('background {\n    color = black\n}\n')
        (self.state / 'idle-enabled').touch()
        (self.state / 'hyprlock.sha256').write_text(hashlib.sha256(self.lock.read_bytes()).hexdigest())
        result = self.run_command('--theme', 'synthwave')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.include.is_file())
        self.assertIn(f'source = {self.include}', self.lock.read_text())

    def test_dangling_symlink_is_refused_before_installing_configs(self):
        target = self.root / 'unrelated'
        self.include.symlink_to(target)
        result = self.run_command('--enable-idle')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse(self.lock.exists())
        self.assertFalse((self.config / 'hypridle.conf').exists())

    def test_existing_include_preserved(self):
        self.include.write_text('$CYBER_WALLPAPER = /custom/image.png\n')
        before = self.include.read_bytes()
        result = self.run_command('--enable-idle')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.include.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
