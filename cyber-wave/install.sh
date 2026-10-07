#!/bin/sh
set -eu

script_name=${0##*/}
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
download_dir=
cleanup() { [ -z "$download_dir" ] || rm -rf -- "$download_dir"; }
trap cleanup EXIT HUP INT TERM

if [ -z "$project_dir" ] || [ ! -f "$project_dir/src/cyber_wave/installer.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-wave.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-wave.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-wave-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" -o "$download_dir/source.tar.gz" || \
       ! tar -xzf "$download_dir/source.tar.gz" --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-wave from cyber-ware main.' >&2
        exit 1
    fi
    project_dir=$download_dir/cyber-wave
fi
[ -f "$project_dir/src/cyber_wave/installer.py" ] || { printf '%s\n' 'cyber-wave sources are incomplete.' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf '%s\n' 'Missing dependency: python3.' >&2; exit 1; }
for dependency in hyprctl mpv; do
    command -v "$dependency" >/dev/null 2>&1 || { printf 'Missing dependency: %s. Install it with your distribution package manager first.\n' "$dependency" >&2; exit 1; }
done
if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' >/dev/null 2>&1; then
    printf '%s\n' 'Missing required dependency: GTK 4 Python bindings. Install gtk4 and python-gobject with your distribution package manager first.' >&2
    exit 1
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$project_dir/src" python3 -m cyber_wave.installer "$project_dir"
[ -z "${revision:-}" ] || printf 'Source revision: %s\n' "$revision"
