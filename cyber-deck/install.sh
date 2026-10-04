#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
app_dir=$data_home/cyber-deck
config_dir=$config_home/cyber-deck
command_dir=$prefix/bin
command_path=$command_dir/cyber-deck
download_dir=

cleanup() { [ -z "$download_dir" ] || rm -rf -- "$download_dir"; }
trap cleanup EXIT HUP INT TERM

for directory in "$data_home" "$config_home" "$command_dir"; do
    if [ -L "$directory" ]; then
        printf 'Refusing a symlinked install directory: %s\n' "$directory" >&2
        exit 1
    fi
done
if [ -L "$app_dir" ] || { [ -e "$app_dir" ] && [ ! -f "$app_dir/.cyber-deck-managed" ]; }; then
    printf 'Refusing an unowned or symlinked application directory: %s\n' "$app_dir" >&2
    exit 1
fi
if [ -L "$config_dir" ] || { [ -e "$config_dir" ] && [ ! -d "$config_dir" ]; }; then
    printf 'Refusing an unsafe configuration directory: %s\n' "$config_dir" >&2
    exit 1
fi
for target in "$app_dir/.cyber-deck-managed" "$app_dir/src" "$app_dir/src/cyber_deck"; do
    if [ -L "$target" ]; then
        printf 'Refusing a symlinked cyber-deck program path: %s\n' "$target" >&2
        exit 1
    fi
done
if [ -L "$command_path" ] || { [ -e "$command_path" ] && { [ ! -f "$command_path" ] || ! grep -q '^# cyber-deck-managed-command$' "$command_path"; }; }; then
    printf 'Refusing to replace an unowned command or symlink: %s\n' "$command_path" >&2
    exit 1
fi
for target in "$config_dir/theme" "$config_dir/themes" "$config_dir/themes/synthwave.ini" "$config_dir/themes/greenline.ini"; do
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ] && [ "$target" != "$config_dir/themes" ]; }; then
        printf 'Refusing an unsafe configuration destination: %s\n' "$target" >&2
        exit 1
    fi
done
command -v python3 >/dev/null 2>&1 || { printf '%s\n' 'Missing required dependency: python3.' >&2; exit 1; }
command -v fuzzel >/dev/null 2>&1 || { printf '%s\n' 'Missing required dependency: fuzzel. Install it with your distribution package manager first.' >&2; exit 1; }

if [ -z "$project_dir" ] || [ ! -f "$project_dir/src/cyber_deck/cli.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-deck.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-deck.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-deck-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" -o "$download_dir/source.tar.gz" || \
       ! tar -xzf "$download_dir/source.tar.gz" --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-deck. Check that cyber-ware is public and has a main branch.' >&2
        exit 1
    fi
    project_dir=$download_dir/cyber-deck
    [ -f "$project_dir/src/cyber_deck/cli.py" ] || { printf '%s\n' 'The cyber-deck component was not found in the cyber-ware archive.' >&2; exit 1; }
fi

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$project_dir/src" CYBER_DECK_HOME="$app_dir" python3 -m cyber_deck.installer "$project_dir"
if [ -n "${revision:-}" ]; then printf 'Source revision: %s\n' "$revision"; fi
