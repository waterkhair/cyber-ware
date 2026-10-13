import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wave import cli


class ToggleTests(unittest.TestCase):
    @patch("cyber_wave.cli._clients", return_value=[])
    @patch("cyber_wave.cli._control", return_value=True)
    @patch("cyber_wave.cli.subprocess.Popen")
    def test_running_picker_is_toggled_through_app_control(self, popen, control, clients):
        self.assertEqual(cli.toggle(), 0)
        control.assert_called_once_with("toggle")
        popen.assert_not_called()
        clients.assert_not_called()

    @patch("cyber_wave.cli._clients", return_value=[{
        "class": cli.CLASS,
        "address": "0x1234",
    }])
    @patch("cyber_wave.cli._control", return_value=False)
    def test_old_picker_without_control_socket_fails_safely(self, control, clients):
        with self.assertRaisesRegex(RuntimeError, "close it with Ctrl\\+Super\\+X"):
            cli.toggle()

    @patch("cyber_wave.cli._control", side_effect=[False, True])
    @patch("cyber_wave.cli._clients", return_value=[])
    @patch("cyber_wave.cli.subprocess.Popen")
    def test_first_launch_waits_for_control_socket(self, popen, clients, control):
        with patch("cyber_wave.cli.paths") as paths:
            paths.return_value = {
                "command": Path("/tmp/test-bin/cyber-wave"),
                "data": Path("/tmp/test-data/cyber-wave"),
            }
            self.assertEqual(cli.toggle(), 0)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(popen.call_args.args[0], ["/tmp/test-bin/cyber-wave", "--ui"])
        control.assert_any_call("ping")

    @patch("cyber_wave.cli.subprocess.run")
    def test_close_dispatch_targets_selected_window(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        self.assertTrue(cli._dispatch("closewindow", "address:0x1234"))
        self.assertIn("window.close", run.call_args.args[0][2])


if __name__ == "__main__":
    unittest.main()
