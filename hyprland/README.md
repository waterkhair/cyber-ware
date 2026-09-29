# Hyprland configuration

This directory contains the shared Lua configuration layer for the cyber-ware
desktop. `hyprland.lua` is the entry point; its modules group appearance,
window/workspace rules, session startup, and keybindings. Machine-specific
monitor and GPU settings belong in `hyprland.local.lua`, not in the shared
modules.

The repository's top-level `install.sh` installs this configuration first,
then asks whether to install each optional component. Use
`./install.sh --no-components` for only the config or `./install.sh --all` to
select every component without prompts. The config conditionally registers
component shortcuts and startup commands when their executables are present.
When upgrading an older modular config, the installer preserves existing
`environment.lua` and `monitors.lua` modules by loading them from a newly
created `hyprland.local.lua` (unless that local file already exists).

The shared theme command, `cyber-ware --theme greenline|synthwave`, controls
the window and group border palette in `appearance.lua`. It also synchronizes
the same selection to installed theme-aware cyber-ware components. The shared
selection is stored as plain text at `~/.config/cyber-ware/theme` (or under
`$XDG_CONFIG_HOME`).

The config is an opinionated integration profile, not a minimal Hyprland install.
It expects the relevant programs and cyber-ware components to be installed.
Install each optional component from its own directory and follow its README.

## Install

Back up your existing Hyprland config outside `~/.config/hypr` before copying
files. For example, from the repository root:

```sh
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
backup="$HOME/.local/share/cyber-ware/backups/hyprland-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
[ ! -e "$config_home/hypr/hyprland.lua" ] || cp -a "$config_home/hypr/hyprland.lua" "$backup/"
[ ! -d "$config_home/hypr/hyprland" ] || cp -a "$config_home/hypr/hyprland" "$backup/"
```

Then install the entry point and modules:

```sh
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
mkdir -p "$config_home/hypr/hyprland"
cp hyprland/hyprland.lua "$config_home/hypr/hyprland.lua"
cp hyprland/appearance.lua hyprland/windows.lua \
   hyprland/autostart.lua hyprland/keybindings.lua \
   "$config_home/hypr/hyprland/"
```

If this is a new setup and you need hardware overrides, copy and edit the
example:

```sh
cp hyprland/machine.example.lua "$config_home/hypr/hyprland.local.lua"
```

That machine-local file is loaded before the shared modules and is not
overwritten by the commands above. Keep it private if it contains identifying
details.
Component commands default to `~/.local/bin`; set `CYBER_WARE_BIN` in the
Hyprland session environment if you install them elsewhere.

Then install the desired cyber-ware components and required system programs.
The keybindings invoke `cyber-console`, `cyber-wall`, `cyber-scan`, and
`cyber-jackout`, as well as local `fuzzel-toggle` and `cliphist-fuzzel` helpers.
The startup module also launches Waybar, Mako, Hypridle, OpenDeck, Discord, and
Steam; remove or change those entries in `hyprland/autostart.lua` if they are
not part of your setup. It does not install packages or create those helpers.

Check the config and reload from an active Hyprland session:

```sh
hyprctl configerrors
hyprctl reload
hyprctl configerrors
```

## Layout

- `hyprland.lua` — entry point and optional local override loader
- `appearance.lua` — gaps, borders, groups, animations, input defaults
- `windows.lua` — app rules and workspace behavior
- `autostart.lua` — session process startup
- `keybindings.lua` — keyboard and mouse bindings
- `machine.example.lua` — optional per-machine GPU and monitor settings

The Lua module layout follows [Hyprland's official configuration
example](https://github.com/hyprwm/Hyprland/blob/main/example/hyprland.lua),
which recommends splitting config files and loading them with `require()`.

## Uninstall

Restore the backup you made before installation. If you did not have an existing
Hyprland config, remove only `hyprland.lua` and the `hyprland/` module directory
from your Hyprland config directory. Do not remove `hyprland.local.lua` unless
you also want to discard your machine-specific settings.
