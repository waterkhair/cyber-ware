# cyber-ware

`cyber-ware` is the umbrella repository for this Hyprland setup: its
configuration, setup documentation, and optional installable tools. Each
standalone tool lives in its own top-level directory, with its own code,
dependencies, installer, and usage instructions. Users can install only the
components they want.

## Components

- [`cyber-wall/`](cyber-wall/README.md) — GTK image/video wallpaper picker for
  Hyprland, using `mpvpaper`.
- [`cyber-signal/`](cyber-signal/README.md) — user-scoped system status
  notifications with Mako themes and optional systemd user timers.
- [`cyber-panel/`](cyber-panel/README.md) — a themed Waybar setup for Hyprland,
  with synthwave and greenline styles.
- [`cyber-console/`](cyber-console/README.md) — one command to toggle floating
  Ghostty windows for terminal tools such as Impala, Wiremix, Bluetui, btop,
  and Yazi.
- [`cyber-jackout/`](cyber-jackout/README.md) — clean Hyprland logout, reboot,
  and shutdown with wallpaper/portal cleanup and matching synthwave/greenline
  wlogout themes.
- [`cyber-scan/`](cyber-scan/README.md) — Wayland region screenshots through
  grim, slurp, and swappy.
- [`cyber-deck/`](cyber-deck/README.md) — themed Fuzzel application launcher
  with a Super+Space toggle command.
- [`hyprland/`](hyprland/README.md) — modular Lua configuration and setup
  guidance for integrating the cyber-ware components.

Keep personal secrets, machine-specific state, and unreviewed configuration
out of the public repository. Hardware-specific settings belong in a local
`hyprland.local.lua` file rather than the shared modules.

## Install the cyber-ware setup

The top-level installer always installs the modular Hyprland configuration,
then asks whether to install each optional cyber-ware component. It checks the
selected components' required commands before changing the active desktop and
does not use sudo or install operating-system packages. It requires Hyprland
0.55 or newer for the Lua config API and checks that version before touching
active files. A piped install resolves and records the exact Git revision
downloaded; running `./install.sh` uses the checked-out tree.

For installation in a running desktop, the installer probes that session's
Lua API directly. A legacy `hyprland.conf` session is refused before active
files change, even if a `hyprland.lua` file already exists on disk. Log out and
install from a TTY, or migrate the running session to Lua first. From a TTY,
compatibility is checked with `Hyprland --version` without requiring IPC.
A legacy `.conf` file is preserved, but its settings are not automatically
translated; put any required machine settings in `hyprland.local.lua` before
starting the new configuration.

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/install.sh | sh
```

To review the repository first, clone it and run `./install.sh`. Use
`./install.sh --no-components` to install only the Hyprland config, or
`./install.sh --all` to install every component without prompts. The config
installer preserves an existing entry point and module folder under
`$XDG_STATE_HOME/cyber-ware/backups/`; it leaves an existing
`hyprland.local.lua` untouched and migrates old `environment.lua`/`monitors.lua`
modules into it when possible.
Details and machine-specific setup are in [`hyprland/README.md`](hyprland/README.md).
The shared command is installed to `~/.local/bin/cyber-ware` by default; ensure
`~/.local/bin` is on `PATH`.
After installing selected components, the installer reloads an active
Hyprland session. Its reload handler starts missing configured services,
refreshes existing Waybar/Mako instances, and restores a saved wallpaper
without duplicating running processes. If run from a TTY, those actions begin
on the next Hyprland login. The transaction stages Lua modules first and
restores the prior config if publication or active config validation fails.
Automatic reload is paused through the Lua API during publication, and its
previous setting is restored. Each installation has a unique entry-point token;
the installer checks it after reload so an unrelated `--config` file cannot
produce a false success.

The installed command directory is recorded for Hyprland and Waybar, so a
custom `PREFIX` works for desktop actions even when the graphical session does
not inherit that directory in `PATH`. To use commands interactively, add that
directory to your shell path (for fish, for example: `fish_add_path ~/.local/bin`).

The installer also provides one shared theme command:

```sh
cyber-ware --theme                 # show the selected theme
cyber-ware --theme greenline       # switch the desktop to greenline
cyber-ware --theme synthwave       # switch the desktop to synthwave
```

The shared theme is saved in `~/.config/cyber-ware/theme` (or under
`$XDG_CONFIG_HOME`). Hyprland reads it for active/inactive window and group
borders. The command also updates installed `cyber-wall`, `cyber-signal`,
`cyber-panel`, `cyber-jackout`, and `cyber-deck`, then reloads Hyprland.
Missing components are skipped; components installed later inherit the saved
theme. `synthwave` is the default when no shared selection exists.

To remove only the umbrella Hyprland config and `cyber-ware` command:

```sh
cyber-ware --uninstall
```

Uninstall requires typing `cyber-ware` to confirm. It restores the original
Hyprland entry point and module directory, preserves a recovery copy of the
current files, and leaves optional components, the shared theme preference,
and backups in place. Remove optional components separately with their own
`--uninstall` commands.

## Installing one component

Each component documents its own install and uninstall steps. For example,
`cyber-wall` can be installed by running its script from this repository:

```sh
./cyber-wall/install.sh
```

Each component README also documents a convenient one-command installer for
that component when you want to install it separately.

For Waybar, `cyber-panel` replaces the default user config and stylesheet after
preserving the existing copies, then provides `synthwave` and `greenline`
themes. Its standalone install, dependency, and recovery details are in the
[`cyber-panel` README](cyber-panel/README.md).

`cyber-console` provides a single configurable command for toggling floating
Ghostty TUI windows. Its installer leaves compositor bindings and window rules
to the user; integration examples are in the
[`cyber-console` README](cyber-console/README.md).

`cyber-deck` toggles the Fuzzel application launcher and provides synthwave and
greenline themes. Its standalone installer does not edit Hyprland bindings;
the bundled cyber-ware configuration binds Super+Space when the component is
installed.

## Repository setup

GitHub credentials and the first push workflow are documented in
[`docs/git-setup.md`](docs/git-setup.md). Initialize Git at this repository
root—not inside a component—so future setup files and tools belong to the same
parent repository.
