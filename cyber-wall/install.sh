#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir" && pwd)
prefix=${PREFIX:-"${HOME}/.local"}
data_home=${XDG_DATA_HOME:-"${HOME}/.local/share"}
app_dir="$data_home/cyber-wall"

missing_required=0
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: python3.' >&2
    missing_required=1
elif ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: GTK 4 Python bindings (PyGObject). Install gtk4 and python-gobject.' >&2
    missing_required=1
fi
if ! command -v mpvpaper >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: mpvpaper. Install it with your distribution package manager first.' >&2
    missing_required=1
fi
if [ "$missing_required" -ne 0 ]; then
    printf '%s\n' 'cyber-wall was not installed. See the README Requirements section for dependency details.' >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    printf '%s\n' 'Optional dependency ffmpeg is missing: video preview thumbnails will be unavailable.' >&2
fi
if ! command -v hyprctl >/dev/null 2>&1; then
    printf '%s\n' 'Optional dependency hyprctl is missing: set an explicit monitor name in config instead of output "auto".' >&2
fi

# Support both ./install.sh from a clone and curl | sh. When no source tree is
# beside this script, fetch the public default-branch archive into a temp dir.
if [ ! -f "$project_dir/src/cyber_wall/picker.py" ]; then
    command -v curl >/dev/null 2>&1 || {
        printf '%s\n' 'curl is required to download cyber-wall.' >&2
        exit 1
    }
    command -v tar >/dev/null 2>&1 || {
        printf '%s\n' 'tar is required to unpack cyber-wall.' >&2
        exit 1
    }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-wall-install.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT
    if ! curl -fsSL 'https://github.com/WaterKhair/cyber-ware/archive/refs/heads/main.tar.gz' \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-wall. Check that the public repository has a commit on its main branch.' >&2
        exit 1
    fi
    project_dir="$download_dir/cyber-wall"
    if [ ! -f "$project_dir/src/cyber_wall/picker.py" ]; then
        printf '%s\n' 'The cyber-wall component was not found in the cyber-ware archive.' >&2
        exit 1
    fi
fi

mkdir -p "$prefix/bin" "$app_dir/src"
# Replace only cyber-wall-owned application files; preserve config and state.
rm -rf -- "$app_dir/src/cyber_wall" "$app_dir/bin"
cp -R "$project_dir/src/cyber_wall" "$app_dir/src/"
install -m 755 "$project_dir/bin/cyber-wall" "$prefix/bin/cyber-wall"
# Remove obsolete entry points from installations made by earlier versions.
rm -f -- "$prefix/bin/cyber-wall-set" "$prefix/bin/cyber-wall-toggle" "$prefix/bin/cyber-wall-uninstall"

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/cyber-wall"
mkdir -p "$config_dir"
if [ ! -e "$config_dir/config.json" ]; then
    install -m 600 "$project_dir/config.example.json" "$config_dir/config.json"
fi

shared_theme_file="${XDG_CONFIG_HOME:-$HOME/.config}/cyber-ware/theme"
if [ -f "$shared_theme_file" ]; then
    shared_theme=$(sed -n '1p' "$shared_theme_file")
    case "$shared_theme" in
        synthwave|greenline)
            CYBER_WALL_CONFIG="$config_dir/config.json" "$prefix/bin/cyber-wall" --theme "$shared_theme"
            ;;
        *) printf 'Ignoring invalid shared cyber-ware theme in %s.\n' "$shared_theme_file" >&2 ;;
    esac
fi

printf 'Installed cyber-wall commands in %s/bin\n' "$prefix"
printf 'Configuration: %s/config.json\n' "$config_dir"
printf '%s\n' 'Uninstall with cyber-wall --uninstall; add --purge only if you also want to remove cyber-wall settings and saved data.'
printf '%s\n' 'Make sure the install bin directory is on PATH. Start with: cyber-wall'
