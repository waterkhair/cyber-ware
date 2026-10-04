#!/bin/sh
# Invoked asynchronously once at compositor startup, never on config reload.
set -eu
state_home=${XDG_STATE_HOME:-${HOME:?Missing home directory}/.local/state}
mkdir -p "$state_home/cyber-ware"
log_file=$state_home/cyber-ware/session-start.log
exec >>"$log_file" 2>&1
log() { printf '%s cyber-ware-session: %s\n' "$(date --iso-8601=seconds)" "$*"; }
trap 'status=$?; if [ "$status" -ne 0 ]; then log "ERROR at line ${LINENO:-unknown}, exit status $status"; fi' EXIT
log "starting (instance=${HYPRLAND_INSTANCE_SIGNATURE:-unset}, display=${WAYLAND_DISPLAY:-unset})"
: "${XDG_RUNTIME_DIR:?Missing user runtime directory}"
: "${HYPRLAND_INSTANCE_SIGNATURE:?Missing Hyprland session identity}"
: "${WAYLAND_DISPLAY:?Missing Wayland display}"
exec 9>"$XDG_RUNTIME_DIR/cyber-ware-start-$HYPRLAND_INSTANCE_SIGNATURE.lock"
if ! flock -n 9; then log 'another startup helper already holds the session lock; exiting'; exit 0; fi

# A socket alone does not prove the compositor is accepting requests yet.
case "$WAYLAND_DISPLAY" in /*) display_socket=$WAYLAND_DISPLAY ;; *) display_socket=$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY ;; esac
attempt=0
until [ -S "$display_socket" ] && timeout 2 hyprctl monitors -j >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 40 ] || { echo 'cyber-ware: compositor did not become ready; login apps were not started.' >&2; exit 1; }
    sleep 0.25
done
log 'compositor is responding'

environment_vars='WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE'
if [ -n "${DISPLAY:-}" ]; then environment_vars="$environment_vars DISPLAY"; fi
log 'importing graphical activation environment into D-Bus and systemd'
# shellcheck disable=SC2086
dbus-update-activation-environment --systemd $environment_vars
# shellcheck disable=SC2086
systemctl --user import-environment $environment_vars

# PAM starts the wallet handoff before the compositor has a usable display.
# Run it once now that both the Wayland socket and activation environment exist.
kwallet_marker=$XDG_RUNTIME_DIR/cyber-ware-kwallet-$HYPRLAND_INSTANCE_SIGNATURE.started
if [ -x /usr/lib/pam_kwallet_init ] && [ -n "${PAM_KWALLET5_LOGIN:-}" ]; then
    if (set -C; : > "$kwallet_marker") 2>/dev/null; then
        log 'starting delayed KWallet PAM handoff'
        /usr/lib/pam_kwallet_init 9>&- >/dev/null 2>&1 &
    else
        log 'KWallet PAM handoff already launched for this session'
    fi
fi

# Early D-Bus activation can exhaust the restart limit using an old environment.
# Check the backend itself: the frontend may advertise interfaces without it.
recover_portals() {
    attempt=1
    while [ "$attempt" -le 3 ]; do
        log "portal recovery attempt $attempt: clear failed state"
        # D-Bus activated static units may not be loaded yet; reset-failed
        # reports that as an error even though start can load them normally.
        systemctl --user reset-failed xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service >/dev/null 2>&1 || log 'no loaded portal failure state to clear'
        if ! systemctl --user start xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service; then
            log 'portal implementation failed to start; details follow'
            systemctl --user --no-pager --full status xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service || true
        elif ! timeout 5 busctl --user get-property org.freedesktop.impl.portal.desktop.hyprland /org/freedesktop/portal/desktop org.freedesktop.impl.portal.ScreenCast version; then
            log 'Hyprland ScreenCast backend did not answer D-Bus property query'
        else
            log 'Hyprland ScreenCast backend is responding; restarting portal frontend'
            if ! systemctl --user restart xdg-desktop-portal.service; then
                log 'portal frontend restart failed'
            else
                frontend_attempt=1
                while [ "$frontend_attempt" -le 10 ]; do
                    interfaces=$(timeout 5 busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop org.freedesktop.DBus.Introspectable Introspect 2>/dev/null || true)
                    if printf '%s' "$interfaces" | grep -q 'org.freedesktop.portal.ScreenCast' && printf '%s' "$interfaces" | grep -q 'org.freedesktop.portal.Screenshot'; then
                        log 'portal frontend advertises ScreenCast and Screenshot'
                        return 0
                    fi
                    sleep 0.5
                    frontend_attempt=$((frontend_attempt + 1))
                done
                log 'portal frontend did not advertise both capture interfaces'
            fi
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    log 'portal recovery failed; dependent login applications were not started'
    return 1
}
if ! recover_portals; then
    systemctl --user --no-pager --full status xdg-desktop-portal.service xdg-desktop-portal-hyprland.service xdg-desktop-portal-gtk.service || true
    exit 1
fi

# Check at launch time, after waiting, in case the user already opened an app.
start_app() {
    process=$1
    shift
    if command -v "$1" >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x -- "$process" >/dev/null; then
        log "starting login application: $*"
        "$@" 9>&- >/dev/null 2>&1 &
    fi
}
if [ "${1:-}" != --portals-only ]; then
    start_app opendeck opendeck --hide
    start_app Discord discord
    start_app steam steam
fi
log 'session startup helper finished'
