import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_wave import player


class PlayerTests(unittest.TestCase):
    station = {"name": "Test", "url": "https://radio.example/stream.mp3"}

    @patch("cyber_wave.player._request")
    def test_same_selected_station_stops_playback(self, request):
        with patch("cyber_wave.player.status", return_value={"url": self.station["url"], "paused": False}):
            player.toggle_selected(self.station)
        request.assert_called_once_with(["stop"])

    @patch("cyber_wave.player.play")
    def test_different_selected_station_starts_playback(self, play):
        with patch("cyber_wave.player.status", return_value={"url": "https://radio.example/other", "paused": False}):
            player.toggle_selected(self.station)
        play.assert_called_once_with(self.station)

    @patch("cyber_wave.player._request")
    def test_playing_same_station_resumes_if_paused(self, request):
        with patch("cyber_wave.player.status", return_value={"url": self.station["url"], "paused": True}):
            player.play(self.station)
        request.assert_called_once_with(["set_property", "pause", False])

    @patch("cyber_wave.player._request", return_value={})
    @patch("cyber_wave.player.subprocess.Popen")
    @patch("cyber_wave.player.Path.unlink")
    @patch("cyber_wave.player._socket_path", return_value=Path("/tmp/cyber-wave-test.sock"))
    @patch("cyber_wave.player._mpris_script", return_value=Path("/etc/mpv/scripts/mpris.so"))
    @patch("cyber_wave.player.shutil.which", return_value="/usr/bin/mpv")
    def test_start_explicitly_loads_installed_mpris_plugin(
        self, _which, mpris_script, _socket_path, _unlink, popen, request
    ):
        player._start()
        args = popen.call_args.args[0]
        self.assertIn("--script=/etc/mpv/scripts/mpris.so", args)
        mpris_script.assert_called_once_with()
        request.assert_called_once_with(["get_property", "idle-active"], wait=3)


if __name__ == "__main__":
    unittest.main()
