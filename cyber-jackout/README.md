# cyber-jackout

`cyber-jackout` safely logs out of Hyprland or requests a reboot/poweroff. It
preserves the current cleanup behavior: stop the user's `mpvpaper` process
without touching ordinary mpv windows, stop portal services before compositor
teardown, restore previously active portals if the action is rejected, and
coordinate reboot/shutdown through a transient systemd user service and a
logind delay inhibitor.

It is one user-local command with no resident daemon and no root installer.
Its two wlogout styles match the companion `cyber-panel` and `cyber-wall`
palettes: `synthwave` and `greenline`.
The `greenline` theme bundles green SVG versions of the wlogout icons so their
glyphs match the phosphor-green palette instead of retaining the system icon
set's lavender color. `synthwave` continues to use the stock wlogout icons.

## Requirements

Runtime requirements:

- Bash, `flock`, `hyprctl`, `logger`, `notify-send`, `pgrep`, `systemctl`,
  `systemd-inhibit`, `systemd-run`, and `timeout`
- An active Hyprland session launched with the Lua configuration API used by
  `hl.dispatch(hl.dsp.exit())`
- A systemd user manager and logind
- `librsvg` (`rsvg-convert`) when using the `greenline` theme so GTK can render
  its bundled SVG icons

Optional integration:

- `cyber-wall` restores the selected wallpaper if a logout/power request fails
  after wallpaper cleanup has started. Without it, cleanup still works, but a
  failed action cannot restore the wallpaper automatically.

The installer checks its tools before changing files and does not install
system packages. Run `cyber-jackout --check` in the target Hyprland session to
check runtime requirements and the optional `cyber-wall` integration.

## Install

Install from the public `main` branch:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-jackout/install.sh | sh
```

This downloads and runs the component installer. To inspect it first:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-jackout
./install.sh
```

The command is installed in `~/.local/bin/cyber-jackout`; program files are
stored in `~/.local/share/cyber-jackout`. Set `PREFIX` or `XDG_DATA_HOME` to
use alternate user-local locations. Ensure `~/.local/bin` is on `PATH`.
Re-running the installer upgrades only a recognized cyber-jackout installation.
It refuses to overwrite unrelated command or data files.

The installer applies the selected theme to `~/.config/wlogout/style.css`
(default: `synthwave`). Before replacing an existing stylesheet, it saves the
original in `~/.local/state/cyber-jackout/backups/` for uninstall recovery.
It does not edit Hyprland bindings or the wlogout layout.

## Usage

```sh
cyber-jackout              # cleanly log out
cyber-jackout logout       # cleanly log out
cyber-jackout reboot       # clean up, request reboot, then exit Hyprland
cyber-jackout poweroff     # clean up, request shutdown, then exit Hyprland
cyber-jackout --check      # check runtime commands and optional cyber-wall
cyber-jackout --theme      # show the selected theme
cyber-jackout --theme greenline
cyber-jackout --theme synthwave
cyber-jackout --uninstall  # remove cyber-jackout files
cyber-jackout --uninstall --purge  # also remove its saved settings/recovery copies
```

The power worker logs under the `session-power` journal identifier. The
cleanup helper logs under `cyber-jackout` and `session-power`:

```sh
journalctl --user -t session-power
journalctl --user -t cyber-jackout
```

## Hyprland and wlogout integration

The installer manages the wlogout stylesheet but leaves the compositor and
power-menu layout to you. Point the logout, reboot, and shutdown entries in
your wlogout layout at:

```text
cyber-jackout
cyber-jackout reboot
cyber-jackout poweroff
```

For a direct Hyprland logout binding, invoke `cyber-jackout` (or
`cyber-jackout logout`). Keep `wlogout` itself and its lock/suspend actions
separate; this component only handles logout, reboot, and poweroff.

## Uninstall

```sh
cyber-jackout --uninstall
```

Uninstall restores the previous wlogout stylesheet, when one existed, and
removes the command and program directory. If you edited the managed stylesheet,
cyber-jackout preserves that edited copy under
`~/.local/state/cyber-jackout/before-uninstall/` before restoring the original.
Hyprland bindings and wlogout layout references are not removed. Settings and
recovery copies are retained unless `--purge` is explicitly confirmed.

## License

MIT; see [`../LICENSE`](../LICENSE).
