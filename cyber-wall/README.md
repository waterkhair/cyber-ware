# cyber-wall

`cyber-wall` is a small image/video wallpaper picker for Hyprland. It has a GTK 4
preview window, searches configurable folders, applies image or video
wallpapers through `mpvpaper`. It is intentionally user-scoped: it does not
need root or replace files in your existing setup. Lock-screen wallpaper
syncing is explicit and only occurs when requested.

## Requirements

- Hyprland (for automatic monitor detection; otherwise set an output name)
- Python 3 with GTK 4 PyGObject bindings (`python-gobject`, `gtk4` on Arch)
- `mpvpaper` to apply wallpapers
- `ffmpeg` (optional) for video preview thumbnails and still images when syncing video wallpapers to Hyprlock
- `hyprctl` (needed for automatic monitor detection; otherwise configure an exact output name)

## Install

Quick install from the public GitHub repository:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-wall/install.sh | sh
```

This downloads the latest `main` source archive and installs user-local files;
it does not require cloning Git or running as root. As with any `curl | sh`
installer, this executes code from the repository. If you prefer to inspect it
first, clone/download the repo, review `install.sh`, then run it locally:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-wall
./install.sh
```

The installer puts commands in `~/.local/bin`, application code under
`~/.local/share/cyber-wall`, copies default wallpapers to
`~/Pictures/Wallpapers` (creating it if needed), and creates
`~/.config/cyber-wall/config.json` only if it does not already exist. Set
`PREFIX` to choose another command directory and ensure it is on your `PATH`.

The installer copies `calm-water.png`, `cozy-husky-bay.png`,
`cozy-husky-coding.png`, `cozy-husky-pool.png`, and `cyberpunk-husky.png`
without conversion.
Identical files are left in place; if a different file already has one of
these names, installation stops rather than overwriting it. On a fresh setup
with no saved selection or custom default, `cyberpunk-husky.png` is the default
wallpaper and appears in the picker. Existing saved selections and explicit
`default_wallpaper` values take precedence. Before a wallpaper has been
applied, `cyber-wall --sync-lock-wallpaper` uses the same default for Hyprlock.
These images are treated as personal files and remain in
`~/Pictures/Wallpapers` after cyber-wall is uninstalled.

The GitHub one-line installer requires the parent repository to be public and
have a commit on its `main` branch. It fetches the parent archive and installs
only the `cyber-wall` component. It does not install system dependencies or call
`sudo`: install GTK 4/PyGObject and `mpvpaper` using your distribution's
package manager first. `ffmpeg` is optional but needed for video thumbnails.

Commands:

```sh
cyber-wall                                  # toggle the picker
cyber-wall --set ~/Pictures/wall.jpg       # apply an image
cyber-wall --set ~/Videos/wall.mp4          # apply a video
cyber-wall --set --restore                 # restore the last choice
cyber-wall --sync-lock-wallpaper            # sync it to Hyprlock
cyber-wall --theme                         # show current and available themes
cyber-wall --theme husky                   # black and white with grayscale highlights
cyber-wall --uninstall                     # uninstall, keep personal data
cyber-wall --uninstall --purge             # confirm, then remove saved data too
```

The single `cyber-wall` command is the only installed entry point. `--theme`
updates the config while preserving the other settings; close and reopen the
picker to apply a theme change. `--uninstall` stops the picker and the
cyber-wall-managed mpvpaper process before removing the command and app files.
It preserves config, wallpaper state, and cache unless `--purge` is requested.

## Configure

Edit `~/.config/cyber-wall/config.json`. The installer never overwrites it.

```json
{
  "directories": ["~/Pictures/Wallpapers", "~/Videos/Wallpapers"],
  "output": "auto",
  "default_wallpaper": null,
  "theme": "synthwave",
  "mpvpaper_options": [
    "no-audio", "--quiet", "--msg-level=all=warn", "--loop-file=inf",
    "--image-display-duration=inf", "--keep-open=yes", "--hwdec=auto"
  ],
  "preview_seek_seconds": 0.5,
  "preview_timeout_seconds": 8
}
```

`output` accepts `"auto"` (focused Hyprland monitor), `"ALL"`, or an exact
monitor name such as `"DP-1"`. `WALLPAPER_OUTPUT` overrides the config for one
invocation. `cyber-wall` leaves Hyprlock's main theme config unchanged when you
run `cyber-wall --sync-lock-wallpaper`. Rendering is staged before publication;
failed writes roll back the affected configuration and state files. The command
reports missing Hyprlock include integration rather than silently doing nothing.
It copies the current image into
cyber-wall state and updates the separate
`~/.config/hypr/hyprlock-wallpaper.conf` include used by cyber-jackout's lock
themes. For a video, it extracts a still frame with optional `ffmpeg`; it does
not play video on the lock screen. A normal uninstall preserves the synced
wallpaper. `--purge` restores the previous include if it is unchanged; if you
edited it after syncing, purge stops and preserves the files.
When upgrading from a release that edited `hyprlock.conf` directly, the first
sync restores the saved original config and migrates its background to the new
include. If that config was edited after the old sync, the command stops and
asks you to review it first.

The default visual template is `synthwave`. The optional `greenline` theme is a
monochrome terminal look with classic phosphor-green text and accents on deep
near-black surfaces. It has no glow effects; wallpaper thumbnails remain
ordinary images. `husky` uses black surfaces, white text, and grayscale
highlights. Themes are plain GTK CSS, with stylesheets in
`src/cyber_wall/themes/`, separate from picker behavior.

Switch themes with `cyber-wall --theme greenline`, `cyber-wall --theme synthwave`,
or `cyber-wall --theme husky`, then close and reopen the picker. Running
`cyber-wall --theme` prints the current and available themes. Existing
configurations keep their current theme; new installations default to
`synthwave`.

The picker supports arrow keys and Ctrl+J/Ctrl+K for navigation, Enter to
apply, and Escape to close. It remembers the last selection in
`$XDG_STATE_HOME/cyber-wall` and stores generated thumbnails in
`$XDG_CACHE_HOME/cyber-wall`.

## Hyprland integration

Add a key binding and a startup restore to your Hyprland config. For a Lua
config using `hl` helpers, adapt the commands to your configuration API:

```lua
hl.bind("$mainMod SHIFT, W", "exec, cyber-wall")
hl.exec_cmd("cyber-wall --set --restore")
```

Traditional Hyprland syntax:

```ini
bind = SUPER SHIFT, W, exec, cyber-wall
exec-once = cyber-wall --set --restore
```

### Make the picker a centered floating window

The installer deliberately does not edit Hyprland configuration. To make the
picker float, add a window rule to your Hyprland config. With the Lua
configuration API, add this alongside your other `hl.window_rule` calls:

```lua
hl.window_rule({
    name = "cyber-wall-floating-picker",
    match = { class = "^org\\.cyber-ware\\.cyber-wall$" },
    float = true,
    center = true,
    size = { 1100, 820 },
})
```

The class match is the picker's GTK application ID, `org.cyber-ware.cyber-wall`.
It must match the app ID exactly; a rule for the older
`com.waterkhair.wallpaper-picker` application will not match `cyber-wall`, so the
window will use the normal tiling behavior. Adjust `size` to suit your display.
If you prefer a borderless window, you can add `border_size = 0` to the rule.

For a traditional `hyprland.conf` configuration, the equivalent rule is:

```ini
windowrule {
    name = cyber-wall-floating-picker
    match:class = ^org\\.cyber-ware\\.cyber-wall$
    float = true
    center = true
    size = 1100 820
}
```

Reload Hyprland after saving the rule (for example, with `hyprctl reload`),
then open the picker. If it still tiles, inspect the active window with
`hyprctl clients` and check that its `class` is `org.cyber-ware.cyber-wall`.
See the [Hyprland window-rules documentation](https://wiki.hypr.land/configuring/core/rules/window-rules/)
for syntax details and options for your installed Hyprland version.

This rule only controls placement. Use a separate Hyprland key binding to
launch `cyber-wall`; the installer does not add or change shortcuts.

## Uninstall

Run `cyber-wall --uninstall` to stop the picker and managed `mpvpaper` process,
then remove the single command from `PREFIX/bin` and the application code under
`$XDG_DATA_HOME/cyber-wall`. By default, config, last wallpaper state, logs, and
cached previews are preserved so reinstalling keeps your settings.

Run `cyber-wall --uninstall --purge` to additionally remove the `cyber-wall`
config, state, and cache. It asks you to type `cyber-wall` before proceeding.
The command never edits Hyprland config files, and never removes system
packages. If you manually added Hyprland bindings, remove those yourself.

## Development

From the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
```

On the maintainer's current CachyOS/Hyprland setup, the existing
Ctrl+Super+Alt+W binding launches `cyber-wall`, and startup restore uses
`cyber-wall --set --restore`. This personal compositor configuration is not
installed or modified by the component scripts. Hyprlock's background is
configured separately and is not changed when cyber-wall applies a wallpaper.

See [../docs/git-setup.md](../docs/git-setup.md) for the repository workflow and
the local GitHub credential-storage setup used for this project.

## License

`cyber-wall` is distributed under the MIT License; see [../LICENSE](../LICENSE).
