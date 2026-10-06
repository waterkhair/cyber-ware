# cyber-console

`cyber-console` is a small launcher/toggler for dedicated floating Ghostty
windows running terminal tools on Hyprland. One command handles every
configured tool, so each application does not need its own launch script:

```sh
cyber-console impala
cyber-console wiremix
cyber-console bluetui
cyber-console btop
cyber-console yazi
```

Calling a tool toggles its dedicated window: if the matching window is open,
the command closes it; otherwise it starts that TUI in Ghostty. It only targets
the exact app class configured for that tool. The Hyprland client lookup is
backed up by an exact Ghostty process check, which also lets the Yazi toggle
close its terminal if Yazi temporarily hides while opening a file in another
application.

The package is user-scoped. It does not need root, install system packages,
edit Hyprland or Waybar configuration, add shortcuts, or start applications at
login. It has no background service: the small Python command runs only when
invoked and then replaces itself with Ghostty. Closing a tool window terminates
that TUI; invoking it again starts a fresh process rather than keeping a hidden
instance in memory.

## Requirements

Required:

- Python 3
- Ghostty (the app class/title command-line options are Ghostty-specific)
- Hyprland and `hyprctl`

The installer checks these before it changes user files. It does not use
`sudo`, install packages, or perform privileged actions. Each configured TUI
is an optional dependency: the installer reports missing commands, and
`cyber-console --check` checks them later. The defaults are `impala`,
`wiremix`, `bluetui`, `btop`, and `yazi`.

For the one-line installer, `curl` and `tar` are also needed to fetch the
repository archive. A local clone only needs Python 3 and the required runtime
programs.

## Install

Install the current public `main` branch with one command:

```sh
curl -fsSL https://raw.githubusercontent.com/WaterKhair/cyber-ware/main/cyber-console/install.sh | sh
```

The repository must have the `cyber-console` component committed and pushed to
`main` for that command to include it.

This downloads the public repository archive and installs only `cyber-console`.
As with any `curl | sh` installer, this runs code from the repository. To
inspect the installer first:

```sh
git clone https://github.com/WaterKhair/cyber-ware.git
cd cyber-ware/cyber-console
./install.sh
```

The command is installed in `~/.local/bin`, its program files under
`~/.local/share/cyber-console`, and the default configuration at
`~/.config/cyber-console/config.json`. `PREFIX`, `XDG_CONFIG_HOME`, and
`XDG_DATA_HOME` can be set to use alternate user-local locations. Ensure the
command directory is on `PATH`.

The installer creates the config only if it does not exist, so upgrades keep
your settings. It never edits Hyprland or Waybar files. After installing,
follow the optional integration steps below to add floating rules, shortcuts,
and bar click actions.

## Commands

```sh
cyber-console <tool>           # toggle that tool's floating terminal
cyber-console --list           # show configured tools and command availability
cyber-console --check          # check Ghostty, Hyprland, and configured tools
cyber-console --theme          # show current theme
cyber-console --theme husky    # use husky for newly opened tools
cyber-console --uninstall      # remove program files; keep your config
cyber-console --uninstall --purge  # remove program and config after confirmation
cyber-console --help
```

Uninstall does not remove packages or change Hyprland/Waybar configuration. If
you added the example bindings or rules, remove them separately. Purge asks you
to type `cyber-console` before deleting the component config.

## Configuration

Edit `~/.config/cyber-console/config.json` to change the Ghostty executable,
window class/title, or command and arguments for each tool. For example:

```json
{
  "terminal": "ghostty",
  "applications": {
    "wiremix": {
      "class": "org.cyber-ware.cyber-console.wiremix",
      "title": "Wiremix",
      "command": ["wiremix", "--mouse", "--theme", "default"]
    }
  }
}
```

Keep every tool you want to launch in `applications`. A command is an argument
array, not shell text, so arguments are passed literally and shell expansion is
not performed. The `class` should be unique per tool and must match the
Hyprland rule you use for that window.

`cyber-console --theme` selects the Ghostty palette for future floating
terminal windows. It supports `synthwave`, `greenline`, and `husky` (black and
white with grayscale highlights); the
umbrella `cyber-ware --theme NAME` keeps this selection in sync with the rest
of the desktop. Theme files are stored with cyber-console's app files, so it
does not edit or replace your main Ghostty configuration.

## Hyprland integration

Add a floating rule for each configured class. With a Lua config using `hl`
helpers, this compact example floats and centers all five default tools:

```lua
local consoleTools = {
    { name = "impala", width = 1100, height = 720 },
    { name = "wiremix", width = 1100, height = 720 },
    { name = "bluetui", width = 1100, height = 720 },
    { name = "btop", width = 1200, height = 800 },
    { name = "yazi", width = 1400, height = 900 },
}

for _, tool in ipairs(consoleTools) do
    hl.window_rule({
        name = "cyber-console-" .. tool.name,
        match = {
            class = "^org\\.cyber-ware\\.cyber-console\\." .. tool.name .. "$",
        },
        float = true,
        size = { tool.width, tool.height },
        center = true,
    })
end
```

Add only the shortcuts you want. Example `hl` bindings:

```lua
hl.bind("CTRL + SUPER + I", hl.dsp.exec_cmd("cyber-console impala"), { description = "Toggle Impala" })
hl.bind("CTRL + SUPER + V", hl.dsp.exec_cmd("cyber-console wiremix"), { description = "Toggle Wiremix" })
hl.bind("CTRL + SUPER + B", hl.dsp.exec_cmd("cyber-console bluetui"), { description = "Toggle Bluetui" })
hl.bind("CTRL + SUPER + O", hl.dsp.exec_cmd("cyber-console btop"), { description = "Toggle btop" })
hl.bind("CTRL + SUPER + Y", hl.dsp.exec_cmd("cyber-console yazi"), { description = "Toggle Yazi" })
```

To invoke one from a Waybar module click handler, use a command such as
`"on-click": "cyber-console impala"`. The same pattern works for `wiremix`.
If you use `cyber-panel`, update the corresponding `on-click` values there.

If you prefer traditional Hyprland syntax, use one rule per app:

```ini
windowrule {
    name = cyber-console-impala
    match:class = ^org\.cyber-ware\.cyber-console\.impala$
    float = true
    center = true
    size = 1100 720
}
```

Reload Hyprland after adding or changing its rules and bindings. The exact class
is configurable; if you change it in `config.json`, update the matching rule.

## Development

From this directory:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
sh -n install.sh
```

`cyber-console` is distributed under the repository's MIT License; see
[`../LICENSE`](../LICENSE).
