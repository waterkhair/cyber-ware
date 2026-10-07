import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wave import cli


class ToggleTests(unittest.TestCase):
    @patch("cyber_wave.cli._dispatch", return_value=True)
    @patch("cyber_wave.cli._clients", return_value=[{
        "class": cli.CLASS,
        "workspace": {"name": "special:Radio"},
        "floating": True,
        "visible": True,
    }])
    def test_existing_window_is_toggled_not_closed_or_relaunched(self, clients, dispatch):
        with patch("cyber_wave.cli.subprocess.Popen") as popen:
            self.assertEqual(cli.toggle(), 0)
        dispatch.assert_called_once_with("togglespecialworkspace", "Radio")
        popen.assert_not_called()

    @patch("cyber_wave.cli._focus_picker", return_value=True)
    @patch("cyber_wave.cli._dispatch", return_value=True)
    @patch("cyber_wave.cli._clients", return_value=[{
        "class": cli.CLASS,
        "address": "0x1234",
        "workspace": {"name": "special:Radio"},
        "floating": True,
        "visible": False,
    }])
    def test_showing_existing_picker_restores_keyboard_focus(self, clients, dispatch, focus):
        self.assertEqual(cli.toggle(), 0)
        dispatch.assert_called_once_with("togglespecialworkspace", "Radio")
        focus.assert_called_once_with(clients.return_value[0])

    @patch("cyber_wave.cli._radio_workspace_is_active", return_value=False)
    @patch("cyber_wave.cli._dispatch", return_value=True)
    @patch("cyber_wave.cli._clients", side_effect=[[], [{
        "initialClass": cli.CLASS,
        "workspace": {"name": "special:Radio"},
        "floating": True,
        "visible": False,
    }]])
    @patch("cyber_wave.cli.subprocess.Popen")
    @patch("cyber_wave.cli._focus_picker", return_value=True)
    def test_first_launch_opens_gtk_picker_then_reveals_radio_workspace(self, focus, popen, clients, dispatch, active):
        with patch("cyber_wave.cli.paths") as paths:
            paths.return_value = {
                "command": Path("/tmp/test-bin/cyber-wave"),
                "data": Path("/tmp/test-data/cyber-wave"),
            }
            self.assertEqual(cli.toggle(), 0)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(popen.call_args.args[0], ["/tmp/test-bin/cyber-wave", "--ui"])
        dispatch.assert_called_once_with("togglespecialworkspace", "Radio")
        active.assert_called_once_with()
        focus.assert_called_once()

    @patch("cyber_wave.cli.subprocess.run")
    def test_special_workspace_toggle_uses_lua_ipc(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        self.assertTrue(cli._dispatch("togglespecialworkspace", "Radio"))
        self.assertEqual(run.call_args.args[0][:2], ["hyprctl", "eval"])
        self.assertIn('toggle_special("Radio")', run.call_args.args[0][2])


if __name__ == "__main__":
    unittest.main()
