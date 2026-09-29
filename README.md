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
- [`hyprland/`](hyprland/README.md) — modular Lua configuration and setup
  guidance for integrating the cyber-ware components.

Keep personal secrets, machine-specific state, and unreviewed configuration
out of the public repository. Hardware-specific settings belong in a local
`hyprland.local.lua` file rather than the shared modules.

## Install the cyber-ware setup

The top-level installer always installs the modular Hyprland configuration,
then asks whether to install each optional cyber-ware component. It does not
use sudo or install operating-system packages; each component installer checks
its own dependencies.

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

## Repository setup

GitHub credentials and the first push workflow are documented in
[`docs/git-setup.md`](docs/git-setup.md). Initialize Git at this repository
root—not inside a component—so future setup files and tools belong to the same
parent repository.
