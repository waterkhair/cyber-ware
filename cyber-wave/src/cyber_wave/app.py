"""GTK4 internet radio picker and station manager."""

from __future__ import annotations

import gi
from pathlib import Path

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from .config import current_theme, save_config, validate_station
from .player import status, toggle_selected


def key_action(keyval: int, state: Gdk.ModifierType) -> str | None:
    ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
    if ctrl and keyval == Gdk.KEY_j:
        return "down"
    if ctrl and keyval == Gdk.KEY_k:
        return "up"
    if ctrl and keyval == Gdk.KEY_a:
        return "add"
    if ctrl and keyval == Gdk.KEY_d:
        return "delete"
    if ctrl and keyval == Gdk.KEY_space:
        return "toggle"
    if ctrl and keyval == Gdk.KEY_u:
        return "clear-search"
    if keyval == Gdk.KEY_Down and not ctrl:
        return "down"
    if keyval == Gdk.KEY_Up and not ctrl:
        return "up"
    if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
        return "toggle"
    if keyval == Gdk.KEY_Escape:
        return "escape"
    return None


def filter_stations(stations: list[dict], query: str) -> list[int]:
    needle = query.casefold().strip()
    return [
        index
        for index, station in enumerate(stations)
        if needle in station["name"].casefold() or needle in station["url"].casefold()
    ]


def display_player_state(actual: dict, pending: dict | None, now: float, pending_since: float) -> tuple[dict, dict | None]:
    if pending is None:
        return actual, None
    if actual == pending:
        return actual, None
    if now - pending_since <= 5.0:
        return pending, pending
    return actual, None


class CyberWavePicker(Gtk.Application):
    def __init__(self, config: dict) -> None:
        super().__init__(
            application_id="org.cyber-ware.cyber-wave",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config = config
        self.stations = config["stations"]
        self.window: Gtk.ApplicationWindow | None = None
        self.search: Gtk.SearchEntry | None = None
        self.listbox: Gtk.ListBox | None = None
        self.rows: list[Gtk.ListBoxRow] = []
        self.form_box: Gtk.Box | None = None
        self.name_entry: Gtk.Entry | None = None
        self.url_entry: Gtk.Entry | None = None
        self.notice: Gtk.Label | None = None
        self.player_source: int | None = None
        self.pending_state: dict | None = None
        self.pending_since = 0.0
        self.player_state = {"url": None, "paused": False}

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        self._load_css()
        self._build_window()
        self.window.present()
        self._refresh_player_state()
        self.player_source = GLib.timeout_add(500, self._refresh_player_state)

    def _load_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        theme = current_theme()
        stylesheet = Path(__file__).with_name("themes") / f"{theme}.css"
        if not stylesheet.is_file():
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(stylesheet.read_text(encoding="utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_window(self) -> None:
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("cyber-wave")
        self.window.set_name("cyber-wave")
        self.window.set_default_size(850, 590)
        self.window.set_resizable(True)
        self.window.set_decorated(False)
        self.window.connect("close-request", self._close_request)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key_pressed)
        self.window.add_controller(keys)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        shell.set_name("shell")
        self.window.set_child(shell)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="CYBER-WAVE  /  INTERNET RADIO")
        title.set_name("title")
        title.set_xalign(0)
        header.append(title)
        shell.append(header)

        self.search = Gtk.SearchEntry()
        self.search.set_name("search")
        self.search.set_placeholder_text("Filter stations by name or URL…")
        self.search.connect("search-changed", self._filter_changed)
        shell.append(self.search)

        self.form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.form_box.set_name("station-form")
        self.form_box.set_visible(False)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("Station name")
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("Stream URL (HTTP/S)")
        self.name_entry.connect("activate", lambda *_: self.url_entry.grab_focus())
        self.url_entry.connect("activate", lambda *_: self._save_station())
        self.form_box.append(self.name_entry)
        self.form_box.append(self.url_entry)
        form_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_button = Gtk.Button(label="Add station")
        save_button.add_css_class("accent")
        save_button.connect("clicked", lambda *_: self._save_station())
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda *_: self._close_form())
        form_actions.append(save_button)
        form_actions.append(cancel_button)
        self.form_box.append(form_actions)
        shell.append(self.form_box)

        self.listbox = Gtk.ListBox()
        self.listbox.set_name("stations")
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(False)
        self.listbox.connect("row-selected", self._row_selected)
        self.listbox.connect("row-activated", self._row_activated)
        for station in self.stations:
            self._append_station(station)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_name("station-scroll")
        scrolled.set_vexpand(True)
        scrolled.set_child(self.listbox)
        shell.append(scrolled)

        self.notice = Gtk.Label(label="")
        self.notice.set_name("notice")
        self.notice.set_xalign(0)
        shell.append(self.notice)

        hint = Gtk.Label(
            label="Ctrl+K/J move   •   Enter/Ctrl+Space play/stop   •   Ctrl+A add   •   Ctrl+D delete   •   Esc close"
        )
        hint.set_name("hint")
        hint.set_xalign(0)
        shell.append(hint)

        if self.rows:
            self.listbox.select_row(self.rows[0])
        self.search.grab_focus()

    def _append_station(self, station: dict) -> None:
        assert self.listbox is not None
        row = Gtk.ListBoxRow()
        row.station = station  # type: ignore[attr-defined]
        row.set_activatable(True)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        marker = Gtk.Label(label="·")
        marker.set_name("play-marker")
        marker.set_width_chars(2)
        row.marker = marker  # type: ignore[attr-defined]
        line.append(marker)
        name = Gtk.Label(label=station["name"])
        name.set_name("station-name")
        name.set_xalign(0)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        line.append(name)
        state = Gtk.Label(label="")
        state.set_name("station-state")
        row.state_label = state  # type: ignore[attr-defined]
        line.append(state)
        row.set_child(line)
        row.add_css_class("station-row")
        self.listbox.append(row)
        self.rows.append(row)

    def _key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        action = key_action(keyval, state)
        if self.form_box is not None and self.form_box.get_visible():
            if action == "escape":
                self._close_form()
                return True
            return False
        if action == "down":
            self._move_selection(1)
            return True
        if action == "up":
            self._move_selection(-1)
            return True
        if action == "add":
            self._open_form()
            return True
        if action == "delete":
            self._delete_selected()
            return True
        if action == "toggle":
            self._toggle_selected()
            return True
        if action == "clear-search" and self.search is not None:
            self.search.set_text("")
            return True
        if action == "escape":
            self.quit()
            return True
        return False

    def _visible_rows(self) -> list[Gtk.ListBoxRow]:
        return [row for row in self.rows if row.get_visible()]

    def _move_selection(self, delta: int) -> None:
        assert self.listbox is not None
        visible = self._visible_rows()
        if not visible:
            return
        selected = self.listbox.get_selected_row()
        try:
            index = visible.index(selected)
        except ValueError:
            index = 0 if delta > 0 else len(visible) - 1
        target = visible[max(0, min(len(visible) - 1, index + delta))]
        self.listbox.select_row(target)
        target.grab_focus()
        if self.search is not None:
            self.search.grab_focus()

    def _filter_changed(self, _entry) -> None:
        assert self.search is not None and self.listbox is not None
        query = self.search.get_text().casefold().strip()
        for row in self.rows:
            station = row.station  # type: ignore[attr-defined]
            row.set_visible(
                not query
                or query in station["name"].casefold()
                or query in station["url"].casefold()
            )
        visible = self._visible_rows()
        if visible and self.listbox.get_selected_row() not in visible:
            self.listbox.select_row(visible[0])

    def _row_selected(self, _listbox, row) -> None:
        if row is not None and self.search is not None:
            self.search.grab_focus()

    def _row_activated(self, _listbox, _row) -> None:
        self._toggle_selected()

    def _selected_station(self) -> dict | None:
        if self.listbox is None:
            return None
        row = self.listbox.get_selected_row()
        return row.station if row is not None else None  # type: ignore[attr-defined]

    def _toggle_selected(self) -> None:
        station = self._selected_station()
        if station is None:
            return
        before = status()
        try:
            toggle_selected(station)
        except RuntimeError as error:
            self._set_notice(str(error))
            return
        if before["url"] == station["url"] and not before["paused"]:
            self.pending_state = {"url": None, "paused": False}
        else:
            self.pending_state = {"url": station["url"], "paused": False}
        self.pending_since = GLib.get_monotonic_time() / 1_000_000
        self._refresh_player_state()
        self._set_notice("")

    def _refresh_player_state(self) -> bool:
        actual, self.pending_state = display_player_state(
            status(), self.pending_state, GLib.get_monotonic_time() / 1_000_000, self.pending_since
        )
        self.player_state = actual
        for row in self.rows:
            station = row.station  # type: ignore[attr-defined]
            playing = actual["url"] == station["url"]
            marker = row.marker  # type: ignore[attr-defined]
            state_label = row.state_label  # type: ignore[attr-defined]
            marker.set_text("Ⅱ" if playing and actual["paused"] else "▶" if playing else "·")
            state_label.set_text("PAUSED" if playing and actual["paused"] else "PLAYING" if playing else "")
            if playing:
                row.add_css_class("playing")
            else:
                row.remove_css_class("playing")
        return GLib.SOURCE_CONTINUE

    def _open_form(self) -> None:
        assert self.form_box is not None and self.name_entry is not None and self.url_entry is not None
        self.name_entry.set_text("")
        self.url_entry.set_text("")
        self.form_box.set_visible(True)
        self.name_entry.grab_focus()
        self._set_notice("Enter a name, then press Enter and enter the stream URL.")

    def _close_form(self) -> None:
        assert self.form_box is not None and self.search is not None
        self.form_box.set_visible(False)
        self.search.grab_focus()
        self._set_notice("")

    def _save_station(self) -> None:
        assert self.name_entry is not None and self.url_entry is not None
        station = {"name": self.name_entry.get_text(), "url": self.url_entry.get_text()}
        try:
            station = validate_station(station)
            if any(existing["url"] == station["url"] for existing in self.stations):
                raise ValueError("That stream URL is already in the list.")
            self.stations.append(station)
            save_config(self.config)
        except (OSError, ValueError) as error:
            if station in self.stations:
                self.stations.remove(station)
            self._set_notice(str(error))
            return
        assert self.search is not None
        self.search.set_text("")
        self._append_station(station)
        self._close_form()
        assert self.listbox is not None
        self.listbox.select_row(self.rows[-1])
        self._set_notice(f"Added {station['name']}")

    def _delete_selected(self) -> None:
        station = self._selected_station()
        if station is None:
            self._set_notice("There is no selected station to delete.")
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Delete {station['name']}?",
        )
        dialog.set_secondary_text("This removes the station from your cyber-wave list.")
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Delete", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self._delete_response, station)
        dialog.present()

    def _delete_response(self, dialog, response, station) -> None:
        dialog.destroy()
        if response != Gtk.ResponseType.ACCEPT:
            return
        index = self.stations.index(station)
        row = self.rows[index]
        self.stations.pop(index)
        try:
            save_config(self.config)
        except (OSError, ValueError) as error:
            self.stations.insert(index, station)
            self._set_notice(str(error))
            return
        self.listbox.remove(row)
        self.rows.remove(row)
        visible = self._visible_rows()
        if visible:
            self.listbox.select_row(visible[min(index, len(visible) - 1)])
        self._set_notice(f"Removed {station['name']}")

    def _set_notice(self, message: str) -> None:
        if self.notice is not None:
            self.notice.set_text(message)

    def _close_request(self, *_args) -> bool:
        self.quit()
        return False

    def do_shutdown(self) -> None:
        if self.player_source is not None:
            GLib.source_remove(self.player_source)
            self.player_source = None
        Gtk.Application.do_shutdown(self)


def run(config: dict) -> int:
    app = CyberWavePicker(config)
    return app.run(None)
