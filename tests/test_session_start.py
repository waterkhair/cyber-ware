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
        local_hook = options.pop('LOCAL_HOOK', False)
        temp = tempfile.TemporaryDirectory(prefix='cyber-ware-session-test-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        for name in ('hyprctl', 'systemctl', 'dbus-update-activation-environment',
                     'busctl', 'sleep'):
            p = bin_dir / name
            p.write_text(MOCK)
            p.chmod(0o755)
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(str(root / 'wayland-test'))
        config_dir = root / 'config/hypr'
        config_dir.mkdir(parents=True)
        if local_hook:
            hook = config_dir / 'hyprland.local-session-start.sh'
            hook.write_text('#!/bin/sh\nprintf "local-session-hook\\n" >> "$MOCK_ROOT/events"\n')
            hook.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + ':/usr/bin:/bin', MOCK_ROOT=str(root),
                   XDG_RUNTIME_DIR=str(root), WAYLAND_DISPLAY='wayland-test',
                   XDG_STATE_HOME=str(root / 'state'), PAM_KWALLET5_LOGIN='',
                   XDG_CONFIG_HOME=str(root / 'config'),
                   HYPRLAND_INSTANCE_SIGNATURE='isolated-test', **options)
        result = subprocess.run(['sh', str(SOURCE)], env=env, capture_output=True,
                                text=True, timeout=10)
        if local_hook and not options:
            for _ in range(100):
                if 'local-session-hook' in (root / 'events').read_text().splitlines():
                    break
                time.sleep(0.01)
        return result, (root / 'events').read_text().splitlines()

    def test_wait_recover_and_run_local_hook_in_order(self):
        result, events = self.run_helper(LOCAL_HOOK=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(events.count('hyprctl monitors -j'), 2)
        self.assertEqual(sum(e.startswith('busctl ') for e in events), 3)
        imported = next(i for i, e in enumerate(events) if e.startswith('dbus-update'))
        reset = next(i for i, e in enumerate(events) if 'reset-failed' in e)
        frontend = events.index('systemctl --user restart xdg-desktop-portal.service')
        self.assertLess(imported, reset)
        self.assertGreater(events.index('local-session-hook'), frontend)

    def test_backend_failure_prevents_local_hook(self):
        result, events = self.run_helper(LOCAL_HOOK=True, FAIL_BACKEND='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(e.startswith('busctl ') for e in events), 3)
        self.assertNotIn('local-session-hook', events)

    def test_frontend_failure_retries_and_prevents_app_launch(self):
        result, events = self.run_helper(LOCAL_HOOK=True, FAIL_FRONTEND='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum('reset-failed' in e for e in events), 3)
        self.assertEqual(sum('Introspect' in e for e in events), 20)
        self.assertNotIn('local-session-hook', events)

if __name__ == '__main__':
    unittest.main()
