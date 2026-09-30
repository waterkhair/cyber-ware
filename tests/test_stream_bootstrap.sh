#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/cyber-ware-stream-test.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/bin" "$tmp/stale-checkout" "$tmp/home"
printf '%s\n' 'stale local checkout marker' > "$tmp/stale-checkout/hyprland.lua"
cat > "$tmp/bin/curl" <<'EOF'
#!/bin/sh
case "$*" in
  *api.github.com/repos/WaterKhair/cyber-ware/commits/main*) printf '%s\n' '{"sha":"0123456789abcdef0123456789abcdef01234567"}' ;;
  *github.com/WaterKhair/cyber-ware/archive/*) printf '%s\n' 'mock archive payload' ;;
  *) exit 2 ;;
esac
EOF
cat > "$tmp/bin/tar" <<'EOF'
#!/bin/sh
destination=
while [ "$#" -gt 0 ]; do
  if [ "$1" = -C ]; then shift; destination=$1; fi
  shift
done
[ -n "$destination" ] || exit 2
exec /bin/cp -a "$CYBER_WARE_TEST_SOURCE/." "$destination/"
EOF
cat > "$tmp/bin/hyprctl" <<'EOF'
#!/bin/sh
# No compositor is reachable from this TTY fixture.
exit 2
EOF
cat > "$tmp/bin/Hyprland" <<'EOF'
#!/bin/sh
[ "$1" = --version ] || exit 2
printf '%s\n' 'Hyprland 0.56.2 test'
EOF
chmod +x "$tmp/bin/curl" "$tmp/bin/tar" "$tmp/bin/hyprctl" "$tmp/bin/Hyprland"
(cd "$tmp/stale-checkout" && cat "$repo/install.sh" | env HOME="$tmp/home" \
    XDG_CONFIG_HOME="$tmp/home/.config" XDG_STATE_HOME="$tmp/home/.local/state" \
    PREFIX="$tmp/home/.local" PATH="$tmp/bin:/usr/bin:/bin" CYBER_WARE_TEST_SOURCE="$repo" \
    HYPRLAND_INSTANCE_SIGNATURE= sh -s -- --no-components)
grep -Fq 'cyber-ware Hyprland configuration' "$tmp/home/.config/hypr/hyprland.lua"
grep -Fq 'source_revision=0123456789abcdef0123456789abcdef01234567' "$tmp/home/.local/state/cyber-ware/install.state"
printf '%s\n' 'PASS: piped installer downloads the pinned remote revision instead of reading the working directory.'
