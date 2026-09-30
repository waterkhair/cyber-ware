#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
download_dir=
stage_dir=
cleanup() {
    [ -z "$stage_dir" ] || rm -rf -- "$stage_dir"
    [ -z "$download_dir" ] || rm -rf -- "$download_dir"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

if [ -z "$project_dir" ] || [ ! -f "$project_dir/bin/cyber-scan" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-scan.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-scan.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-scan-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-scan. Check that cyber-ware has a public main branch.' >&2
        exit 1
    fi
    project_dir="$download_dir/cyber-scan"
fi

[ -f "$project_dir/bin/cyber-scan" ] || { printf '%s\n' 'cyber-scan source was not found.' >&2; exit 1; }

for command in bash chmod cp dirname ln mkdir mktemp mv readlink rm; do
    command -v "$command" >/dev/null 2>&1 || { printf 'Required installer command missing: %s\n' "$command" >&2; exit 1; }
done
for command in grim slurp swappy; do
    command -v "$command" >/dev/null 2>&1 || {
        printf 'Missing required dependency: %s\n' "$command" >&2
        printf '%s\n' 'Install grim, slurp, and swappy with your distribution package manager first.' >&2
        exit 1
    }
done

prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
app_dir="$data_home/cyber-scan"
command_dir="$prefix/bin"
command_path="$command_dir/cyber-scan"
case "$command_dir" in
    /bin|/usr/bin|/usr/local/bin)
        printf 'Refusing to install a user command into system directory %s.\n' "$command_dir" >&2
        exit 1
        ;;
esac
case "$app_dir" in
    /cyber-scan|/)
        printf 'Refusing unsafe application data directory %s.\n' "$app_dir" >&2
        exit 1
        ;;
esac

if [ -e "$command_path" ] || [ -L "$command_path" ]; then
    if [ ! -L "$command_path" ] || [ "$(readlink -f -- "$command_path" 2>/dev/null || true)" != "$app_dir/bin/cyber-scan" ]; then
        printf 'Refusing to overwrite existing file: %s\n' "$command_path" >&2
        exit 1
    fi
fi
if [ -L "$app_dir" ] || { [ -e "$app_dir" ] && [ ! -f "$app_dir/.cyber-scan-managed" ]; }; then
    printf 'Refusing to overwrite unrecognized or unsafe data directory: %s\n' "$app_dir" >&2
    exit 1
fi

mkdir -p "$command_dir" "$(dirname -- "$app_dir")"
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-scan-stage.XXXXXX")
cp -R "$project_dir/." "$stage_dir/"
chmod 755 "$stage_dir/bin/cyber-scan"
: > "$stage_dir/.cyber-scan-managed"
if [ -e "$app_dir" ]; then
    rm -rf -- "$app_dir"
fi
mv "$stage_dir" "$app_dir"
stage_dir=
ln -sfn "$app_dir/bin/cyber-scan" "$command_path"

printf 'Installed cyber-scan in %s\n' "$app_dir"
printf 'Command: %s\n' "$command_path"
printf '%s\n' 'Run cyber-scan --check to verify dependencies.'
printf '%s\n' 'The installer does not edit Hyprland or Swappy configuration.'
