#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/cyber-ware-transaction-test.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/bin" "$tmp/home/.config/hypr/hyprland"
printf '#!/bin/sh\nexit 0\n' > "$tmp/bin/ghostty"
chmod +x "$tmp/bin/ghostty"
cat > "$tmp/bin/hyprctl" <<'EOF'
#!/bin/sh
case "$1" in
  version) printf '%s\n' 'Hyprland 0.56.2 test' ;;
  getoption) printf 'bool: %s\n' "${HYPRCTL_AUTORELOAD:-false}" ;;
  eval)
    printf '%s\n' "$2" >> "$HYPRCTL_TEST_STATE.calls"
    case "$2" in
      'assert(type(hl)'*)
        case "${INSTALL_TEST_MODE:-}" in
          legacy) printf '%s\n' 'eval is only supported with the lua config manager'; exit 0 ;;
          unreachable) exit 2 ;;
        esac ;;
      *'disable_autoreload = true'*)
        if [ "${INSTALL_TEST_MODE:-}" = pause-failure ]; then printf '%s\n' 'injected pause failure'; exit 0; fi ;;
      *cyber_ware_install_token*)
        if [ "${INSTALL_TEST_MODE:-}" = wrong-entrypoint ]; then printf '%s\n' 'cyber-ware entry point was not loaded'; exit 0; fi
        token=$(sed -n 's/^_G.cyber_ware_install_token = "\([^"]*\)"/\1/p' "$XDG_CONFIG_HOME/hypr/hyprland.lua")
        [ -n "$token" ] || exit 1
        case "$2" in *"'$token'"*) ;; *) exit 1 ;; esac ;;
    esac
    printf '%s\n' ok ;;
  configerrors)
    if [ -f "$HYPRCTL_TEST_STATE" ] && [ "${HYPRCTL_FAIL_VALIDATION:-no}" = yes ]; then printf '%s\n' 'injected config validation failure'; fi
    ;;
  reload) : > "$HYPRCTL_TEST_STATE"; printf '%s\n' ok ;;
  keyword) printf '%s\n' 'keyword cannot work with non-legacy parsers'; exit 0 ;;
  *) : ;;
esac
exit 0
EOF
chmod +x "$tmp/bin/hyprctl"
cat > "$tmp/bin/install" <<'EOF'
#!/bin/sh
last=
for arg do last=$arg; done
case "$INSTALL_TEST_MODE:$last" in
  copy-failure:*hyprland/keybindings.lua) exit 73 ;;
esac
exec /usr/bin/install "$@"
EOF
chmod +x "$tmp/bin/install"

config=$tmp/home/.config/hypr
printf '%s\n' 'old entry point' > "$config/hyprland.lua"
printf '%s\n' 'old module set' > "$config/hyprland/keybindings.lua"
printf '%s\n' 'monitor=HDMI-A-1,preferred,auto,1' > "$config/hyprland/monitors.lua"

run_install() {
    fail_validation=no
    [ "${1:-}" != validation-failure ] || fail_validation=yes
    env HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/home/.config" XDG_STATE_HOME="$tmp/home/.local/state" \
        PREFIX="$tmp/home/.local" PATH="$tmp/bin:/usr/bin:/bin" HYPRLAND_INSTANCE_SIGNATURE=test \
        HYPRCTL_TEST_STATE="$tmp/hyprctl-loaded" HYPRCTL_FAIL_VALIDATION="$fail_validation" INSTALL_TEST_MODE="${1:-}" \
        sh "$repo/install.sh" --no-components
}

if run_install copy-failure >/dev/null 2>&1; then
    printf '%s\n' 'Expected injected module copy failure.' >&2
    exit 1
fi
[ "$(cat "$config/hyprland.lua")" = 'old entry point' ]
[ "$(cat "$config/hyprland/keybindings.lua")" = 'old module set' ]
[ "$(cat "$config/hyprland/monitors.lua")" = 'monitor=HDMI-A-1,preferred,auto,1' ]
[ ! -e "$tmp/home/.local/state/cyber-ware/install.state" ]

rm -f "$tmp/hyprctl-loaded"
if run_install validation-failure >/dev/null 2>&1; then
    printf '%s\n' 'Expected injected configuration validation failure.' >&2
    exit 1
fi
[ "$(cat "$config/hyprland.lua")" = 'old entry point' ]
[ "$(cat "$config/hyprland/keybindings.lua")" = 'old module set' ]
[ "$(cat "$config/hyprland/monitors.lua")" = 'monitor=HDMI-A-1,preferred,auto,1' ]
[ ! -e "$tmp/home/.local/state/cyber-ware/install.state" ]

# A legacy session is rejected even with a misleading .lua file on disk.
# IPC errors with status 0 must not be mistaken for success either.
for failure in legacy unreachable pause-failure wrong-entrypoint; do
    rm -f "$tmp/hyprctl-loaded" "$tmp/hyprctl-loaded.calls"
    if run_install "$failure" >"$tmp/$failure.log" 2>&1; then
        printf 'Expected failure: %s\n' "$failure" >&2
        exit 1
    fi
    [ "$(cat "$config/hyprland.lua")" = 'old entry point' ]
    [ "$(cat "$config/hyprland/keybindings.lua")" = 'old module set' ]
    [ "$(cat "$config/hyprland/monitors.lua")" = 'monitor=HDMI-A-1,preferred,auto,1' ]
    [ ! -e "$tmp/home/.local/state/cyber-ware/install.state" ]
    case "$failure" in
      legacy|unreachable) grep -Fq 'running session must use' "$tmp/$failure.log"; [ ! -e "$tmp/hyprctl-loaded" ] ;;
      pause-failure) grep -Fq 'Cannot pause automatic reload' "$tmp/$failure.log"; [ ! -e "$tmp/hyprctl-loaded" ] ;;
      wrong-entrypoint) grep -Fq 'Hyprland did not load' "$tmp/$failure.log"; [ -e "$tmp/hyprctl-loaded" ] ;;
    esac
done

# A clean install must keep the explicit "no original" sentinel on upgrades.
clean_home=$tmp/clean
mkdir -p "$clean_home"
# A dormant legacy file must not override evidence from the running Lua parser.
mkdir -p "$clean_home/.config/hypr"
printf '%s\n' 'original legacy configuration' > "$clean_home/.config/hypr/hyprland.conf"
for pass in first second; do
    env HOME="$clean_home" XDG_CONFIG_HOME="$clean_home/.config" XDG_STATE_HOME="$clean_home/.local/state" \
        PREFIX="$clean_home/.local" PATH="$tmp/bin:/usr/bin:/bin" HYPRLAND_INSTANCE_SIGNATURE=test \
        HYPRCTL_TEST_STATE="$tmp/hyprctl-clean" HYPRCTL_FAIL_VALIDATION=no HYPRCTL_AUTORELOAD=true INSTALL_TEST_MODE= \
        sh "$repo/install.sh" --no-components >/dev/null 2>&1
    grep -Fxq 'backup_name=none' "$clean_home/.local/state/cyber-ware/install.state"
    [ "$(tail -n 1 "$tmp/hyprctl-clean.calls")" = 'hl.config({misc = {disable_autoreload = true}})' ]
    [ "$(cat "$clean_home/.config/hypr/hyprland.conf")" = 'original legacy configuration' ]
done

# Generated machine overrides retain their original hash over upgrades.
migration_home=$tmp/migration
mkdir -p "$migration_home/.config/hypr/hyprland"
printf '%s\n' 'return {}' > "$migration_home/.config/hypr/hyprland/environment.lua"
printf '%s\n' 'return {}' > "$migration_home/.config/hypr/hyprland/monitors.lua"
env HOME="$migration_home" XDG_CONFIG_HOME="$migration_home/.config" XDG_STATE_HOME="$migration_home/.local/state" \
    PREFIX="$migration_home/.local" PATH="$tmp/bin:/usr/bin:/bin" HYPRLAND_INSTANCE_SIGNATURE=test \
    HYPRCTL_TEST_STATE="$tmp/hyprctl-migration" HYPRCTL_FAIL_VALIDATION=no INSTALL_TEST_MODE= \
    sh "$repo/install.sh" --no-components >/dev/null 2>&1
local_file=$migration_home/.config/hypr/hyprland.local.lua
original_hash=$(sed -n 's/^local_config_sha256=//p' "$migration_home/.local/state/cyber-ware/install.state")
printf '%s\n' '-- user edit that must survive uninstall' >> "$local_file"
env HOME="$migration_home" XDG_CONFIG_HOME="$migration_home/.config" XDG_STATE_HOME="$migration_home/.local/state" \
    PREFIX="$migration_home/.local" PATH="$tmp/bin:/usr/bin:/bin" HYPRLAND_INSTANCE_SIGNATURE=test \
    HYPRCTL_TEST_STATE="$tmp/hyprctl-migration" HYPRCTL_FAIL_VALIDATION=no INSTALL_TEST_MODE= \
    sh "$repo/install.sh" --no-components >/dev/null 2>&1
[ "$(sed -n 's/^local_config_sha256=//p' "$migration_home/.local/state/cyber-ware/install.state")" = "$original_hash" ]
if command -v script >/dev/null 2>&1; then
    printf '%s\n' cyber-ware | env HOME="$migration_home" XDG_CONFIG_HOME="$migration_home/.config" \
        XDG_STATE_HOME="$migration_home/.local/state" PREFIX="$migration_home/.local" \
        PATH="$tmp/bin:/usr/bin:/bin" HYPRLAND_INSTANCE_SIGNATURE=test HYPRCTL_TEST_STATE="$tmp/hyprctl-migration" \
        script -q -e -c "$migration_home/.local/bin/cyber-ware --uninstall" /dev/null >/dev/null 2>&1
    grep -Fq 'user edit that must survive uninstall' "$local_file"
fi
printf '%s\n' 'PASS: failed module publication and config validation restore the prior desktop.'
printf '%s\n' 'PASS: reinstall preserves the no-original sentinel and edited machine overrides.'
printf '%s\n' 'PASS: actual Lua API required; IPC, pause and wrong-entrypoint failures are handled; prior autoreload preference preserved.'
