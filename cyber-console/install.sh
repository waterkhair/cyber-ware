#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir

if [ ! -f "$project_dir/src/cyber_console/installer.py" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-console.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-console.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-console-install.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT
    if ! curl -fsSL 'https://github.com/WaterKhair/cyber-ware/archive/refs/heads/main.tar.gz' \
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
