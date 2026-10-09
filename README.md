# cyber-ware

`cyber-ware` is the umbrella repository for this Hyprland setup: its
configuration, setup documentation, and optional installable tools. Each
standalone tool lives in its own top-level directory, with its own code,
dependencies, installer, and usage instructions. Users can install only the
components they want.

## Components

- [`cyber-wall/`](cyber-wall/README.md) — GTK image/video wallpaper picker for
  Hyprland, using `mpvpaper`, with three default images installed in
  `~/Pictures/Wallpapers` and `cozy-husky-bay.png` as the first-run wallpaper.
- [`cyber-signal/`](cyber-signal/README.md) — user-scoped system status
  notifications with Mako themes and optional systemd user timers.
- [`cyber-panel/`](cyber-panel/README.md) — a themed Waybar setup for Hyprland,
  with synthwave, greenline, and husky styles.
- [`cyber-console/`](cyber-console/README.md) — one command to toggle floating
  Ghostty windows for terminal tools such as Impala, Wiremix, Bluetui, btop,
  and Yazi, with matching terminal palettes.
- [`cyber-jackout/`](cyber-jackout/README.md) — clean Hyprland logout, reboot,
  and shutdown with wallpaper/portal cleanup and matching synthwave/greenline/husky
  wlogout themes.
- [`cyber-scan/`](cyber-scan/README.md) — Wayland region screenshots through
  grim, slurp, and swappy.
- [`cyber-deck/`](cyber-deck/README.md) — themed Fuzzel application launcher
  with a Super+Space toggle command.
- [`cyber-wave/`](cyber-wave/README.md) — persistent floating radio-station
  picker with `mpv` playback and cyber-ware themes.
- [`hyprland/`](hyprland/README.md) — modular Lua configuration and setup
  guidance for integrating the cyber-ware components.
- [`desktop/`](desktop/README.md) — base Ghostty, Fish, Yazi, Nautilus, and
  GTK/Qt appearance integration, installed with the umbrella desktop.

Keep personal secrets, machine-specific state, and unreviewed configuration
out of the public repository. Hardware-specific settings belong in a local
`hyprland.local.lua` file rather than the shared modules.

## Install the cyber-ware setup

The top-level installer asks which optional cyber-ware components to include,
installs the required system packages, then installs the modular Hyprland
configuration and selected components. Automatic package installation supports
CachyOS/Arch systems with pacman. Only the package transaction uses sudo; run
the installer as your regular desktop user. It requires Hyprland
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
`./install.sh --no-components` to install the Hyprland config, desktop profile, and base
packages, or `./install.sh --all` to select every component. Sudo and pacman
can still prompt for authentication and transaction confirmation. The config
installer preserves an existing entry point and module folder under
`$XDG_STATE_HOME/cyber-ware/backups/`; it leaves an existing
`hyprland.local.lua` untouched and migrates old `environment.lua`/`monitors.lua`
modules into it when possible.
Details and machine-specific setup are in [`hyprland/README.md`](hyprland/README.md).
The shared command is installed to `~/.local/bin/cyber-ware` by default; ensure
`~/.local/bin` is on `PATH`.
After installing selected components, the installer reloads an active
Hyprland session. Its reload handler starts missing configured services,
reloads Mako, leaves an existing Waybar running, and restores a saved wallpaper
without duplicating running processes. If run from a TTY, those actions begin
on the next Hyprland login. The transaction stages Lua modules first and
restores the prior config if publication or active config validation fails.
Automatic reload is paused through the Lua API during publication, and its
previous setting is restored. Each installation has a unique entry-point token;
the installer checks it after reload so an unrelated `--config` file cannot
produce a false success.

### System packages and desktop defaults

Package groups are maintained in [`packages/arch.sh`](packages/arch.sh).
The installer combines the base group with selected component groups, removes
duplicates, and installs only missing packages with `sudo pacman -S --needed`.
Skipped components do not add their package groups; a shared dependency may
still be needed by the base desktop or another selected component.

| Group | Provided requirements |
|---|---|
| Base desktop | Hyprland, Lua/Python, Ghostty, Fish, Yazi and media/preview tools, Nautilus/GVfs, GTK/Qt themes, Breeze icons/cursors, fonts, xsettingsd, Polkit agent, portals, PipeWire/WirePlumber audio, Fuzzel theme picker, system utilities |
| cyber-wall | Python/GTK 4, mpvpaper, FFmpeg video previews |
| cyber-signal | Python, Mako, libnotify, NetworkManager client, Arch update checker |
| cyber-console | Python, Ghostty, Impala/iwd, Wiremix, Bluetui/BlueZ, btop (Yazi is part of the base desktop) |
| cyber-panel | Python, Waybar, playerctl |
| cyber-jackout | wlogout, Hyprlock, Hypridle, libnotify |
| cyber-scan | grim, slurp, swappy |
| cyber-deck | Python, Fuzzel, cliphist, wl-clipboard |
| cyber-wave | Python/GTK 4, mpv, mpv-mpris |

Selecting cyber-jackout enables its 5-minute lock/10-minute display-off policy;
selecting cyber-deck enables clipboard history and Super+V; selecting
cyber-signal enables notification monitoring. These are part of the umbrella
desktop profile, with no extra feature prompts. Clipboard history persists
copied content locally. Existing unmanaged lock configs are preserved and
reported as an integration conflict, not overwritten. A failed integration
produces a failed installer result with its component identified.

The base [desktop profile](desktop/README.md) configures Ghostty to launch Fish,
installs a portable shell prompt and Yazi media openers, applies coordinated
GTK/Qt appearance, and binds Ctrl+Super+F to Nautilus. It is included even with
`--no-components`. Original app configs are backed up; subsequent edits are
preserved. Uninstall restores managed originals. Theme changes also update
this profile. No tmux, SDDM, Limine, or personal application profiles are copied.

The package phase runs before any active desktop config is replaced. It checks
that every missing package exists in the configured repositories before asking
pacman to install anything. Some packages, such as mpvpaper/wlogout, may require
additional provisioning on plain Arch; cyber-ware does not add repositories or
install an AUR helper. An unavailable package produces an actionable error.

Start with a fully updated system. The installer does not refresh package
databases, perform a full system upgrade, install GPU drivers, or select a
monitor mode. If package installation fails due to stale mirrors/dependencies,
complete `sudo pacman -Syu` and rerun. Avoid partial upgrades as described in
the [Arch maintenance guidance](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported).
Pacman retains its normal conflict/replacement prompts. System packages remain
installed after a later desktop-install failure or cyber-ware uninstall.
NetworkManager/iwd and Bluetooth service configuration is left with the host
system; package installation does not switch an existing network backend.

Standalone component installers still check requirements without installing
system packages or enabling the umbrella profile. For another distribution or
an externally provisioned machine, install the requirements yourself and run
`CYBER_WARE_INSTALL_PACKAGES=0 ./install.sh`; executable and GTK checks still
apply. For a streamed install, put the variable on the shell:
`curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/install.sh | CYBER_WARE_INSTALL_PACKAGES=0 sh`.

The installed command directory is recorded for Hyprland and Waybar, so a
custom `PREFIX` works for desktop actions even when the graphical session does
not inherit that directory in `PATH`. To use commands interactively, add that
directory to your shell path (for fish, for example: `fish_add_path ~/.local/bin`).

The installer also provides one shared theme command:

```sh
cyber-ware --theme                 # show the selected theme
cyber-ware --theme-picker          # choose a theme with Fuzzel
cyber-ware --theme greenline       # switch the desktop to greenline
cyber-ware --theme synthwave       # switch the desktop to synthwave
cyber-ware --theme husky           # switch to black and white with grayscale accents
```

`Ctrl+Super+Alt+T` opens the theme picker; `Super+Space` remains the app
launcher.

The shared theme is saved in `~/.config/cyber-ware/theme` (or under
`$XDG_CONFIG_HOME`). Hyprland reads it for active/inactive window and group
borders. The command also updates installed `cyber-wall`, `cyber-signal`,
`cyber-panel`, `cyber-jackout`, `cyber-deck`, `cyber-console`, and
`cyber-scan`, and `cyber-wave`, then reloads Hyprland.
Missing components are skipped; components installed later inherit the saved
theme. `synthwave` is the default when no shared selection exists.

To remove only the umbrella Hyprland config and `cyber-ware` command:

```sh
cyber-ware --uninstall
```

Uninstall requires typing `cyber-ware` to confirm. It restores managed base
desktop configs and interface preferences, preserves user-edited profile files,
restores the original Hyprland entry point and module directory, and preserves a recovery copy of the
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
preserving the existing copies, then provides `synthwave`, `greenline`, and `husky`
themes. Its standalone install, dependency, and recovery details are in the
[`cyber-panel` README](cyber-panel/README.md).

`cyber-console` provides a single configurable command for toggling floating
Ghostty TUI windows with matching terminal palettes. Its installer leaves compositor bindings and window rules
to the user; integration examples are in the
[`cyber-console` README](cyber-console/README.md).

`cyber-deck` toggles the Fuzzel application launcher and provides synthwave,
greenline, and husky themes. Its standalone installer does not edit Hyprland bindings;
the bundled cyber-ware configuration binds Super+Space when the component is
installed.
The umbrella installer enables clipboard history and Super+V. For a standalone
installation, enable it with `cyber-deck --clipboard enable`.

The umbrella installer runs `cyber-jackout --enable-idle` to install the themed Hyprlock and
Hypridle configuration: lock after five minutes, turn displays off after ten,
and lock before suspend. Existing Hyprland lock/idle configs are preserved.
Remove the managed integration with `cyber-jackout --disable-idle`.
Standalone cyber-jackout installations leave this integration opt-in.

## Repository setup

GitHub credentials and the first push workflow are documented in
[`docs/git-setup.md`](docs/git-setup.md). Initialize Git at this repository
root—not inside a component—so future setup files and tools belong to the same
parent repository.
