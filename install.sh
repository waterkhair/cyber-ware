#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_dir=$script_dir
download_dir=
local_config_tmp=
cleanup() {
    [ -z "$download_dir" ] || rm -rf -- "$download_dir"
    [ -z "$local_config_tmp" ] || rm -f -- "$local_config_tmp"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

mode=prompt
case "${1:-}" in
    "") ;;
    --all) mode=all ;;
    --no-components) mode=none ;;
    --help|-h)
        cat <<'EOF'
Usage: ./install.sh [--all | --no-components]

Install the modular Hyprland configuration, then choose optional components.
  --all            install every component without prompting
  --no-components  install only the Hyprland configuration
EOF
        exit 0
        ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { printf '%s\n' 'Use at most one option.' >&2; exit 2; }

if [ ! -f "$source_dir/hyprland/hyprland.lua" ] || [ ! -d "$source_dir/cyber-wall" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-ware.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-ware.' >&2; exit 1; }
    command -v mktemp >/dev/null 2>&1 || { printf '%s\n' 'mktemp is required to download cyber-ware safely.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-ware-install.XXXXXX")
    if ! curl -fsSL 'https://github.com/WaterKhair/cyber-ware/archive/refs/heads/main.tar.gz' \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download the cyber-ware main branch.' >&2
        exit 1
    fi
    source_dir=$download_dir
fi

for file in hyprland/hyprland.lua hyprland/appearance.lua hyprland/windows.lua \
    hyprland/autostart.lua hyprland/keybindings.lua; do
    [ -f "$source_dir/$file" ] || { printf 'Required config file is missing: %s\n' "$file" >&2; exit 1; }
done
for component in cyber-wall cyber-signal cyber-panel cyber-console cyber-jackout cyber-scan; do
    [ -f "$source_dir/$component/install.sh" ] || {
        printf 'Component installer is missing: %s/install.sh\n' "$component" >&2
        exit 1
    }
done

config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
hypr_dir=$config_home/hypr
module_dir=$hypr_dir/hyprland
main_config=$hypr_dir/hyprland.lua
case "$config_home" in /|"") printf '%s\n' 'Refusing an unsafe configuration directory.' >&2; exit 1 ;; esac
case "$state_home" in /|"") printf '%s\n' 'Refusing an unsafe state directory.' >&2; exit 1 ;; esac
if [ -L "$main_config" ] || [ -L "$module_dir" ]; then
    printf '%s\n' 'Refusing to replace a symlinked Hyprland config target.' >&2
    exit 1
fi
if [ -e "$main_config" ] && [ ! -f "$main_config" ]; then
    printf 'Refusing to replace a non-file config target: %s\n' "$main_config" >&2
    exit 1
fi
for file in appearance.lua windows.lua autostart.lua keybindings.lua; do
    target=$module_dir/$file
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
        printf 'Refusing to replace an unsafe module target: %s\n' "$target" >&2
        exit 1
    fi
done

for command in chmod cp date mkdir mktemp mv rm; do
    command -v "$command" >/dev/null 2>&1 || { printf 'Required installer command missing: %s\n' "$command" >&2; exit 1; }
done

backup_parent=$state_home/cyber-ware/backups
backup_dir=
if [ -e "$main_config" ] || [ -e "$module_dir" ]; then
    mkdir -p "$backup_parent"
    backup_dir=$(mktemp -d "$backup_parent/hyprland-$(date +%Y%m%d-%H%M%S).XXXXXX")
    [ ! -e "$main_config" ] || cp -a -- "$main_config" "$backup_dir/"
    [ ! -e "$module_dir" ] || cp -a -- "$module_dir" "$backup_dir/"
fi

local_config=$hypr_dir/hyprland.local.lua
migrate_env=no
migrate_monitor=no
if [ ! -e "$local_config" ] && [ ! -L "$local_config" ]; then
    [ ! -f "$module_dir/environment.lua" ] || [ -L "$module_dir/environment.lua" ] || migrate_env=yes
    [ ! -f "$module_dir/monitors.lua" ] || [ -L "$module_dir/monitors.lua" ] || migrate_monitor=yes
fi

mkdir -p "$module_dir"
cp -- "$source_dir/hyprland/hyprland.lua" "$main_config"
for file in appearance.lua windows.lua autostart.lua keybindings.lua; do
    cp -- "$source_dir/hyprland/$file" "$module_dir/$file"
done
if [ "$migrate_env" = yes ] || [ "$migrate_monitor" = yes ]; then
    local_config_tmp=$(mktemp "$hypr_dir/.hyprland.local.lua.XXXXXX")
    {
        printf '%s\n' '-- Migrated by cyber-ware from your previous modular Hyprland config.'
        [ "$migrate_env" != yes ] || printf '%s\n' 'require("hyprland.environment")'
        [ "$migrate_monitor" != yes ] || printf '%s\n' 'require("hyprland.monitors")'
    } > "$local_config_tmp"
    chmod 644 "$local_config_tmp"
    mv -- "$local_config_tmp" "$local_config"
    local_config_tmp=
    printf '%s\n' 'Preserved existing environment/monitor modules through hyprland.local.lua.'
fi
printf 'Installed the cyber-ware Hyprland config in %s\n' "$hypr_dir"
if [ -n "$backup_dir" ]; then
    printf 'Previous config files backed up to %s\n' "$backup_dir"
else
    printf '%s\n' 'No previous Hyprland entry point or module directory needed backing up.'
fi
if [ "$migrate_env" != yes ] && [ "$migrate_monitor" != yes ]; then
    printf '%s\n' 'Existing hyprland.local.lua machine overrides were left untouched.'
fi

if [ -t 0 ]; then
    prompt_source=stdin
elif (exec 3</dev/tty) 2>/dev/null; then
    prompt_source=tty
else
    prompt_source=none
fi
if [ "$mode" = prompt ] && [ "$prompt_source" = none ]; then
    printf '%s\n' 'No terminal is available for component prompts; skipping optional components.'
    printf '%s\n' 'Use --all or --no-components to choose non-interactively.'
    mode=none
fi

failures=
install_component() {
    component=$1
    if [ "$mode" = all ]; then
        answer=y
    elif [ "$mode" = none ]; then
        answer=n
    else
        printf 'Install optional %s? [y/N] ' "$component"
        if [ "$prompt_source" = tty ]; then
            IFS= read -r answer </dev/tty || answer=
        else
            IFS= read -r answer || answer=
        fi
    fi
    case "$answer" in
        y|Y|yes|YES)
            printf '\nInstalling %s...\n' "$component"
            if (CDPATH= cd -- "$source_dir/$component" && sh ./install.sh); then
                printf 'Installed %s.\n\n' "$component"
            else
                printf 'Installation failed for %s; see its README for requirements. Continuing.\n\n' "$component" >&2
                failures="$failures $component"
            fi
            ;;
        *) printf 'Skipped %s.\n\n' "$component" ;;
    esac
}

for component in cyber-wall cyber-signal cyber-console cyber-panel cyber-jackout cyber-scan; do
    install_component "$component"
done

printf '%s\n' 'The config detects installed optional commands when Hyprland loads.'
printf '%s\n' 'Reload from Hyprland with: hyprctl reload'
printf '%s\n' 'System packages are not installed by this script; each component checks its own requirements.'
if [ -n "$failures" ]; then
    printf 'These component installs failed:%s\n' "$failures" >&2
    exit 1
fi
