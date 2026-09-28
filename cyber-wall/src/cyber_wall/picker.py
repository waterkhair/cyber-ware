#!/usr/bin/python3
"""Cyberpunk image/video wallpaper picker with a live preview."""

from __future__ import annotations

import hashlib
import signal
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from .config import cache_dir, expand_path, load_config

CONFIG = load_config()
WALLPAPER_DIRS = tuple(expand_path(path) for path in CONFIG["directories"])
STATE_DIR = cache_dir()
THUMBNAIL_DIR = STATE_DIR / "thumbnails"
THEME_CSS = Path(__file__).with_name("themes") / f"{CONFIG['theme']}.css"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


def discover_wallpapers() -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for directory in WALLPAPER_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                continue
            items.append(
                {
                    "path": path,
                    "name": path.name,
                    "is_video": suffix in VIDEO_EXTENSIONS,
                }
            )
    return sorted(items, key=lambda item: str(item["name"]).casefold())


class WallpaperPicker(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="org.cyber-ware.cyber-wall",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window: Gtk.ApplicationWindow | None = None
        self.items: list[dict[str, object]] = []
        self.rows: list[Gtk.ListBoxRow] = []
        self.current_item: dict[str, object] | None = None
        self.picture: Gtk.Picture | None = None
        self.video_badge: Gtk.Label | None = None
        self.search: Gtk.SearchEntry | None = None
        self.listbox: Gtk.ListBox | None = None
        self.preview_process = None
        self.preview_source = None
        self.preview_temporary = None

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return

        self.items = discover_wallpapers()
        if not self.items:
            self.quit()
            return

        self._load_css()
        self._build_window()
        self.window.present()

    def _load_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(THEME_CSS.read_bytes())
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_window(self) -> None:
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("cyber-wall")
        self.window.set_default_size(1100, 820)
        self.window.set_resizable(True)
        self.window.set_decorated(False)
        self.window.connect("close-request", self._close_request)

        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._key_pressed)
        self.window.add_controller(key_controller)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        shell.set_name("shell")
        self.window.set_child(shell)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label="PREVIEW")
        title.set_name("title")
        title.set_xalign(0)
        heading.append(title)
        heading.append(Gtk.Label())
        shell.append(heading)

        preview_frame = Gtk.Frame()
        preview_frame.set_name("preview-frame")
        preview_overlay = Gtk.Overlay()
        preview_frame.set_child(preview_overlay)
        self.picture = Gtk.Picture()
        self.picture.set_name("preview")
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_size_request(-1, 405)
        self.picture.set_hexpand(True)
        preview_overlay.set_child(self.picture)
        self.video_badge = Gtk.Label(label="IMAGE")
        self.video_badge.set_name("media-badge")
        self.video_badge.add_css_class("image-badge")
        self.video_badge.set_halign(Gtk.Align.END)
        self.video_badge.set_valign(Gtk.Align.START)
        self.video_badge.set_visible(False)
        preview_overlay.add_overlay(self.video_badge)
        shell.append(preview_frame)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Filter wallpapers…")
        self.search.connect("search-changed", self._filter_changed)
        shell.append(self.search)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(False)
        self.listbox.connect("row-selected", self._row_selected)
        self.listbox.connect("row-activated", self._row_activated)
        for item in self.items:
            self._append_row(item)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(185)
        scrolled.set_vexpand(True)
        scrolled.set_child(self.listbox)
        shell.append(scrolled)

        hint = Gtk.Label(label="Enter select   •   Esc cancel   •   Ctrl+J/K or arrows navigate")
        hint.set_name("hint")
        hint.set_xalign(0)
        shell.append(hint)

        self.listbox.select_row(self.rows[0])
        self.search.grab_focus()

    def _append_row(self, item: dict[str, object]) -> None:
        assert self.listbox is not None
        row = Gtk.ListBoxRow()
        row.item = item  # type: ignore[attr-defined]
        row.set_activatable(True)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        badge = Gtk.Label(label="VIDEO" if item["is_video"] else "IMAGE")
        badge.add_css_class("badge-video" if item["is_video"] else "badge")
        badge.set_xalign(0)
        content.append(badge)
        label = Gtk.Label(label=str(item["name"]))
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_hexpand(True)
        content.append(label)
        row.set_child(content)
        self.listbox.append(row)
        self.rows.append(row)

    def _key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval == Gdk.KEY_j:
            self._move_selection(1)
            return True
        if ctrl and keyval == Gdk.KEY_k:
            self._move_selection(-1)
            return True
        if keyval == Gdk.KEY_Down and not ctrl:
            self._move_selection(1)
            return True
        if keyval == Gdk.KEY_Up and not ctrl:
            self._move_selection(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._apply_selected()
            return True
        if keyval == Gdk.KEY_Escape:
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
            current_index = visible.index(selected)
        except ValueError:
            current_index = 0 if delta > 0 else len(visible) - 1
        target = visible[max(0, min(len(visible) - 1, current_index + delta))]
        self.listbox.select_row(target)
        # Briefly focus the row so GTK's ListBox/ScrolledWindow keeps it
        # visible, then return keyboard focus to the search entry.
        target.grab_focus()
        if self.search is not None:
            self.search.grab_focus()

    def _filter_changed(self, _entry) -> None:
        assert self.search is not None and self.listbox is not None
        query = self.search.get_text().casefold().strip()
        for row in self.rows:
            item = row.item  # type: ignore[attr-defined]
            row.set_visible(not query or query in str(item["name"]).casefold())
        visible = self._visible_rows()
        if visible:
            selected = self.listbox.get_selected_row()
            if selected not in visible:
                self.listbox.select_row(visible[0])
        else:
            self.current_item = None
            self._set_preview(None)

    def _row_selected(self, _listbox, row) -> None:
        if row is None:
            return
        self._set_preview(row.item)  # type: ignore[attr-defined]
        if self.search is not None:
            self.search.grab_focus()

    def _row_activated(self, _listbox, row) -> None:
        self._apply_item(row.item)  # type: ignore[attr-defined]

    def _cancel_preview(self) -> None:
        if self.preview_source is not None:
            GLib.source_remove(self.preview_source)
            self.preview_source = None
        process = self.preview_process
        self.preview_process = None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
        if self.preview_temporary is not None:
            self.preview_temporary.unlink(missing_ok=True)
            self.preview_temporary = None

    def do_shutdown(self) -> None:
        self._cancel_preview()
        Gtk.Application.do_shutdown(self)

    def _show_texture(self, path: Path) -> None:
        try:
            self.picture.set_paintable(Gdk.Texture.new_from_filename(str(path)))
        except GLib.Error:
            self.picture.set_paintable(None)

    def _request_thumbnail(self, path: Path) -> None:
        try:
            stamp = f"{path}:{path.stat().st_mtime_ns}:{path.stat().st_size}".encode()
        except OSError:
            return None
        thumbnail = THUMBNAIL_DIR / (hashlib.sha256(stamp).hexdigest()[:20] + ".jpg")
        if thumbnail.is_file():
            self._show_texture(thumbnail)
            return
        THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    str(CONFIG["preview_seek_seconds"]),
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=960:-2",
                    str(thumbnail.with_suffix('.pending.jpg')),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        self.preview_process = process
        started = time.monotonic()
        temporary = thumbnail.with_suffix('.pending.jpg')
        self.preview_temporary = temporary

        def poll() -> bool:
            status = process.poll()
            if status is None and time.monotonic() - started < float(CONFIG["preview_timeout_seconds"]):
                return GLib.SOURCE_CONTINUE
            self.preview_source = None
            self.preview_process = None
            self.preview_temporary = None
            if status is None:
                process.kill()
                process.wait()
            elif status == 0 and temporary.is_file():
                temporary.replace(thumbnail)
                self._show_texture(thumbnail)
            temporary.unlink(missing_ok=True)
            return GLib.SOURCE_REMOVE

        self.preview_source = GLib.timeout_add(50, poll)

    def _set_preview(self, item: dict[str, object] | None) -> None:
        self._cancel_preview()
        if self.picture is None:
            return
        self.current_item = item
        if item is None:
            self.picture.set_paintable(None)
            if self.video_badge is not None:
                self.video_badge.set_visible(False)
            return

        path = Path(item["path"])
        self.picture.set_paintable(None)
        if item["is_video"]:
            self._request_thumbnail(path)
        else:
            self._show_texture(path)
        if self.video_badge is not None:
            is_video = bool(item["is_video"])
            self.video_badge.set_text("VIDEO" if is_video else "IMAGE")
            if is_video:
                self.video_badge.remove_css_class("image-badge")
            else:
                self.video_badge.add_css_class("image-badge")
            self.video_badge.set_visible(True)

    def _apply_selected(self) -> None:
        assert self.listbox is not None
        row = self.listbox.get_selected_row()
        if row is not None:
            self._apply_item(row.item)  # type: ignore[attr-defined]

    def _apply_item(self, item: dict[str, object]) -> None:
        path = Path(item["path"])
        subprocess.Popen(
            [sys.executable, "-m", "cyber_wall.cli", "--set", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.quit()

    def _close_request(self, *_args) -> bool:
        self.quit()
        return False

if __name__ == "__main__":
    app = WallpaperPicker()

    def terminate_picker() -> bool:
        app.quit()
        return GLib.SOURCE_REMOVE

    # The keyboard toggle sends SIGTERM; run normal GTK shutdown so any
    # in-flight thumbnail process is reaped and its partial file removed.
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, terminate_picker)
    app.run(None)
