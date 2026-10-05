# cyber-deck

`cyber-deck` toggles the Fuzzel application launcher for Hyprland. It provides
three Fuzzel themes, `synthwave`, `greenline`, and `husky`, and an optional themed
clipboard history picker backed by cliphist. It works as a standalone
cyber-ware component and does not install system packages.

## Requirements

- Fuzzel
- Python 3
- A Wayland session with Fuzzel's required layer-shell support
- Optional clipboard history: `cliphist`, `wl-copy`, and `wl-paste`

Install Fuzzel with your distribution's package manager before installing
cyber-deck.

## Install

Install the current public `main` branch with one command:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-deck/install.sh | sh
```

This installs user-local files and does not require Git or root. It fetches the
public cyber-ware source archive and installs only cyber-deck. As with any
`curl | sh` installer, this runs code from the repository. To inspect the
installer first:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-deck
./install.sh
```

The command goes in `~/.local/bin`, program files in
`~/.local/share/cyber-deck`, and editable theme files in
`~/.config/cyber-deck/themes`. `PREFIX`, `XDG_DATA_HOME`, and
`XDG_CONFIG_HOME` select alternate locations. Ensure the command directory is
on `PATH`.

The installer keeps existing theme files and theme selection during upgrades.
It stages and validates the replacement before publishing it, restoring the
previous installation if publication fails. Both bundled themes support
Ctrl+J/Ctrl+K and arrow navigation; Escape closes the launcher. Existing edited
theme files are preserved, so add the bundled `[key-bindings]` section to older
local themes if you want these bindings.
It does not install Fuzzel or change Hyprland bindings. The one-line install
requires the cyber-ware repository to be public and have a commit on `main`.

## Use

```sh
cyber-deck                         # toggle the app launcher
cyber-deck --clipboard             # pick saved clipboard text or image
cyber-deck --clipboard enable      # enable clipboard history collection
cyber-deck --clipboard disable     # disable clipboard history collection
cyber-deck --theme                 # show the selected theme
cyber-deck --theme greenline       # switch to greenline
cyber-deck --theme synthwave       # switch to synthwave
cyber-deck --theme husky           # monochrome with green/blue accents
cyber-deck --check                 # validate both Fuzzel theme files
cyber-deck --uninstall             # remove program; keep theme files
cyber-deck --uninstall --purge     # confirm, then remove theme files too
```

The theme takes effect the next time the launcher opens. Edit either INI file
under `~/.config/cyber-deck/themes` to customize its Fuzzel settings. The
component checks for its own Fuzzel window before toggling it, so unrelated
Fuzzel menus remain open.

Clipboard history is disabled by default. After enabling it, run
`hyprctl reload`: cyber-ware then starts the `wl-paste` watcher and registers
Super+V. Disabling it stops only the matching cliphist watcher; reload removes
the binding. The picker passes the selected row to `cliphist decode` through
standard input, never through a shell, and restores image MIME types.

## Hyprland integration

The cyber-ware Hyprland configuration binds Super+Space to `cyber-deck` when
the command is installed. A standalone install leaves Hyprland files alone; add
a binding yourself if needed. For a Lua config using `hl` helpers:

```lua
hl.bind("SUPER + Space", hl.dsp.exec_cmd(os.getenv("HOME") .. "/.local/bin/cyber-deck"), { description = "Toggle application launcher" })
```

For traditional Hyprland syntax:

```ini
bind = SUPER, Space, exec, ~/.local/bin/cyber-deck
```

Use your installed command path if you chose a custom `PREFIX`. When upgrading
an older cyber-ware desktop, replace the existing `fuzzel-toggle` target in
`~/.config/hypr/hyprland/keybindings.lua` with `cyber-deck`, then run
`hyprctl reload`. Do not add a second Super+Space binding. Installing this
standalone component does not update an older desktop configuration for you.

## Shared cyber-ware themes

`cyber-ware --theme synthwave`, `cyber-ware --theme greenline`, and
`cyber-ware --theme husky` also update
cyber-deck when it is installed. New installs inherit the currently selected
shared theme. Direct `cyber-deck --theme ...` changes only cyber-deck's
selection. Reinstalling preserves that selection; the shared theme is inherited
only when no local selection exists.

## Uninstall

`cyber-deck --uninstall` removes its command and program files, disables
clipboard collection, and keeps the selected theme and editable theme files.
Add `--purge` to remove those settings after typing `cyber-deck` to confirm. It
does not alter Hyprland configuration or uninstall Fuzzel.
The installation manifest records the command path, so uninstall also works
for a custom `PREFIX` without exporting it again. Keep any custom
`XDG_CONFIG_HOME` in your session environment when accessing its configuration.

## Tests

From the repository root:

```sh
PYTHONPATH=cyber-deck/src python3 -m unittest discover -s cyber-deck/tests
```

Tests use temporary directories and mocked downloads/Fuzzel. They cover
upgrade rollback, custom-prefix uninstall, theme preservation, ownership
checks, and streamed installation from inside a stale checkout. No live
desktop applications are launched.

See [../docs/git-setup.md](../docs/git-setup.md) for the repository workflow.
