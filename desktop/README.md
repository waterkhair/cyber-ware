# Base desktop profile

The top-level cyber-ware installer installs this profile even when all optional
components are skipped. It includes:

- Ghostty: JetBrainsMono Nerd Font, padding, transparency, underline cursor,
  image-protocol support, and Fish as its terminal command.
- Fish: compact path/Git prompt, the installed cyber-ware command directory on
  PATH, editor discovery and zoxide integration. No CachyOS-only script imports,
  universal variables, personal functions, credentials, or history are copied.
  The account's login shell is not changed.
- Yazi: the 1:3:4 panel layout, large image previews, and mpv media openers.
  mpv selects its graphics backend automatically; no NVIDIA/Vulkan override.
- Nautilus: installed as Files, opened by Ctrl+Super+F. Personal bookmarks and
  application preferences are not exported.
- GTK 3/4: adw-gtk3-dark where supported, dark preference for libadwaita,
  Noto Sans, and theme palette CSS without changing widget layout.
- Qt 5/6: Fusion widgets and matching color palettes via qt5ct/qt6ct.
- Breeze dark icons and Breeze cursors (24 px), with xsettingsd for X11 clients.

`cyber-ware --theme synthwave|greenline|husky` updates managed terminal and
GTK/Qt palette files alongside the component themes. Fish uses matching prompt
colors. Applications may need to be reopened; use Ghostty's reload-configuration
action or start a new instance for terminal changes. GTK/libadwaita and Qt
applications vary in which styling settings they honor; the profile does not
patch applications or force unsupported widget themes. After initial setup,
a fresh Hyprland login propagates Qt/cursor settings to all session processes.

## Ownership and restoration

`manage.py` is an internal installer helper, not an extra public command. Its
installed copy and palettes live in `$XDG_CONFIG_HOME/cyber-ware/desktop/`.
It checks all destinations for symlinks before changing files, records the
original file contents/permissions and installed hashes in
`$XDG_STATE_HOME/cyber-ware/desktop.json`, and restores preceding contents if a
profile file publication fails. The manifest is private (mode 0600); it can
contain previous personal config contents and must not be committed.

On first installation, the profile replaces the listed app config files after
recording their originals. On upgrades/theme changes, files edited since their
last managed version are preserved and reported. `cyber-ware --uninstall`
restores original unedited files or removes ones that did not previously exist.
Edited files and their recovery records remain. Unrelated files, such as Fish
functions, Yazi plugins, and GTK bookmarks, are not removed.

GTK interface preferences are applied after graphical-session readiness (or
during installation in a live session), and their original values are saved
separately in `desktop-settings.json`. Uninstall restores values still matching
the managed settings and preserves subsequent user edits.

This profile does not manage tmux, SDDM, Limine, browser/account profiles, or
Steam/Discord/OBS/OpenDeck installation. GPU and display settings remain in
the user's `hyprland.local.lua`.
