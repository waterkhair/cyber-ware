# cyber-wave

`cyber-wave` is a keyboard-driven GTK internet radio picker for Hyprland. It opens
in a dedicated floating GTK window on the `Radio` special workspace.
`Ctrl+Super+R` shows and hides that window without terminating the picker or
stopping playback. `mpv` runs independently, so playback continues while the
picker is hidden or after `Esc` closes it.

## Requirements

- Hyprland with the cyber-ware Lua configuration
- `hyprctl`
- `mpv`
- `mpv-mpris` (optional; enables media status and controls in Waybar/MPRIS clients)
- Python 3 with GTK 4 bindings (`gtk4` and `python-gobject` on CachyOS/Arch)

Install requirements with your distribution package manager first. The
installer does not use `sudo` or install packages.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-wave/install.sh | sh
```

This installs only cyber-wave under `~/.local` and does not modify Hyprland
configuration. The umbrella cyber-ware installer offers it as an optional
component and includes the binding and window rule. For an existing cyber-ware
setup, reinstall/reload cyber-ware after adding the component, or add the
integration shown below manually.

Files are installed under `~/.local/share/cyber-wave`, command under
`~/.local/bin/cyber-wave`, and station settings under
`~/.config/cyber-wave/config.json`. `PREFIX`, `XDG_DATA_HOME`, and
`XDG_CONFIG_HOME` are respected.

## Use

```sh
cyber-wave                 # show/hide the persistent picker
cyber-wave --check          # check GTK 4, Hyprland, mpv, and station config
cyber-wave --theme greenline
cyber-wave --theme synthwave
cyber-wave --theme husky
cyber-wave --uninstall
cyber-wave --uninstall --purge
```

The initial station is Esoterica Radio S3. Manage stations in the picker or
edit `~/.config/cyber-wave/config.json`; each station has a display `name` and
a direct HTTP(S) audio-stream `url`:

```json
{
  "theme": "synthwave",
  "stations": [
    {
      "name": "Esoterica Radio S3",
      "url": "https://esoterica.servemp3.com:444/listen/darkbasshouse_cyberpunk_hybridtrap/radio.mp3"
    }
  ]
}
```

| Key | Action |
| --- | --- |
| Ctrl+K / Ctrl+J | Move up/down through stations |
| Enter / Ctrl+Space | Toggle playback for the selected station (start/switch or stop) |
| Type text | Filter station names and URLs; Backspace edits, Ctrl+U clears |
| Ctrl+A | Open the add-station form (Tab changes fields, Enter advances/saves, Esc cancels) |
| Ctrl+D | Confirm and delete the selected station from your list |
| Esc | Close the picker window; playback continues, and the shortcut can open a new picker later |
| Ctrl+Super+R | Hide/show the same picker window without closing it |

The GTK picker handles Ctrl+J and Ctrl+K as native key events, separate from
Enter. The three bundled GTK stylesheets follow cyber-ware's synthwave,
greenline, and husky palettes.

The station list uses direct stream addresses, not station webpages. Streams
can change or go offline; update the URL in the config if that happens. Playback
is handled by a detached local `mpv` process controlled over a user-private
Unix socket under `$XDG_RUNTIME_DIR/cyber-wave`.

When `mpv-mpris` is installed, cyber-wave explicitly loads its plugin so the
radio appears as an MPRIS player (for example, in Waybar's MPRIS module). On
CachyOS/Arch, install it with `sudo pacman -S mpv-mpris`; restart playback
after installing it.

## Hyprland integration

The cyber-ware config automatically provides the binding and floating rule when
the command is installed. For a standalone install, the equivalent Lua binding
is:

```lua
hl.bind("CTRL + SUPER + R", hl.dsp.exec_cmd(os.getenv("HOME") .. "/.local/bin/cyber-wave"), { description = "Toggle internet radio picker" })
```

The window class is `org.cyber-ware.cyber-wave`. Send it to a silent
`special:Radio` workspace and float it; cyber-wave relies on that rule to keep
the same picker alive while hidden.

For a traditional Hyprland configuration, the equivalent rule is:

```ini
windowrule {
    name = cyber-wave-picker
    match:class = ^org\.cyber-ware\.cyber-wave$
    workspace = special:Radio silent
    float = true
    size = 1050 720
    center = true
}
```

## Themes and uninstall

`cyber-ware --theme synthwave|greenline|husky` updates cyber-wave when installed.
Direct `cyber-wave --theme NAME` changes only this component. Uninstall removes
its command and program files but keeps your station list. Add `--purge` to
remove cyber-wave configuration too; it asks for confirmation.
Uninstall also stops cyber-wave's mpv process and closes its picker window if
the Hyprland session is available. Reload Hyprland afterward to remove the
component-conditional shortcut from the active configuration.
