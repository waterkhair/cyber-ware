# Package names for the supported pacman installation path.
# Keep component-only tools out of base so skipped components add no packages.
cw_packages() {
    case "$1" in
        base) echo 'hyprland lua python ghostty fish yazi nautilus gvfs xdg-utils mpv ffmpeg file jq poppler fd ripgrep fzf zoxide 7zip chafa gtk3 gtk4 glib2 gsettings-desktop-schemas adw-gtk-theme qt5ct qt6ct breeze-icons breeze-cursors noto-fonts xsettingsd hyprpolkitagent xdg-desktop-portal xdg-desktop-portal-hyprland xdg-desktop-portal-gtk pipewire pipewire-pulse wireplumber ttf-jetbrains-mono-nerd fuzzel coreutils diffutils findutils grep sed util-linux procps-ng systemd dbus bash' ;;
        cyber-wall) echo 'python python-gobject gtk4 mpvpaper ffmpeg' ;;
        cyber-signal) echo 'python mako libnotify networkmanager pacman-contrib' ;;
        cyber-console) echo 'python ghostty impala iwd wiremix bluetui bluez btop' ;;
        cyber-panel) echo 'python waybar playerctl' ;;
        cyber-jackout) echo 'wlogout hyprlock hypridle libnotify' ;;
        cyber-scan) echo 'grim slurp swappy' ;;
        cyber-deck) echo 'python fuzzel cliphist wl-clipboard' ;;
        cyber-wave) echo 'python python-gobject gtk4 mpv mpv-mpris' ;;
        *) printf 'Unknown package group: %s\n' "$1" >&2; return 1 ;;
    esac
}
