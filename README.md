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

## Repository setup

GitHub credentials and the first push workflow are documented in
[`docs/git-setup.md`](docs/git-setup.md). Initialize Git at this repository
root—not inside a component—so future setup files and tools belong to the same
parent repository.
