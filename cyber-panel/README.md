# cyber-panel

`cyber-panel` is a standalone Waybar configuration and theme package for
Hyprland. It provides a compact status bar with workspace pills, active-window
title, media controls, system tray, network state, volume, and clock. It ships
two styles: `synthwave` (muted violet/cyan) and `greenline` (phosphor green on
near-black).

The package only manages its own Waybar configuration and stylesheet. It does
not install system packages, edit Hyprland config, add key bindings, or start
Waybar at login. Keep your existing `waybar` startup entry; the default Waybar
config paths will use the installed files.

## Requirements

Required:

- Waybar built with the Hyprland and ext-workspace modules
- Hyprland and `hyprctl`
- Python 3

Optional, depending on the configured click actions:

- `playerctl` for MPRIS play/pause/previous/next actions
- `cyber-console` (optional companion component) for the network and volume
  pill click actions
- A Nerd Font for the icons; otherwise replace the icon glyphs or select an
  installed font in the CSS

`cyber-console` is not a standard program. Install it from this repository or
remove/replace the corresponding `on-click` values in
`~/.config/waybar/config.jsonc`. Without it, the click actions do not work, but
the bar and status modules still run normally.

The installer checks the required executables before changing files, reports
optional commands that are unavailable, and never invokes `sudo` or installs
system dependencies. Install missing packages with your distribution's package
manager first.

## Install

Quick install from the public GitHub repository:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-panel/install.sh | sh
```

This fetches the public `main` archive and installs only `cyber-panel`. As with
any `curl | sh` installer, it executes code from the repository. To inspect it
before running:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-panel
./install.sh
```

The installer places the single `cyber-panel` command in `~/.local/bin`, its
program files in `~/.local/share/cyber-panel`, theme selection in
`~/.config/cyber-panel/config.json`, and the Waybar files in
`~/.config/waybar/config.jsonc` and `~/.config/waybar/style.css`. Set `PREFIX`
to choose a different command prefix, or use the standard XDG environment
variables to change config, data, or state locations. Make sure the command
directory is on `PATH`.

Before replacing Waybar files, the installer saves any existing config and
stylesheet in `$XDG_STATE_HOME/cyber-panel/backups` (normally
`~/.local/state/cyber-panel/backups`). Re-running the installer preserves
these original copies. An existing unrelated `~/.config/cyber-panel/config.json`
is not overwritten.

## Commands

```sh
cyber-panel                         # show install and theme status
cyber-panel --theme                 # show selected and available themes
cyber-panel --theme greenline       # switch styles and reload running Waybar
cyber-panel --theme synthwave       # switch back to synthwave
cyber-panel --uninstall             # restore the original Waybar files
cyber-panel --uninstall --purge     # restore, then remove settings and recovery copies
cyber-panel --help
```

Waybar is reloaded with `SIGUSR2` after a theme switch when a running instance
is found. When Waybar is stopped, the chosen theme is used the next time it
starts. Theme names and the config key use lowercase spelling.

Uninstall preserves cyber-panel settings and recovery copies by default. The
`--purge` form requires typing `cyber-panel`; it removes those saved files only
after restoring the pre-install Waybar config and stylesheet. If you edited a
managed Waybar file after installation, that edited copy is preserved in
`$XDG_STATE_HOME/cyber-panel/before-uninstall` before the original is restored.

## Configuration and themes

The installed Waybar JSONC file is a starting point and may be edited normally.
The default layout orders the right side as `MPRIS | tray | network | volume |
clock`. Workspace buttons are ordered by workspace ID and click to activate.
Network and volume click handlers call the optional helper commands above;
volume scrolling is intentionally a no-op so scrolling over the pill does not
change volume accidentally.

The theme selector changes only the CSS, not the Waybar module layout. The
source styles are `themes/synthwave.css` and `themes/greenline.css`; installed
copies are in `~/.local/share/cyber-panel/themes/`. The live stylesheet is
`~/.config/waybar/style.css`.

## Hyprland startup

No Hyprland changes are needed if Waybar already starts with its default
configuration paths. For example, an existing startup command such as
`waybar` continues to work. This package deliberately does not edit compositor
configuration or choose a shortcut for you.

## Development

From this directory:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
sh -n install.sh
```

`cyber-panel` is distributed under the repository's MIT License; see
[`../LICENSE`](../LICENSE).
