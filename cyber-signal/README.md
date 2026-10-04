# cyber-signal

`cyber-signal` is a lightweight, user-level notification helper for Linux. It
can report NetworkManager connectivity changes, available Arch updates, and
low disk space. Notifications are delivered through `notify-send`; the
selected `synthwave` or `greenline` theme sets Mako's desktop-wide defaults,
while cyber-signal notifications receive matching app-specific emphasis.

It does not need root, install packages, edit your Mako/Hyprland configuration,
or monitor continuously except for the small network state watcher when
enabled. Update and disk checks are short-lived timer jobs.

## Quick install

Requirements: Python 3, `notify-send` (provided by `libnotify`), and a desktop
notification daemon. Network monitoring additionally needs NetworkManager's
`nmcli`; Arch update checks need `checkupdates` from `pacman-contrib`. Mako and
`makoctl` are optional, and disk checks use Python's standard library.

On Arch/CachyOS, install the required and optional utilities with your package
manager as desired, then run:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-signal/install.sh | sh
```

The one-line installer downloads the public repository archive and installs
only this component. It does not use `sudo` or install system packages. As with
any `curl | sh` installer, this runs code from the repository. To inspect it
first:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-signal
./install.sh
```

By default, the command is installed in `~/.local/bin`, application code in
`~/.local/share/cyber-signal`, configuration in
`~/.config/cyber-signal/config.json`, and user services in
`~/.config/systemd/user`. Set `PREFIX` to install the command elsewhere. The
installer does not overwrite an existing config file.

When Mako is installed, the installer adds the selected theme in a clearly
marked block at the end of `~/.config/mako/config`, then reloads Mako if it is
running. The theme sets Mako's global defaults, so ordinary `notify-send`
notifications use the selected cyber-ware colors too. More specific
app-scoped rules give cyber-signal notifications distinct critical styling.
The installer preserves settings outside its marked block. See the [Mako configuration
manual](https://github.com/emersion/mako/blob/master/doc/mako.5.scd). If Mako
is absent, cyber-signal still works, but its Mako theme cannot be applied until
Mako is installed.

## Start and use

The installer leaves monitoring disabled until you opt in. Enable the user
network watcher and update/disk timers with:

```sh
cyber-signal --enable
```

Useful commands:

```sh
cyber-signal --test                  # preview a notification
cyber-signal --status                # show config and user-unit status
cyber-signal --check network         # report current NetworkManager state
cyber-signal --check updates         # check for changed/new Arch updates
cyber-signal --check disk            # check configured mounts and alert on threshold crossings
cyber-signal --theme                 # show selected theme and Mako config path
cyber-signal --theme greenline       # select terminal phosphor-green
cyber-signal --theme synthwave       # select muted purple/pink synthwave
cyber-signal --disable               # stop and disable monitoring
cyber-signal --help
```

`--enable` runs a small network watcher (default poll interval 10 seconds) and
two timers: update checks begin after 15 minutes and repeat every 6 hours; disk
checks begin after 5 minutes and repeat every 30 minutes. Baseline state is
recorded without an immediate “recovered” notification. Repeated identical
update lists and unchanged disk severity are quiet. Notifications are
user-session scoped; they do not run while logged out. The first network poll
stores a quiet connectivity baseline; available updates and already-low disk
mounts can notify on the first timer check.

## Configuration

Edit `~/.config/cyber-signal/config.json`:

```json
{
  "theme": "synthwave",
  "network_poll_seconds": 10,
  "disk_warning_percent": 90,
  "disk_critical_percent": 95,
  "disk_mounts": ["/", "/home"],
  "update_detail_limit": 8,
  "checks": {
    "network": true,
    "updates": true,
    "disk": true
  }
}
```

Mounts that do not exist on the machine are skipped. Thresholds must satisfy
`1 <= warning < critical <= 100`. Disable individual checks under `checks`.
Network status comes from NetworkManager's connectivity state (`full` counts as
internet access). Update checks use Arch's `checkupdates`; this tool only
notifies and never installs updates.

The two Mako theme source files are in `src/cyber_signal/themes/`. Switching
with `cyber-signal --theme NAME` updates the selected theme and the managed
Mako style block, then asks Mako to reload when `makoctl` is present. This
changes the appearance of desktop notifications generally, including those
sent directly with `notify-send`; the cyber-signal critical rule remains
app-specific.

## Troubleshooting

- `notify-send` missing: install `libnotify` and ensure a notification daemon
  is running in the graphical session.
- No network events: confirm `nmcli general` reports connectivity and inspect
  `systemctl --user status cyber-signal-network.service`.
- No Arch update checks: install `pacman-contrib`, then test with
  `cyber-signal --check updates`.
- Check logs with `journalctl --user -u cyber-signal-network.service` or
  `journalctl --user -u cyber-signal-updates.service`.
- For timer details, use `systemctl --user list-timers 'cyber-signal-*'`.

## Uninstall

```sh
cyber-signal --uninstall
```

This stops and disables the component's user units, removes those unit files,
the one command, and application code. Configuration, generated Mako theme,
and state are preserved. The installer-managed Mako style block is removed,
while all other Mako settings remain. Any custom Mako rules you added outside
that block are left untouched.

To also remove cyber-signal's settings, generated theme, and saved state:

```sh
cyber-signal --uninstall --purge
```

Purge requires typing `cyber-signal` to confirm. Neither uninstall mode
changes Hyprland, other Mako settings, installed packages, or other user data.

## Development

From the component directory:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m compileall -q src tests
sh -n install.sh
```

`cyber-signal` is distributed under the repository's MIT License; see
[`../LICENSE`](../LICENSE).
