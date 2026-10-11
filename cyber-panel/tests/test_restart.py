import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cyber_panel import cli


class RestartTests(unittest.TestCase):
    def make_process(self, root):
        entry = root / "123"
        entry.mkdir()
        (entry / "cmdline").write_bytes(b"waybar\0-c\0/tmp/custom config.jsonc\0")
        (entry / "environ").write_bytes(b"WAYLAND_DISPLAY=wayland-1\0CUSTOM=value=with=equals\0")
        (entry / "exe").symlink_to("/usr/bin/true")
        (entry / "cwd").symlink_to(root)
        return entry

    def test_restart_waits_and_preserves_arguments_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = self.make_process(root)
            with patch.object(cli.os, "pidfd_open", return_value=42), \
                 patch.object(cli.os, "close") as close, \
                 patch.object(cli.signal, "pidfd_send_signal") as send, \
                 patch.object(cli.select, "select", side_effect=[([], [], []), ([42], [], [])]) as wait, \
                 patch.object(cli.subprocess, "Popen") as spawn:
                events = Mock()
                events.attach_mock(send, "send")
                events.attach_mock(wait, "wait")
                events.attach_mock(spawn, "spawn")
                log = object()
                cli._restart_process(entry, log)
                send.assert_called_once_with(42, signal.SIGTERM)
                self.assertEqual([call[0] for call in events.mock_calls], ["wait", "send", "wait", "spawn"])
                spawn.assert_called_once_with(
                    ["waybar", "-c", "/tmp/custom config.jsonc"], executable="/usr/bin/true",
                    cwd=str(root), env={"WAYLAND_DISPLAY": "wayland-1", "CUSTOM": "value=with=equals"},
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    start_new_session=True, close_fds=True)
                close.assert_called_once_with(42)

    def test_slow_exit_does_not_create_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = self.make_process(Path(directory))
            with patch.object(cli.os, "pidfd_open", return_value=42), \
                 patch.object(cli.os, "close"), \
                 patch.object(cli.signal, "pidfd_send_signal"), \
                 patch.object(cli.select, "select", return_value=([], [], [])), \
                 patch.object(cli.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(RuntimeError, "no duplicate"):
                    cli._restart_process(entry, None)
                spawn.assert_not_called()

    def test_theme_refresh_does_not_start_stopped_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli, "paths", return_value={"state": Path(directory)}), \
                 patch.object(cli, "_running_waybars", return_value=[]), \
                 patch.object(cli.subprocess, "Popen") as spawn:
                cli.restart_waybar()
                spawn.assert_not_called()

    def test_start_missing_bar_once(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli, "paths", return_value={"state": Path(directory)}), \
                 patch.object(cli, "_running_waybars", return_value=[]), \
                 patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}), \
                 patch.object(cli.shutil, "which", return_value="/usr/bin/waybar"), \
                 patch.object(cli.time, "sleep"), \
                 patch.object(cli.subprocess, "Popen") as spawn:
                spawn.return_value.poll.return_value = None
                cli.restart_waybar(start_if_missing=True)
                spawn.assert_called_once()
                self.assertEqual(spawn.call_args.args, (["/usr/bin/waybar"],))

    def test_tty_theme_does_not_touch_other_graphical_sessions(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cli, "_running_waybars") as discover:
            cli.restart_waybar()
            discover.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "graphical session"):
                cli.restart_waybar(start_if_missing=True)


if __name__ == "__main__":
    unittest.main()
