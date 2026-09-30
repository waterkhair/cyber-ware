#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/cyber-ware-autostart-test.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/home/.local/bin"
TEST_HOME="$tmp/home" TEST_REPO="$repo" lua "$repo/tests/test_autostart.lua"
