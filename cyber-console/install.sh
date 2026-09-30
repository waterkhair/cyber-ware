#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac

if [ -z "$project_dir" ] || [ ! -f "$project_dir/src/cyber_console/installer.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-console.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-console.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-console-install.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-console. Check that the public cyber-ware repository has a main branch.' >&2
        exit 1
    fi
    project_dir="$download_dir/cyber-console"
fi

if [ ! -f "$project_dir/src/cyber_console/installer.py" ]; then
    printf '%s\n' 'The cyber-console component was not found in the cyber-ware archive.' >&2
    exit 1
fi

PYTHONPATH="$project_dir/src${PYTHONPATH+:$PYTHONPATH}" python3 "$project_dir/src/cyber_console/installer.py"
