#!/bin/sh
# Invoked asynchronously once at compositor startup, never on config reload.
set -eu
: "${XDG_RUNTIME_DIR:?Missing user runtime directory}"
: "${HYPRLAND_INSTANCE_SIGNATURE:?Missing Hyprland session identity}"
: "${WAYLAND_DISPLAY:?Missing Wayland display}"
exec 9>"$XDG_RUNTIME_DIR/cyber-ware-start-$HYPRLAND_INSTANCE_SIGNATURE.lock"
flock -n 9 || exit 0

# A socket alone does not prove the compositor is accepting requests yet.
case "$WAYLAND_DISPLAY" in /*) display_socket=$WAYLAND_DISPLAY ;; *) display_socket=$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY ;; esac
attempt=0
until [ -S "$display_socket" ] && timeout 2 hyprctl monitors -j >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 40 ] || { echo 'cyber-ware: compositor did not become ready; login apps were not started.' >&2; exit 1; }
    sleep 0.25
done

dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE DISPLAY
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE DISPLAY

# Early D-Bus activation can exhaust the restart limit using an old environment.
# Check the backend itself: the frontend may advertise interfaces without it.
attempt=0
until (
    systemctl --user reset-failed xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service &&
    systemctl --user start xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service &&
    timeout 5 busctl --user get-property org.freedesktop.impl.portal.desktop.hyprland /org/freedesktop/portal/desktop org.freedesktop.impl.portal.ScreenCast version >/dev/null
); do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 3 ] || { echo 'cyber-ware: portal backend recovery failed; login apps were not started.' >&2; exit 1; }
    sleep 1
done
systemctl --user restart xdg-desktop-portal.service

# Check at launch time, after waiting, in case the user already opened an app.
start_app() {
    process=$1
    shift
    if command -v "$1" >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x -- "$process" >/dev/null; then
        "$@" 9>&- >/dev/null 2>&1 &
    fi
}
if [ "${1:-}" != --portals-only ]; then
    start_app opendeck opendeck --hide
    start_app Discord discord
    start_app steam steam
fi
