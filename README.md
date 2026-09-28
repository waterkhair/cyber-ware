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

Hyprland setup files and documentation can be added at the repository root or
in a dedicated directory as they are prepared for sharing. Keep personal
secrets, machine-specific state, and unreviewed configuration out of the
public repository.

## Installing a component

Each component documents its own install and uninstall steps. For example,
`cyber-wall` can be installed by running its script from this repository:

```sh
./cyber-wall/install.sh
```

Once this repository is public and has a commit on `main`, its README also
documents the convenient one-command installer for that component.

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
