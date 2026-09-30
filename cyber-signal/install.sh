#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir=$data_home/cyber-signal
command_dir=$prefix/bin
command_path=$command_dir/cyber-signal

if [ -L "$data_home" ] || [ -L "$config_home/systemd" ] || [ -L "$config_home/systemd/user" ] || [ -L "$config_home/cyber-signal" ] || [ -L "$command_dir" ]; then
    printf '%s\n' 'Refusing a symlinked cyber-signal data, systemd, or command directory.' >&2
    exit 1
fi
if [ -L "$app_dir" ]; then
    printf 'Refusing a symlinked application directory: %s\n' "$app_dir" >&2
    exit 1
fi
if [ -L "$app_dir/install.json" ] || [ -L "$app_dir/.cyber-signal-managed" ] || [ -L "$app_dir/src/cyber_signal" ]; then
    printf '%s\n' 'Refusing symlinked cyber-signal program or manifest files.' >&2
    exit 1
fi
managed_manifest=no
if [ -f "$app_dir/install.json" ] && grep -Fq "\"executable\":\"$command_path\"" "$app_dir/install.json"; then managed_manifest=yes; fi
if [ -L "$app_dir" ] || { [ -e "$app_dir" ] && [ ! -f "$app_dir/.cyber-signal-managed" ] && [ "$managed_manifest" != yes ]; }; then
    printf 'Refusing an unowned or symlinked application directory: %s\n' "$app_dir" >&2
    exit 1
fi
if [ -L "$command_path" ] || { [ -e "$command_path" ] && { [ ! -f "$command_path" ] || { ! grep -q '^# cyber-signal-managed-command$' "$command_path" && [ "$managed_manifest" != yes ]; }; }; }; then
    printf 'Refusing an unowned command or symlink: %s\n' "$command_path" >&2
    exit 1
fi
for target in "$config_home/cyber-signal/config.json" "$config_home/cyber-signal/active.mako"; do
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
        printf 'Refusing unsafe cyber-signal destination: %s\n' "$target" >&2
        exit 1
    fi
done
for unit_target in "$config_home/systemd/user/cyber-signal-network.service" "$config_home/systemd/user/cyber-signal-updates.service" "$config_home/systemd/user/cyber-signal-updates.timer" "$config_home/systemd/user/cyber-signal-disk.service" "$config_home/systemd/user/cyber-signal-disk.timer"; do
    if [ -e "$unit_target" ] && [ "$managed_manifest" != yes ] && ! grep -q '^# cyber-signal-managed-unit$' "$unit_target" 2>/dev/null; then
        printf 'Refusing to overwrite an unowned user unit: %s\n' "$unit_target" >&2
        exit 1
    fi
done

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
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
if [ -z "$project_dir" ] || [ ! -f "$project_dir/src/cyber_signal/cli.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-signal.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-signal.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-signal-install.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT HUP INT TERM
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
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

mkdir -p "$command_dir" "$app_dir/src" "$config_home/cyber-signal" "$config_home/systemd/user"
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
shared_theme_file=$config_home/cyber-ware/theme
if [ -f "$shared_theme_file" ]; then
    shared_theme=$(sed -n '1p' "$shared_theme_file")
    case "$shared_theme" in
        synthwave|greenline) theme=$shared_theme ;;
        *) printf 'Ignoring invalid shared cyber-ware theme in %s.\n' "$shared_theme_file" >&2 ;;
    esac
fi
install -m 644 "$app_dir/src/cyber_signal/themes/$theme.mako" "$config_home/cyber-signal/active.mako"

escape_sed() { printf '%s' "$1" | sed 's/[\\&#]/\\&/g'; }
exec_path=$(escape_sed "$prefix/bin/cyber-signal")
for template in "$project_dir"/systemd/user/*.in; do
    unit_name=$(basename "$template" .in)
    unit_target=$config_home/systemd/user/$unit_name
    [ ! -L "$unit_target" ] || { printf 'Refusing symlinked user unit: %s\n' "$unit_target" >&2; exit 1; }
    sed "s#@CYBER_SIGNAL_EXEC@#$exec_path#g" "$template" > "$unit_target"
done
printf '{"executable":"%s"}\n' "$prefix/bin/cyber-signal" > "$app_dir/install.json"
printf '%s\n' 'managed by cyber-signal installer' > "$app_dir/.cyber-signal-managed"
chmod 600 "$app_dir/install.json"
"$prefix/bin/cyber-signal" --theme "$theme" --no-reload

if ! command -v nmcli >/dev/null 2>&1; then
    printf '%s\n' 'Optional: nmcli is missing; network notifications need NetworkManager.' >&2
fi
if ! command -v checkupdates >/dev/null 2>&1; then
    printf '%s\n' 'Optional: checkupdates is missing; Arch update checks need pacman-contrib.' >&2
fi
printf 'Installed cyber-signal command in %s/bin\n' "$prefix"
printf 'Configuration: %s/cyber-signal/config.json\n' "$config_home"
printf 'User service units: %s/systemd/user\n' "$config_home"
printf '%s\n' 'The app-scoped theme was integrated without replacing your existing Mako settings.'
printf '%s\n' 'Enable monitoring with: cyber-signal --enable'
printf '%s\n' 'Uninstall with: cyber-signal --uninstall; add --purge to remove settings and saved state.'
