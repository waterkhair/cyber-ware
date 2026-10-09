"""Exercise package selection and transactions with fake pacman/sudo only."""
import fcntl
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import termios
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = '''#!/usr/bin/python3
import os, sys
from pathlib import Path
root = Path(os.environ['PACKAGE_TEST_ROOT'])
args = sys.argv[1:]
with (root / 'calls').open('a') as f:
    f.write(Path(sys.argv[0]).name + ' ' + ' '.join(args) + '\\n')
if Path(sys.argv[0]).name == 'sudo':
    os.execv(str(root / 'bin/pacman'), args)
installed = root / 'installed'
if args[0] == '-Q':
    sys.exit(0 if os.environ.get('ALL_INSTALLED') or args[1] in installed.read_text().split() else 1)
if args[0] == '-Si':
    sys.exit(1 if args[1] == os.environ.get('UNAVAILABLE') else 0)
if args[0] == '-S':
    if os.environ.get('FAIL_INSTALL'): sys.exit(1)
    installed.write_text(' '.join(args[args.index('--') + 1:]))
    sys.exit(0)
sys.exit(2)
'''


class PackageTests(unittest.TestCase):
    def run_packages(self, components='', tty=True, **options):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            (root / 'installed').write_text('')
            (root / 'calls').touch()
            for name in ('sudo', 'pacman'):
                target = root / 'bin' / name
                target.write_text(MOCK)
                target.chmod(0o755)
            env = dict(os.environ, PACKAGE_TEST_ROOT=str(root),
                       PATH=str(root / 'bin') + ':/usr/bin:/bin',
                       selected_components=components, CYBER_WARE_INSTALL_PACKAGES='1', **options)
            script = '. "$1/packages/arch.sh"; . "$1/packages/install.sh"; cw_install_packages'
            master, slave = pty.openpty()
            try:
                def session():
                    os.setsid()
                    if tty:
                        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
                result = subprocess.run(['sh', '-c', script, 'test', str(ROOT)], env=env,
                                        stdin=slave if tty else subprocess.DEVNULL,
                                        capture_output=True, text=True, preexec_fn=session,
                                        pass_fds=(slave,), timeout=15)
            finally:
                os.close(master)
                os.close(slave)
            return result, (root / 'calls').read_text().splitlines(), (root / 'installed').read_text().split()

    def test_base_only_does_not_install_component_tools(self):
        result, calls, packages = self.run_packages()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('hyprland', packages)
        self.assertIn('ghostty', packages)
        for name in ('fish', 'yazi', 'nautilus', 'mpv', 'gtk4', 'qt5ct', 'qt6ct',
                     'adw-gtk-theme', 'breeze-icons', 'breeze-cursors'):
            self.assertIn(name, packages)
        self.assertNotIn('dolphin', packages)
        self.assertNotIn('mpvpaper', packages)
        self.assertNotIn('waybar', packages)
        self.assertEqual(sum(c.startswith('sudo ') for c in calls), 1)

    def test_selected_components_are_combined_and_deduplicated(self):
        result, calls, packages = self.run_packages('cyber-wall cyber-wave cyber-deck')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('mpvpaper', 'ffmpeg', 'mpv-mpris', 'gtk4', 'cliphist', 'wl-clipboard'):
            self.assertIn(name, packages)
        self.assertEqual(packages.count('python'), 1)
        self.assertEqual(packages.count('fuzzel'), 1)
        self.assertNotIn('wlogout', packages)
        self.assertFalse(any('-Sy' in c or '--noconfirm' in c for c in calls))

    def test_already_installed_needs_no_sudo_or_terminal(self):
        result, calls, _ = self.run_packages(tty=False, ALL_INSTALLED='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c.startswith('sudo ') for c in calls))

    def test_unavailable_package_prevents_entire_transaction(self):
        result, calls, packages = self.run_packages('cyber-jackout', UNAVAILABLE='wlogout')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('wlogout', result.stderr)
        self.assertFalse(any(c.startswith('sudo ') for c in calls))
        self.assertEqual(packages, [])

    def test_failed_transaction_aborts(self):
        result, _, packages = self.run_packages(FAIL_INSTALL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no desktop files changed', result.stderr)
        self.assertEqual(packages, [])

    def test_umbrella_package_failure_preserves_existing_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            pacman = root / 'bin/pacman'
            pacman.write_text('#!/bin/sh\nexit 1\n')
            pacman.chmod(0o755)
            main = root / 'config/hypr/hyprland.lua'
            main.parent.mkdir(parents=True)
            main.write_text('-- original working configuration\n')
            env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / 'config'),
                       XDG_STATE_HOME=str(root / 'state'), PREFIX=str(root / 'prefix'),
                       HYPRLAND_INSTANCE_SIGNATURE='', CYBER_WARE_INSTALL_PACKAGES='1',
                       PATH=str(root / 'bin') + ':/usr/bin:/bin')
            result = subprocess.run(['sh', str(ROOT / 'install.sh'), '--no-components'],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unavailable in configured repositories', result.stderr)
            self.assertEqual(main.read_text(), '-- original working configuration\n')
            self.assertFalse((root / 'state').exists())
            self.assertFalse((root / 'prefix').exists())
            self.assertEqual(list(main.parent.iterdir()), [main])

    def test_no_terminal_cannot_install_missing_packages(self):
        result, calls, _ = self.run_packages(tty=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c.startswith('sudo ') for c in calls))

    def test_all_components_include_their_default_tools(self):
        result, _, packages = self.run_packages(
            'cyber-wall cyber-signal cyber-console cyber-panel cyber-jackout cyber-scan cyber-deck cyber-wave')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('hypridle', 'hyprlock', 'wlogout', 'mako', 'networkmanager',
                     'pacman-contrib', 'impala', 'wiremix', 'bluetui', 'btop',
                     'yazi', 'waybar', 'playerctl', 'grim', 'slurp', 'swappy'):
            self.assertIn(name, packages)

    def test_profile_enables_only_the_selected_integration_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('cyber-deck', 'cyber-jackout', 'cyber-signal'):
                target = root / name
                target.write_text('#!/bin/sh\nprintf "%s %s\\n" "${0##*/}" "$*"\nexit "${MOCK_EXIT:-0}"\n')
                target.chmod(0o755)
            for component, expected in (
                ('cyber-deck', 'cyber-deck --clipboard enable'),
                ('cyber-jackout', 'cyber-jackout --enable-idle'),
                ('cyber-signal', 'cyber-signal --enable'),
                ('cyber-wall', ''),
            ):
                result = subprocess.run(
                    ['sh', '-c', '. "$1/packages/install.sh"; cw_enable_component "$2"',
                     'test', str(ROOT), component],
                    env=dict(os.environ, command_dir=str(root)), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), expected)
            result = subprocess.run(
                ['sh', '-c', '. "$1/packages/install.sh"; cw_enable_component cyber-jackout',
                 'test', str(ROOT)], env=dict(os.environ, command_dir=str(root), MOCK_EXIT='1'),
                capture_output=True)
            self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
