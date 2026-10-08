import unittest

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from cyber_wave.app import display_player_state, filter_stations, hide_picker, key_action


class AppTests(unittest.TestCase):
    def test_filter_matches_name_and_url(self):
        stations = [
            {"name": "Esoterica Dark", "url": "https://one.example/stream"},
            {"name": "Ambient", "url": "https://two.example/dark"},
        ]
        self.assertEqual(filter_stations(stations, "DARK"), [0, 1])
        self.assertEqual(filter_stations(stations, ""), [0, 1])
        self.assertEqual(filter_stations(stations, "missing"), [])

    def test_ctrl_j_and_ctrl_k_are_distinct_navigation_actions(self):
        ctrl = Gdk.ModifierType.CONTROL_MASK
        self.assertEqual(key_action(Gdk.KEY_j, ctrl), "down")
        self.assertEqual(key_action(Gdk.KEY_k, ctrl), "up")

    def test_enter_is_distinct_from_ctrl_j(self):
        ctrl = Gdk.ModifierType.CONTROL_MASK
        plain = Gdk.ModifierType(0)
        self.assertEqual(key_action(Gdk.KEY_Return, plain), "toggle")
        self.assertEqual(key_action(Gdk.KEY_j, ctrl), "down")
        self.assertNotEqual(key_action(Gdk.KEY_j, ctrl), key_action(Gdk.KEY_Return, plain))

    def test_other_keyboard_actions(self):
        ctrl = Gdk.ModifierType.CONTROL_MASK
        plain = Gdk.ModifierType(0)
        self.assertEqual(key_action(Gdk.KEY_space, ctrl), "toggle")
        self.assertEqual(key_action(Gdk.KEY_a, ctrl), "add")
        self.assertEqual(key_action(Gdk.KEY_d, ctrl), "delete")
        self.assertEqual(key_action(Gdk.KEY_Escape, plain), "escape")
        self.assertEqual(key_action(Gdk.KEY_Down, plain), "down")
        self.assertEqual(key_action(Gdk.KEY_Up, plain), "up")

    def test_escape_hide_uses_the_same_radio_workspace_toggle_as_shortcut(self):
        from unittest.mock import patch

        with patch("cyber_wave.cli._dispatch", return_value=True) as dispatch:
            self.assertTrue(hide_picker())
        dispatch.assert_called_once_with("togglespecialworkspace", "Radio")

    def test_pending_selection_displays_immediately_and_clears_on_confirmation(self):
        desired = {"url": "https://radio.example/second", "paused": False}
        stale = {"url": "https://radio.example/first", "paused": False}
        shown, pending = display_player_state(stale, desired, 15.0, 10.0)
        self.assertEqual(shown, desired)
        self.assertEqual(pending, desired)
        shown, pending = display_player_state(desired, desired, 15.1, 10.0)
        self.assertEqual(shown, desired)
        self.assertIsNone(pending)

    def test_pending_state_expires_if_player_never_catches_up(self):
        actual = {"url": "https://radio.example/first", "paused": False}
        pending = {"url": "https://radio.example/second", "paused": False}
        shown, next_pending = display_player_state(actual, pending, 16.0, 10.0)
        self.assertEqual(shown, actual)
        self.assertIsNone(next_pending)


if __name__ == "__main__":
    unittest.main()
