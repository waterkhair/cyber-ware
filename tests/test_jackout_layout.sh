#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/cyber-jackout-layout-test.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/home/.config/wlogout"
printf '%s\n' 'original user layout' > "$tmp/home/.config/wlogout/layout"
env HOME="$tmp/home" PREFIX="$tmp/home/.local" XDG_CONFIG_HOME="$tmp/home/.config" \
    XDG_DATA_HOME="$tmp/home/.local/share" XDG_STATE_HOME="$tmp/home/.local/state" \
    sh "$repo/cyber-jackout/install.sh" >/dev/null
layout=$tmp/home/.config/wlogout/layout
grep -Fq "$tmp/home/.local/bin/cyber-jackout logout" "$layout"
grep -Fq "$tmp/home/.local/bin/cyber-jackout reboot" "$layout"
grep -Fq "$tmp/home/.local/bin/cyber-jackout poweroff" "$layout"
grep -Fq '"action": "systemctl suspend"' "$layout"
grep -Fq 'original user layout' "$tmp/home/.local/state/cyber-jackout/backups/layout"
printf '%s\n' cyber-jackout | env HOME="$tmp/home" PREFIX="$tmp/home/.local" \
    XDG_CONFIG_HOME="$tmp/home/.config" XDG_DATA_HOME="$tmp/home/.local/share" \
    XDG_STATE_HOME="$tmp/home/.local/state" "$tmp/home/.local/bin/cyber-jackout" --uninstall >/dev/null
[ "$(cat "$layout")" = 'original user layout' ]

env HOME="$tmp/home" PREFIX="$tmp/home/.local" XDG_CONFIG_HOME="$tmp/home/.config" \
    XDG_DATA_HOME="$tmp/home/.local/share" XDG_STATE_HOME="$tmp/home/.local/state" \
    sh "$repo/cyber-jackout/install.sh" >/dev/null
printf '%s\n' 'user-edited layout' > "$layout"
env HOME="$tmp/home" PREFIX="$tmp/home/.local" XDG_CONFIG_HOME="$tmp/home/.config" \
    XDG_DATA_HOME="$tmp/home/.local/share" XDG_STATE_HOME="$tmp/home/.local/state" \
    sh "$repo/cyber-jackout/install.sh" > "$tmp/reinstall.log"
grep -Fq 'user-edited layout' "$layout"
grep -Fq 'Kept your modified wlogout layout' "$tmp/reinstall.log"
printf '%s\n' cyber-jackout | env HOME="$tmp/home" PREFIX="$tmp/home/.local" \
    XDG_CONFIG_HOME="$tmp/home/.config" XDG_DATA_HOME="$tmp/home/.local/share" \
    XDG_STATE_HOME="$tmp/home/.local/state" "$tmp/home/.local/bin/cyber-jackout" --uninstall >/dev/null
[ "$(cat "$layout")" = 'user-edited layout' ]
printf '%s\n' 'PASS: generated power actions use cyber-jackout; original and later user-edited layouts are preserved safely.'
