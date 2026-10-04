"""Isolated installer and command regression tests; no desktop interaction."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cyber_deck import cli, installer

SOURCE = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cyber-deck-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.mocks = self.root / "mocks"
        self.mocks.mkdir()
        self.executable("fuzzel", "#!/bin/sh\nexit 0\n")
        self.environment = patch.dict(os.environ, {
            "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / "config"),
            "XDG_DATA_HOME": str(self.home / "data"), "PREFIX": str(self.home / "custom prefix"),
            "PATH": str(self.mocks) + ":/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("CYBER_DECK_HOME", None)
        self.app = self.home / "data/cyber-deck"
        self.config = self.home / "config/cyber-deck"
        self.command = self.home / "custom prefix/bin/cyber-deck"

    def executable(self, name, content):
        path = self.mocks / name
        path.write_text(content)
        path.chmod(0o755)

    def install(self):
        with redirect_stdout(io.StringIO()):
            installer.install(SOURCE)

    def command_run(self, *args, env=None):
        return subprocess.run([str(self.command), *args], env=env, text=True,
                              capture_output=True, timeout=10)

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob("*") if p.is_file()}

    def test_custom_prefix_uninstall_without_prefix_environment(self):
        self.install()
        env = dict(os.environ)
        env.pop("PREFIX")
        result = self.command_run("--uninstall", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.command.exists())
        self.assertFalse(self.app.exists())
        self.assertTrue((self.config / "theme").exists())

    def test_copy_failure_preserves_working_installation(self):
        self.install()
        before = self.snapshot()
        with patch.object(installer.shutil, "copytree", side_effect=OSError("injected copy failure")):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.command_run("--help").returncode, 0)

    def test_publication_failure_restores_all_previous_files(self):
        self.install()
        before = self.snapshot()
        replace = os.replace

        def fail_command(source, destination):
            if Path(source).name == "new" and destination == self.command:
                raise OSError("injected command publication failure")
            return replace(source, destination)

        with patch.object(installer.os, "replace", side_effect=fail_command):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.command_run("--help").returncode, 0)

    def test_invalid_theme_aborts_before_publication(self):
        self.install()
        before = self.snapshot()
        self.executable("fuzzel", "#!/bin/sh\nexit 2\n")
        with self.assertRaises(subprocess.CalledProcessError):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_toggle_closes_only_identified_launcher(self):
        self.install()
        with patch.object(cli, "_deck_pids", return_value=[12345]), \
             patch.object(cli.os, "kill") as kill, patch.object(cli.os, "execv") as execute:
            self.assertEqual(cli._toggle(), 0)
        kill.assert_called_once_with(12345, signal.SIGTERM)
        execute.assert_not_called()

    def test_toggle_opens_selected_theme(self):
        self.install()
        self.assertEqual(self.command_run("--theme", "greenline").returncode, 0)
        with patch.object(cli, "_deck_pids", return_value=[]), \
             patch.object(cli.os, "execv") as execute:
            self.assertEqual(cli._toggle(), 0)
        execute.assert_called_once_with(str(self.mocks / "fuzzel"),
            [str(self.mocks / "fuzzel"), f"--config={self.config / 'themes/greenline.ini'}"])

    def test_clipboard_enable_preserves_other_settings_and_checks_requirements(self):
        settings = self.config / "config.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"custom": "kept"}\n')
        with patch.object(cli.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            self.assertEqual(cli._set_clipboard(True), 0)
        self.assertEqual(json.loads(settings.read_text()), {"custom": "kept", "clipboard_enabled": True})
        with patch.object(cli.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "clipboard history requires"):
                cli._set_clipboard(True)

    def test_uninstall_disables_clipboard_collection_but_preserves_theme_settings(self):
        self.install()
        (self.config / "config.json").write_text('{"clipboard_enabled": true}\n')
        with patch.object(cli, "_deck_pids", return_value=[]), \
             patch.object(cli, "_stop_clipboard_watcher") as stop_watcher:
            self.assertEqual(cli._uninstall(False), 0)
        stop_watcher.assert_called_once()
        self.assertFalse(json.loads((self.config / "config.json").read_text())["clipboard_enabled"])
        self.assertTrue((self.config / "theme").is_file())

    def test_clipboard_picker_decodes_selected_image_without_shell(self):
        self.install()
        (self.config / "theme").write_text("greenline\n")
        selected = b"41\t[image/png] ; touch /tmp/should-not-exist\n"
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            if args[-1:] == ["list"]:
                return SimpleNamespace(returncode=0, stdout=selected, stderr=b"")
            if args[0].endswith("fuzzel"):
                return SimpleNamespace(returncode=0, stdout=selected, stderr=b"")
            if args[-1:] == ["decode"]:
                self.assertEqual(kwargs["input"], selected)
                return SimpleNamespace(returncode=0, stdout=b"\x89PNG\r\n", stderr=b"")
            self.assertEqual(args, ["/usr/bin/wl-copy", "--type", "image/png"])
            self.assertEqual(kwargs["input"], b"\x89PNG\r\n")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

        with patch.object(cli, "clipboard_is_enabled", return_value=True), \
             patch.object(cli.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"), \
             patch.object(cli.subprocess, "run", side_effect=run):
            self.assertEqual(cli._clipboard(), 0)
        self.assertTrue(all("shell" not in kwargs for _, kwargs in calls))
        self.assertEqual(calls[1][0][-1], f"--config={self.config / 'themes/greenline.ini'}")

    def test_process_detection_excludes_unrelated_fuzzel(self):
        self.install()
        proc = self.root / "proc"
        proc.mkdir()
        commands = {
            10: ["fuzzel", f"--config={self.config / 'themes/synthwave.ini'}"],
            11: ["/usr/bin/fuzzel", "--config", str(self.config / 'themes/greenline.ini')],
            12: ["fuzzel", "--dmenu"],
            13: ["fuzzel", "--config=/unrelated/menu.ini"],
        }
        for pid, args in commands.items():
            directory = proc / str(pid)
            directory.mkdir()
            (directory / "cmdline").write_bytes(b"\0".join(arg.encode() for arg in args) + b"\0")
        with patch.object(cli, "Path", side_effect=lambda path: proc if path == "/proc" else Path(path)):
            self.assertEqual(sorted(cli._deck_pids()), [10, 11])

    def test_first_install_inherits_shared_theme_upgrade_keeps_override(self):
        shared = self.home / "config/cyber-ware"
        shared.mkdir(parents=True)
        (shared / "theme").write_text("greenline\n")
        self.install()
        self.assertEqual((self.config / "theme").read_text(), "greenline\n")
        self.assertEqual(self.command_run("--theme", "synthwave").returncode, 0)
        theme_file = self.config / "themes/synthwave.ini"
        theme_file.write_text(theme_file.read_text() + "\n# custom theme\n")
        self.install()
        self.assertEqual((self.config / "theme").read_text(), "synthwave\n")
        self.assertIn("# custom theme", theme_file.read_text())

    def test_unowned_command_and_symlink_are_preserved(self):
        self.command.parent.mkdir(parents=True)
        external = self.root / "external"
        external.write_text("user file")
        self.command.symlink_to(external)
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(external.read_text(), "user file")
        self.command.unlink()
        self.command.write_text("user command")
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(self.command.read_text(), "user command")

    def test_uninstall_refuses_replaced_command(self):
        self.install()
        self.command.write_text("unrelated user command")
        # Invoke the module directly because the command has been replaced.
        env = {**os.environ, "PYTHONPATH": str(self.app / "src")}
        result = subprocess.run(["python3", "-m", "cyber_deck.cli", "--uninstall"],
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.app.exists())
        self.assertEqual(self.command.read_text(), "unrelated user command")

    def test_stream_install_downloads_pinned_source_and_cleans_temporary_files(self):
        archive = self.root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(SOURCE, arcname="cyber-ware-test/cyber-deck")
        revision = "a" * 40
        self.executable("curl", f'''#!/usr/bin/python3
import json, shutil, sys
from pathlib import Path
args = sys.argv[1:]
if "https://api.github.com/repos/WaterKhair/cyber-ware/commits/main" in args:
    print(json.dumps({{"sha": {revision!r}}}))
else:
    assert "https://github.com/WaterKhair/cyber-ware/archive/{revision}.tar.gz" in args
    shutil.copyfile({str(archive)!r}, args[args.index("-o") + 1])
''')
        stale = self.root / "stale"
        (stale / "src/cyber_deck").mkdir(parents=True)
        (stale / "src/cyber_deck/cli.py").write_text("raise RuntimeError('stale checkout')")
        downloads = self.root / "downloads"
        downloads.mkdir()
        env = {**os.environ, "TMPDIR": str(downloads)}
        result = subprocess.run(["sh"], input=(SOURCE / "install.sh").read_text(),
                                cwd=stale, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(revision, result.stdout)
        self.assertEqual(list(downloads.iterdir()), [])
        self.assertEqual(self.command_run("--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
