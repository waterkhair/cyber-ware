"""Execute session startup with fake desktop commands; never touch live services."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'hyprland/session-start.sh'
MOCK = '''#!/usr/bin/python3
import os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
root = Path(os.environ['MOCK_ROOT'])
with (root / 'events').open('a') as f:
    f.write(name + ' ' + ' '.join(sys.argv[1:]) + '\\n')
if name == 'hyprctl':
    p = root / 'ready'
    if not p.exists():
        p.touch()
        sys.exit(1)
if name == 'busctl':
    if 'Introspect' in sys.argv:
        if not os.environ.get('FAIL_FRONTEND'):
            print('org.freedesktop.portal.ScreenCast org.freedesktop.portal.Screenshot')
        sys.exit(0)
    p = root / 'backend-ready'
    if not p.exists() or os.environ.get('FAIL_BACKEND'):
        p.touch()
        sys.exit(1)
if name == 'pgrep':
    sys.exit(0 if os.environ.get('APPS_RUNNING') else 1)
'''

class SessionStartTests(unittest.TestCase):
    def run_helper(self, **options):
        temp = tempfile.TemporaryDirectory(prefix='cyber-ware-session-test-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        for name in ('hyprctl', 'systemctl', 'dbus-update-activation-environment',
                     'busctl', 'pgrep', 'opendeck', 'discord', 'steam', 'sleep'):
            p = bin_dir / name
            p.write_text(MOCK)
            p.chmod(0o755)
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(str(root / 'wayland-test'))
        env = dict(os.environ, PATH=str(bin_dir) + ':/usr/bin:/bin', MOCK_ROOT=str(root),
                   XDG_RUNTIME_DIR=str(root), WAYLAND_DISPLAY='wayland-test',
                   XDG_STATE_HOME=str(root / 'state'), PAM_KWALLET5_LOGIN='',
                   HYPRLAND_INSTANCE_SIGNATURE='isolated-test', **options)
        result = subprocess.run(['sh', str(SOURCE)], env=env, capture_output=True,
                                text=True, timeout=10)
        if not options:
            for _ in range(100):
                if all(n in (root / 'events').read_text().splitlines()
                       for n in ('opendeck --hide', 'discord ', 'steam ')):
                    break
                time.sleep(0.01)
        return result, (root / 'events').read_text().splitlines()

    def test_wait_recover_and_launch_in_order(self):
        result, events = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(events.count('hyprctl monitors -j'), 2)
        self.assertEqual(sum(e.startswith('busctl ') for e in events), 3)
        imported = next(i for i, e in enumerate(events) if e.startswith('dbus-update'))
        reset = next(i for i, e in enumerate(events) if 'reset-failed' in e)
        frontend = events.index('systemctl --user restart xdg-desktop-portal.service')
        self.assertLess(imported, reset)
        for app in ('opendeck --hide', 'discord ', 'steam '):
            self.assertGreater(events.index(app), frontend)

    def test_existing_apps_are_checked_after_portals(self):
        result, events = self.run_helper(APPS_RUNNING='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        frontend = events.index('systemctl --user restart xdg-desktop-portal.service')
        self.assertTrue(all(i > frontend for i, e in enumerate(events) if e.startswith('pgrep ')))
        self.assertFalse(any(e in events for e in ('opendeck --hide', 'discord ', 'steam ')))

    def test_backend_failure_prevents_app_launch(self):
        result, events = self.run_helper(FAIL_BACKEND='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(e.startswith('busctl ') for e in events), 3)
        self.assertFalse(any(e.startswith('pgrep ') for e in events))

    def test_frontend_failure_retries_and_prevents_app_launch(self):
        result, events = self.run_helper(FAIL_FRONTEND='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum('reset-failed' in e for e in events), 3)
        self.assertEqual(sum('Introspect' in e for e in events), 20)
        self.assertFalse(any(e.startswith('pgrep ') for e in events))

if __name__ == '__main__':
    unittest.main()
