#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir" && pwd)
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
prefix=${PREFIX:-"${HOME}/.local"}
data_home=${XDG_DATA_HOME:-"${HOME}/.local/share"}
app_dir="$data_home/cyber-wall"
command_dir="$prefix/bin"
command_path="$command_dir/cyber-wall"
download_dir=
stage_dir=
cleanup() { [ -z "$download_dir" ] || rm -rf -- "$download_dir"; [ -z "$stage_dir" ] || rm -rf -- "$stage_dir"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ -L "$data_home" ] || [ -L "$command_dir" ]; then
    printf '%s\n' 'Refusing a symlinked cyber-wall data or command directory.' >&2
    exit 1
fi

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
command -v cmp >/dev/null 2>&1 || {
    printf '%s\n' 'Missing required installer command: cmp.' >&2
    exit 1
}

if ! command -v ffmpeg >/dev/null 2>&1; then
    printf '%s\n' 'Optional dependency ffmpeg is missing: video preview thumbnails will be unavailable.' >&2
fi
if ! command -v hyprctl >/dev/null 2>&1; then
    printf '%s\n' 'Optional dependency hyprctl is missing: set an explicit monitor name in config instead of output "auto".' >&2
fi

if [ -L "$app_dir" ] || { [ -e "$app_dir" ] && [ ! -f "$app_dir/.cyber-wall-managed" ]; }; then
    printf 'Refusing to replace an unowned or symlinked application directory: %s\n' "$app_dir" >&2
    exit 1
fi
if [ -L "$app_dir/.cyber-wall-managed" ] || [ -L "$app_dir/src" ] || [ -L "$app_dir/src/cyber_wall" ]; then
    printf '%s\n' 'Refusing symlinked cyber-wall marker or program directory.' >&2
    exit 1
fi
if [ -L "$command_path" ] || { [ -e "$command_path" ] && { [ ! -f "$command_path" ] || ! grep -q '^# cyber-wall-managed-command$' "$command_path"; }; }; then
    printf 'Refusing to replace an unowned command or symlink: %s\n' "$command_path" >&2
    exit 1
fi

# Support both ./install.sh from a clone and curl | sh. When no source tree is
# beside this script, fetch the public default-branch archive into a temp dir.
if [ -z "$project_dir" ] || [ ! -f "$project_dir/src/cyber_wall/picker.py" ]; then
    command -v curl >/dev/null 2>&1 || {
        printf '%s\n' 'curl is required to download cyber-wall.' >&2
        exit 1
    }
    command -v tar >/dev/null 2>&1 || {
        printf '%s\n' 'tar is required to unpack cyber-wall.' >&2
        exit 1
    }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-wall-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
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

wallpaper_dir=$HOME/Pictures/Wallpapers
wallpaper_source_dir=$project_dir/assets/wallpapers
wallpaper_files='city-tijuana.png cozy-husky-bay.png calm-water.png'
retired_wallpaper_files='cozy-husky-coding.png cozy-husky-pool.png cyberpunk-husky.png'
if [ ! -d "$wallpaper_source_dir" ]; then
    printf 'Bundled wallpaper source directory is missing: %s\n' "$wallpaper_source_dir" >&2
    exit 1
fi
if [ -L "$HOME/Pictures" ] || [ -L "$wallpaper_dir" ] || \
    { [ -e "$wallpaper_dir" ] && [ ! -d "$wallpaper_dir" ]; }; then
    printf 'Refusing an unsafe wallpaper destination: %s\n' "$wallpaper_dir" >&2
    exit 1
fi
for wallpaper in $wallpaper_files; do
    source_file=$wallpaper_source_dir/$wallpaper
    destination_file=$wallpaper_dir/$wallpaper
    [ -f "$source_file" ] || { printf 'Bundled wallpaper is missing: %s\n' "$source_file" >&2; exit 1; }
    if [ -L "$destination_file" ] || { [ -e "$destination_file" ] && [ ! -f "$destination_file" ]; }; then
        printf 'Refusing an unsafe wallpaper file: %s\n' "$destination_file" >&2
        exit 1
    fi
    if [ -f "$destination_file" ] && ! cmp -s -- "$source_file" "$destination_file"; then
        printf 'A different file already exists at %s; move it before installing cyber-wall.\n' "$destination_file" >&2
        exit 1
    fi
done

mkdir -p "$command_dir" "$(dirname -- "$app_dir")"
stage_dir=$(mktemp -d "$(dirname -- "$app_dir")/.cyber-wall-stage.XXXXXX")
cp -R "$project_dir/src/cyber_wall" "$stage_dir/cyber_wall"
: > "$stage_dir/.cyber-wall-managed"
mkdir -p "$app_dir/src"
if [ -e "$app_dir/src/cyber_wall" ]; then mv "$app_dir/src/cyber_wall" "$stage_dir/previous"; fi
if ! mv "$stage_dir/cyber_wall" "$app_dir/src/cyber_wall"; then
    [ ! -e "$stage_dir/previous" ] || mv "$stage_dir/previous" "$app_dir/src/cyber_wall"
    printf '%s\n' 'Could not publish cyber-wall code; the previous program was restored.' >&2
    exit 1
fi
[ ! -e "$stage_dir/previous" ] || rm -rf -- "$stage_dir/previous"
[ -f "$app_dir/.cyber-wall-managed" ] || mv "$stage_dir/.cyber-wall-managed" "$app_dir/.cyber-wall-managed"
install -m 755 "$project_dir/bin/cyber-wall" "$command_path"

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/cyber-wall"
if [ -L "$config_dir" ]; then
    printf 'Refusing a symlinked configuration directory: %s\n' "$config_dir" >&2
    exit 1
fi
if [ -L "$config_dir/config.json" ] || { [ -e "$config_dir/config.json" ] && [ ! -f "$config_dir/config.json" ]; }; then
    printf 'Refusing unsafe cyber-wall config destination: %s/config.json\n' "$config_dir" >&2
    exit 1
fi
mkdir -p "$config_dir"
mkdir -p "$wallpaper_dir"
for wallpaper in $wallpaper_files; do
    destination_file=$wallpaper_dir/$wallpaper
    if [ ! -e "$destination_file" ]; then
        install -m 644 "$wallpaper_source_dir/$wallpaper" "$destination_file"
    fi
done
if [ ! -e "$config_dir/config.json" ]; then
    install -m 600 "$project_dir/config.example.json" "$config_dir/config.json"
fi

# Retire only unmodified copies from the previous bundled set. User-edited
# versions and unrelated wallpapers are personal files and must be preserved.
if command -v sha256sum >/dev/null 2>&1; then
    for wallpaper in $retired_wallpaper_files; do
        case "$wallpaper" in
            cozy-husky-coding.png) expected_hash=01c2c0f2e1ba19e8443f427f92235b379c9e351d98835301d2ac73a1ac6fdf46 ;;
            cozy-husky-pool.png) expected_hash=f67fdf1d68a53f0741382a027edf0d8698431cb7ffa2376549e694de9589660f ;;
            cyberpunk-husky.png) expected_hash=dc19ff07fbead95c6d79575067202abe5f0a00547528bf9a8c1d389d34354cac ;;
        esac
        retired_path=$wallpaper_dir/$wallpaper
        if [ -f "$retired_path" ] && [ ! -L "$retired_path" ]; then
            actual_hash=$(sha256sum -- "$retired_path" | cut -d ' ' -f 1)
            if [ "$actual_hash" = "$expected_hash" ]; then
                rm -f -- "$retired_path"
                printf 'Removed retired bundled wallpaper: %s\n' "$retired_path"
            fi
        fi
    done
fi

shared_theme_file="${XDG_CONFIG_HOME:-$HOME/.config}/cyber-ware/theme"
if [ -f "$shared_theme_file" ]; then
    shared_theme=$(sed -n '1p' "$shared_theme_file")
    case "$shared_theme" in
        synthwave|greenline|husky)
            PYTHONDONTWRITEBYTECODE=1 CYBER_WALL_CONFIG="$config_dir/config.json" "$prefix/bin/cyber-wall" --theme "$shared_theme"
            ;;
        *) printf 'Ignoring invalid shared cyber-ware theme in %s.\n' "$shared_theme_file" >&2 ;;
    esac
fi

printf 'Installed cyber-wall commands in %s/bin\n' "$prefix"
printf 'Configuration: %s/config.json\n' "$config_dir"
printf 'Bundled wallpapers: %s\n' "$wallpaper_dir"
printf '%s\n' 'Uninstall with cyber-wall --uninstall; add --purge only if you also want to remove cyber-wall settings and saved data.'
printf '%s\n' 'Make sure the install bin directory is on PATH. Start with: cyber-wall'
