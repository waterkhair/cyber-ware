# SDDM setup

This is an optional part of the top-level cyber-ware installation, not a
standalone cyber-ware component. When selected, cyber-ware installs the Arch
`sddm` package, downloads the Monochrome SDDM theme from the upstream GitLab
project at a pinned revision, installs the tracked `wallpaper.png` into the
theme directory, enables the theme's custom-background setting, and sets
`Current=monochrome` as the default greeter theme. The theme source files are
not bundled in this repository; the wallpaper asset is.

The installer preserves all other `/etc/sddm.conf` settings and backs up the
original file to `/etc/sddm.conf.cyber-ware-backup` before changing its theme
selection. An existing valid Monochrome directory is preserved, then its
`theme.conf` and wallpaper are configured. The image is installed at
`/usr/share/sddm/themes/monochrome/wallpaper.png`, which is the path selected
by Monochrome's custom-background setting. It does not change SDDM's
X11/Wayland configuration, enable its service, or restart the greeter. The
selected theme is used the next time SDDM starts.

The SDDM package, theme files, and selected greeter configuration remain after
`cyber-ware --uninstall`, consistent with the installer's other system package
changes. If you want to restore a previous config, inspect the backup and copy
it back manually; if no `/etc/sddm.conf` existed before installation, remove or
edit the generated `[Theme]` section yourself.
