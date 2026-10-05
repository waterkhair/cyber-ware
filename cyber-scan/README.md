# cyber-scan

`cyber-scan` captures a selected screen region on Wayland: `slurp` selects the
area, `grim` captures it, and `swappy` opens the image for annotation and
saving. `Escape` in the selection step cancels without taking a screenshot.

## Requirements

- Hyprland or another Wayland compositor
- `grim`, `slurp`, and `swappy`

The installer checks these tools before modifying user files. It does not
install packages or require root access. Install missing dependencies with
your distribution's package manager first.

## Install

Install from the public `main` branch:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-scan/install.sh | sh
```

To inspect the component before installing:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-scan
./install.sh
```

The command is installed in `~/.local/bin/cyber-scan`; program files are in
`~/.local/share/cyber-scan`. Set `PREFIX` or `XDG_DATA_HOME` for alternate
user-local paths. Ensure `~/.local/bin` is on `PATH`.

## Use

```sh
cyber-scan          # select a region, capture it, and open Swappy
cyber-scan --check  # check dependencies and Wayland environment
cyber-scan --theme  # show current accent theme
cyber-scan --theme husky  # use blue/green selection accents
cyber-scan --help
cyber-scan --uninstall
```

Swappy controls the final save action and location. For example, `Ctrl+S`
saves when `auto_save=false`; the destination follows `save_dir` in your
Swappy configuration. cyber-scan creates `~/Pictures/Screenshots` before
opening Swappy; the final save destination is controlled by Swappy's
`save_dir` setting.

The Slurp selection uses the selected cyber-ware accent (`synthwave`,
`greenline`, or `husky`). `cyber-ware --theme NAME` updates cyber-scan when it
is installed. Swappy's own editor controls continue to follow the host GTK
theme.

## Hyprland shortcut

The component does not edit compositor configuration. Add a binding such as
this to a Lua-based Hyprland configuration:

```lua
hl.bind("CTRL + SUPER + ALT + P", hl.dsp.exec_cmd("cyber-scan"), {
    description = "Capture and annotate a screen region",
})
```

Reload Hyprland after adding the binding.

## Uninstall

```sh
cyber-scan --uninstall
```

Uninstall removes only the managed command and program directory. It leaves
Hyprland, Swappy, and package-manager configuration untouched, and does not
delete screenshots.

The saved theme selection is also preserved at
`~/.config/cyber-scan/theme` for a future reinstall.

## License

MIT; see [`../LICENSE`](../LICENSE).
