#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir=$data_home/cyber-signal

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: python3.' 'Install Python 3 with your distribution package manager, then retry.' >&2
    exit 1
fi
if ! command -v notify-send >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: notify-send (usually provided by libnotify).' >&2
    exit 1
fi

# Support both a local checkout and curl | sh (where this script is the only
# local file). In the latter case, fetch the public cyber-ware source archive.
if [ ! -f "$project_dir/src/cyber_signal/cli.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-signal.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-signal.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-signal-install.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT HUP INT TERM
    if ! curl -fsSL 'https://github.com/WaterKhair/cyber-ware/archive/refs/heads/main.tar.gz' \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-signal. Check that cyber-ware is public and has a main branch.' >&2
        exit 1
    fi
    project_dir=$download_dir/cyber-signal
    if [ ! -f "$project_dir/src/cyber_signal/cli.py" ]; then
        printf '%s\n' 'The cyber-signal component was not found in the cyber-ware archive.' >&2
        exit 1
    fi
fi

mkdir -p "$prefix/bin" "$app_dir/src" "$config_home/cyber-signal" "$config_home/systemd/user"
rm -rf -- "$app_dir/src/cyber_signal"
cp -R "$project_dir/src/cyber_signal" "$app_dir/src/"
install -m 755 "$project_dir/bin/cyber-signal" "$prefix/bin/cyber-signal"
if [ ! -e "$config_home/cyber-signal/config.json" ]; then
    install -m 600 "$project_dir/config.example.json" "$config_home/cyber-signal/config.json"
fi

# Preserve existing theme selection on upgrades; new installations default to
# synthwave. The generated file is deliberately separate from Mako's own config.
theme=synthwave
if [ -f "$config_home/cyber-signal/config.json" ]; then
    configured_theme=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("theme", "synthwave"))' \
        "$config_home/cyber-signal/config.json" 2>/dev/null || printf '%s' synthwave)
    case "$configured_theme" in synthwave|greenline) theme=$configured_theme ;; esac
fi
install -m 644 "$app_dir/src/cyber_signal/themes/$theme.mako" "$config_home/cyber-signal/active.mako"

escape_sed() { printf '%s' "$1" | sed 's/[\\&#]/\\&/g'; }
exec_path=$(escape_sed "$prefix/bin/cyber-signal")
for template in "$project_dir"/systemd/user/*.in; do
    unit_name=$(basename "$template" .in)
    sed "s#@CYBER_SIGNAL_EXEC@#$exec_path#g" "$template" > "$config_home/systemd/user/$unit_name"
done
printf '{"executable":"%s"}\n' "$prefix/bin/cyber-signal" > "$app_dir/install.json"
chmod 600 "$app_dir/install.json"

if ! command -v nmcli >/dev/null 2>&1; then
    printf '%s\n' 'Optional: nmcli is missing; network notifications need NetworkManager.' >&2
fi
if ! command -v checkupdates >/dev/null 2>&1; then
    printf '%s\n' 'Optional: checkupdates is missing; Arch update checks need pacman-contrib.' >&2
fi
if ! command -v makoctl >/dev/null 2>&1; then
    printf '%s\n' 'Optional: makoctl is missing; Mako theme reload must be done manually.' >&2
fi

printf 'Installed cyber-signal command in %s/bin\n' "$prefix"
printf 'Configuration: %s/cyber-signal/config.json\n' "$config_home"
printf 'User service units: %s/systemd/user\n' "$config_home"
printf '%s\n' 'To apply the notification theme, add this line to your Mako config:'
printf '  include=%s/cyber-signal/active.mako\n' "$config_home"
printf '%s\n' 'Then run: makoctl reload (or restart Mako). Enable monitoring with: cyber-signal --enable'
printf '%s\n' 'Uninstall with: cyber-signal --uninstall; add --purge to remove settings and saved state.'
