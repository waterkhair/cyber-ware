#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_dir=$script_dir
revision=unknown
case "$script_name" in sh|bash|dash|-sh|-bash) source_dir= ;; esac
download_dir=
local_config_tmp=
stage_dir=
transaction_dir=
publish_started=no
install_complete=no
autoreload_paused=no
previous_autoreload=false

# hyprctl can return exit status 0 for an IPC error. Check its reply as well.
hypr_request() {
    reply=$(hyprctl "$@" 2>&1) || { printf '%s\n' "$reply" >&2; return 1; }
    [ "$reply" = ok ] || { printf '%s\n' "$reply" >&2; return 1; }
}
set_autoreload() {
    hypr_request eval "hl.config({misc = {disable_autoreload = $1}})"
}
cleanup() {
    result=$?
    if [ "$publish_started" = yes ] && [ "$install_complete" != yes ] && [ -n "$transaction_dir" ]; then
        # A failed explicit reload may have re-enabled the file watcher.
        if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then set_autoreload true || :; fi
        if [ -e "$transaction_dir/modules" ]; then rm -rf "$hypr_dir/hyprland"; cp -a "$transaction_dir/modules" "$hypr_dir/hyprland"; else rm -rf "$hypr_dir/hyprland"; fi
        if [ -e "$transaction_dir/local" ]; then cp -a "$transaction_dir/local" "$hypr_dir/hyprland.local.lua"; elif [ -e "$transaction_dir/local-absent" ]; then rm -f "$hypr_dir/hyprland.local.lua"; fi
        if [ -e "$transaction_dir/state" ]; then cp -a "$transaction_dir/state" "$install_state"; elif [ -e "$transaction_dir/state-absent" ]; then rm -f "$install_state"; fi
        if [ -e "$transaction_dir/bin-path" ]; then cp -a "$transaction_dir/bin-path" "$bin_path_file"; else rm -f "$bin_path_file"; fi
        if [ -e "$transaction_dir/theme" ]; then cp -a "$transaction_dir/theme" "$theme_file"; elif [ -e "$transaction_dir/theme-absent" ]; then rm -f "$theme_file"; fi
        if [ -e "$transaction_dir/command" ]; then cp -a "$transaction_dir/command" "$command_path"; else rm -f "$command_path"; fi
        if [ -e "$transaction_dir/main" ]; then cp -a "$transaction_dir/main" "$hypr_dir/hyprland.lua"; else rm -f "$hypr_dir/hyprland.lua"; fi
        if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
            hypr_request reload || printf '%s\n' 'Previous files restored, but Hyprland could not reload them; run hyprctl reload.' >&2
        fi
    fi
    if [ "$autoreload_paused" = yes ]; then
        set_autoreload "$previous_autoreload" || printf '%s\n' 'Could not restore the previous automatic-reload setting.' >&2
    fi
    [ -z "$download_dir" ] || rm -rf -- "$download_dir"
    [ -z "$local_config_tmp" ] || rm -f -- "$local_config_tmp"
    [ -z "$stage_dir" ] || rm -rf -- "$stage_dir"
    [ -z "$transaction_dir" ] || rm -rf -- "$transaction_dir"
    return "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

mode=prompt
if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run cyber-ware as your regular desktop user; only package installation uses sudo.' >&2
    exit 1
fi
case "${1:-}" in
    "") ;;
    --all) mode=all ;;
    --no-components) mode=none ;;
    --help|-h)
        cat <<'EOF'
Usage: ./install.sh [--all | --no-components]

Choose components, install their system packages, and configure the desktop.
  --all            select every component (sudo/pacman may still prompt)
  --no-components  install the base desktop without optional components
EOF
        exit 0
        ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { printf '%s\n' 'Use at most one option.' >&2; exit 2; }

if [ -z "$source_dir" ] || [ ! -f "$source_dir/hyprland/hyprland.lua" ] || [ ! -d "$source_dir/cyber-wall" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-ware.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-ware.' >&2; exit 1; }
    command -v mktemp >/dev/null 2>&1 || { printf '%s\n' 'mktemp is required to download cyber-ware safely.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-ware-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve the cyber-ware main revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download the cyber-ware main branch.' >&2
        exit 1
    fi
    source_dir=$download_dir
else
    revision=$(git -C "$source_dir" rev-parse HEAD 2>/dev/null || printf '%s' unknown)
    if [ "$revision" != unknown ] && ! git -C "$source_dir" diff --quiet --ignore-submodules HEAD -- 2>/dev/null; then
        revision=$revision-dirty
    fi
fi

for file in hyprland/hyprland.lua hyprland/appearance.lua hyprland/windows.lua \
    hyprland/autostart.lua hyprland/keybindings.lua hyprland/session-start.sh bin/cyber-ware packages/arch.sh packages/install.sh desktop/manage.py; do
    [ -f "$source_dir/$file" ] || { printf 'Required config file is missing: %s\n' "$file" >&2; exit 1; }
done
for component in cyber-wall cyber-signal cyber-panel cyber-console cyber-jackout cyber-scan cyber-deck cyber-wave; do
    [ -f "$source_dir/$component/install.sh" ] || {
        printf 'Component installer is missing: %s/install.sh\n' "$component" >&2
        exit 1
    }
done

# Select components before touching active Hyprland files.
if [ -t 0 ]; then prompt_source=stdin
elif (exec 3</dev/tty) 2>/dev/null; then prompt_source=tty
else prompt_source=none; fi
if [ "$mode" = prompt ] && [ "$prompt_source" = none ]; then
    printf '%s\n' 'No terminal is available for optional component prompts; skipping them.'
    mode=none
fi
selected_components=
for component in cyber-wall cyber-signal cyber-console cyber-panel cyber-jackout cyber-scan cyber-deck cyber-wave; do
    if [ "$mode" = all ]; then answer=y
    elif [ "$mode" = none ]; then answer=n
    else
        printf 'Install optional %s? [y/N] ' "$component"
        if [ "$prompt_source" = tty ]; then IFS= read -r answer </dev/tty || answer=
        else IFS= read -r answer || answer=; fi
    fi
    case "$answer" in y|Y|yes|YES) selected_components="$selected_components $component" ;; esac
done

config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
prefix=${PREFIX:-"$HOME/.local"}
command_dir=$prefix/bin
command_path=$command_dir/cyber-ware
theme_file=$config_home/cyber-ware/theme
bin_path_file=$config_home/cyber-ware/bin-path
install_state=$state_home/cyber-ware/install.state
hypr_dir=$config_home/hypr
module_dir=$hypr_dir/hyprland
main_config=$hypr_dir/hyprland.lua
case "$config_home" in /|"") printf '%s\n' 'Refusing an unsafe configuration directory.' >&2; exit 1 ;; esac
case "$state_home" in /|"") printf '%s\n' 'Refusing an unsafe state directory.' >&2; exit 1 ;; esac
case "$prefix" in /|"") printf '%s\n' 'Refusing an unsafe command prefix.' >&2; exit 1 ;; esac
if [ -L "$hypr_dir" ] || [ -L "$state_home/cyber-ware" ] || [ -L "$state_home/cyber-ware/install.state" ] || [ -L "$command_dir" ]; then
    printf '%s\n' 'Refusing symlinked Hyprland or cyber-ware state destinations.' >&2
    exit 1
fi
if [ -L "$hypr_dir/hyprland.local.lua" ] || [ -L "$state_home/cyber-ware/backups" ]; then
    printf '%s\n' 'Refusing symlinked local-override or backup destinations.' >&2
    exit 1
fi
command -v sed >/dev/null 2>&1 || { printf '%s\n' 'Required installer command missing: sed' >&2; exit 1; }
if [ -L "$command_path" ] || { [ -e "$command_path" ] && { [ ! -f "$command_path" ] || [ "$(sed -n '2p' "$command_path")" != '# cyber-ware-managed-cli' ]; }; }; then
    printf 'Refusing to replace an unrelated command: %s\n' "$command_path" >&2
    exit 1
fi
if [ -L "$theme_file" ] || { [ -e "$theme_file" ] && [ ! -f "$theme_file" ]; }; then
    printf 'Refusing to replace an unsafe theme file: %s\n' "$theme_file" >&2
    exit 1
fi
if [ -L "$bin_path_file" ] || { [ -e "$bin_path_file" ] && [ ! -f "$bin_path_file" ]; }; then
    printf 'Refusing to replace an unsafe command-path file: %s\n' "$bin_path_file" >&2
    exit 1
fi
if [ -f "$theme_file" ]; then
    selected_theme=$(sed -n '1p' "$theme_file")
    case "$selected_theme" in synthwave|greenline|husky) ;; *) printf 'Invalid shared theme in %s\n' "$theme_file" >&2; exit 1 ;; esac
fi
initial_backup_name=
created_local_config=no
existing_install=no
local_hash_legacy_unknown=no
preserved_local_hash=
if [ -f "$install_state" ] && { [ "$(sed -n '1p' "$install_state")" = 'version=1' ] || [ "$(sed -n '1p' "$install_state")" = 'version=2' ]; }; then
    existing_install=yes
    state_version=$(sed -n '1p' "$install_state")
    initial_backup_name=$(sed -n 's/^backup_name=//p' "$install_state")
    [ -n "$initial_backup_name" ] || initial_backup_name=none
    created_local_config=$(sed -n 's/^created_local_config=//p' "$install_state")
    old_local_hash=$(sed -n 's/^local_config_sha256=//p' "$install_state")
    case "$old_local_hash" in ''|unknown) ;; *) preserved_local_hash=$old_local_hash ;; esac
    if [ "$state_version" = version=1 ] && [ "$created_local_config" = yes ] && [ -z "$old_local_hash" ]; then
        local_hash_legacy_unknown=yes
    fi
    case "$created_local_config" in yes|no) ;; *) printf '%s\n' 'Invalid existing cyber-ware installation state.' >&2; exit 1 ;; esac
fi
if [ -L "$main_config" ] || [ -L "$module_dir" ]; then
    printf '%s\n' 'Refusing to replace a symlinked Hyprland config target.' >&2
    exit 1
fi
if [ -e "$main_config" ] && [ ! -f "$main_config" ]; then
    printf 'Refusing to replace a non-file config target: %s\n' "$main_config" >&2
    exit 1
fi
for file in appearance.lua windows.lua autostart.lua keybindings.lua session-start.sh; do
    target=$module_dir/$file
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
        printf 'Refusing to replace an unsafe module target: %s\n' "$target" >&2
        exit 1
    fi
done

for command in chmod cp cut date dirname install mkdir mktemp mv rm sed sha256sum; do
    command -v "$command" >/dev/null 2>&1 || { printf 'Required installer command missing: %s\n' "$command" >&2; exit 1; }
done
. "$source_dir/packages/arch.sh"
. "$source_dir/packages/install.sh"
cw_install_packages

for command in python3 fish lua hyprctl pgrep flock timeout busctl dbus-update-activation-environment systemctl; do
    command -v "$command" >/dev/null 2>&1 || { printf 'Required command missing before install: %s\n' "$command" >&2; exit 1; }
done
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    hypr_version_text=$(hyprctl version 2>&1) || { printf 'Cannot query the running Hyprland version; no files changed:\n%s\n' "$hypr_version_text" >&2; exit 1; }
else
    command -v Hyprland >/dev/null 2>&1 || { printf '%s\n' 'Hyprland is required to check compatibility outside a graphical session.' >&2; exit 1; }
    hypr_version_text=$(Hyprland --version 2>&1) || { printf 'Cannot query the installed Hyprland version; no files changed:\n%s\n' "$hypr_version_text" >&2; exit 1; }
fi
hypr_version=$(printf '%s\n' "$hypr_version_text" | sed -n 's/^Hyprland \([0-9][0-9]*\)\.\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2 \3/p' | sed -n '1p')
set -- $hypr_version
if [ "$#" -ne 3 ] || { [ "$1" -eq 0 ] && [ "$2" -lt 55 ]; }; then
    detected_version=$(printf '%s\n' "$hypr_version_text" | sed -n '1p')
    printf 'cyber-ware requires Hyprland 0.55+ with the Lua config API; detected: %s. No files changed.\n' "$detected_version" >&2
    exit 1
fi
terminal_found=no
for terminal in ghostty kitty foot alacritty wezterm; do
    if command -v "$terminal" >/dev/null 2>&1; then terminal_found=yes; break; fi
done
[ "$terminal_found" = yes ] || { printf '%s\n' 'Install a terminal first (Ghostty, Kitty, Foot, Alacritty, or WezTerm); cyber-ware will not remove your terminal binding.' >&2; exit 1; }
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    # Filenames and keybindings cannot establish which parser is in use.
    # This read-only API probe also works in a minimal Lua config with no binds.
    if ! hypr_request eval 'assert(type(hl) == "table" and type(hl.config) == "function" and type(hl.bind) == "function" and type(hl.on) == "function", "missing cyber-ware Lua API")'; then
        printf '%s\n' 'The running session must use the Hyprland Lua config API. No desktop files changed.' 'For a legacy .conf session, log out and install from a TTY, or migrate that session to Lua first. Creating a .lua file alone does not switch the running parser.' >&2
        exit 1
    fi
    active_errors=$(hyprctl configerrors 2>&1) || { printf 'Could not inspect active Hyprland; no files changed:\n%s\n' "$active_errors" >&2; exit 1; }
    [ -z "$active_errors" ] || { printf 'Fix active Hyprland config errors before installation:\n%s\n' "$active_errors" >&2; exit 1; }
    autoreload_option=$(hyprctl getoption misc:disable_autoreload 2>&1) || { printf '%s\n' 'Cannot inspect automatic-reload setting; no files changed.' >&2; exit 1; }
    previous_autoreload=$(printf '%s\n' "$autoreload_option" | sed -n 's/^bool: \(true\|false\)$/\1/p')
    case "$previous_autoreload" in true|false) ;; *) printf '%s\n' 'Unrecognized automatic-reload setting; no files changed.' >&2; exit 1 ;; esac
fi
missing_selected=
for component in $selected_components; do
    case "$component" in
        cyber-wall) required='python3 mpvpaper ffmpeg' ;;
        cyber-signal) required='python3 mako notify-send nmcli checkupdates systemctl' ;;
        cyber-console) required='python3 ghostty hyprctl impala wiremix bluetui btop yazi' ;;
        cyber-panel) required='python3 waybar hyprctl playerctl' ;;
        cyber-jackout) required='wlogout hyprlock hypridle bash cat chmod cp cut dirname flock hyprctl logger mkdir mktemp mv notify-send pgrep readlink rm sed sha256sum sleep systemctl systemd-inhibit systemd-run timeout' ;;
        cyber-scan) required='grim slurp swappy' ;;
        cyber-deck) required='python3 fuzzel cliphist wl-paste wl-copy' ;;
        cyber-wave) required='python3 hyprctl mpv' ;;
    esac
    for dependency in $required; do
        command -v "$dependency" >/dev/null 2>&1 || missing_selected="$missing_selected $dependency($component)"
    done
    if { [ "$component" = cyber-wall ] || [ "$component" = cyber-wave ]; } && command -v python3 >/dev/null 2>&1 && \
        ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' >/dev/null 2>&1; then
        missing_selected="$missing_selected GTK4-PyGObject($component)"
    fi
done
[ -z "$missing_selected" ] || { printf 'Selected component requirements are missing; no desktop files changed:%s\n' "$missing_selected" >&2; exit 1; }
python3 "$source_dir/desktop/manage.py" check "${selected_theme:-synthwave}"

# Stage and syntax-check the entire required module set before publication.
mkdir -p "$hypr_dir"
stage_dir=$(mktemp -d "$hypr_dir/.cyber-ware-stage.XXXXXX")
cp -- "$source_dir/hyprland/hyprland.lua" "$stage_dir/hyprland.lua"
# A fresh token proves reload consumed this entry point, even if Hyprland was
# started with --config pointing elsewhere or silently kept the previous file.
install_token=${stage_dir##*/}
printf '\n_G.cyber_ware_install_token = "%s"\n' "$install_token" >> "$stage_dir/hyprland.lua"
for file in appearance.lua windows.lua autostart.lua keybindings.lua session-start.sh; do
    cp -- "$source_dir/hyprland/$file" "$stage_dir/$file"
done
sh -n "$stage_dir/session-start.sh"
for file in "$stage_dir"/*.lua; do
    CYBER_WARE_LUA_FILE="$file" lua -e 'assert(loadfile(os.getenv("CYBER_WARE_LUA_FILE")))' || { printf 'Staged Lua validation failed: %s\n' "$file" >&2; exit 1; }
done
mkdir -p "$state_home"
transaction_dir=$(mktemp -d "$state_home/cyber-ware-transaction.XXXXXX")
if [ -e "$main_config" ]; then cp -a -- "$main_config" "$transaction_dir/main"; else : > "$transaction_dir/main-absent"; fi
if [ -e "$module_dir" ]; then cp -a -- "$module_dir" "$transaction_dir/modules"; else : > "$transaction_dir/modules-absent"; fi
if [ -e "$hypr_dir/hyprland.local.lua" ]; then cp -a -- "$hypr_dir/hyprland.local.lua" "$transaction_dir/local"; else : > "$transaction_dir/local-absent"; fi
if [ -e "$install_state" ]; then cp -a -- "$install_state" "$transaction_dir/state"; else : > "$transaction_dir/state-absent"; fi
if [ -e "$bin_path_file" ]; then cp -a -- "$bin_path_file" "$transaction_dir/bin-path"; fi
if [ -e "$theme_file" ]; then cp -a -- "$theme_file" "$transaction_dir/theme"; else : > "$transaction_dir/theme-absent"; fi
if [ -e "$command_path" ]; then cp -a -- "$command_path" "$transaction_dir/command"; fi

backup_parent=$state_home/cyber-ware/backups
backup_dir=
if [ -e "$main_config" ] || [ -e "$module_dir" ]; then
    mkdir -p "$backup_parent"
    backup_dir=$(mktemp -d "$backup_parent/hyprland-$(date +%Y%m%d-%H%M%S).XXXXXX")
    [ ! -e "$main_config" ] || cp -a -- "$main_config" "$backup_dir/"
    [ ! -e "$module_dir" ] || cp -a -- "$module_dir" "$backup_dir/"
fi
if [ -z "$initial_backup_name" ] && [ -n "$backup_dir" ]; then
    initial_backup_name=${backup_dir##*/}
fi
if [ -z "$initial_backup_name" ]; then initial_backup_name=none; fi

local_config=$hypr_dir/hyprland.local.lua
migrate_env=no
migrate_monitor=no
if [ ! -e "$local_config" ] && [ ! -L "$local_config" ]; then
    [ ! -f "$module_dir/environment.lua" ] || [ -L "$module_dir/environment.lua" ] || migrate_env=yes
    [ ! -f "$module_dir/monitors.lua" ] || [ -L "$module_dir/monitors.lua" ] || migrate_monitor=yes
fi

mkdir -p "$module_dir" "$command_dir" "$(dirname -- "$theme_file")"
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    set_autoreload true || { printf '%s\n' 'Cannot pause automatic reload; active configuration was not replaced.' >&2; exit 1; }
    autoreload_paused=yes
fi
publish_started=yes
for file in appearance.lua windows.lua autostart.lua keybindings.lua session-start.sh; do
    install -m 644 "$stage_dir/$file" "$module_dir/$file"
done
if [ "$migrate_env" = yes ] || [ "$migrate_monitor" = yes ]; then
    local_config_tmp=$(mktemp "$hypr_dir/.hyprland.local.lua.XXXXXX")
    {
    printf '%s\n' '-- cyber-ware-migrated-local-config'
        printf '%s\n' '-- Migrated by cyber-ware from your previous modular Hyprland config.'
        [ "$migrate_env" != yes ] || printf '%s\n' 'require("hyprland.environment")'
        [ "$migrate_monitor" != yes ] || printf '%s\n' 'require("hyprland.monitors")'
    } > "$local_config_tmp"
    chmod 644 "$local_config_tmp"
    mv -- "$local_config_tmp" "$local_config"
    local_config_tmp=
    created_local_config=yes
    printf '%s\n' 'Preserved existing environment/monitor modules through hyprland.local.lua.'
fi
printf '%s\n' "$command_dir" > "$bin_path_file"
chmod 600 "$bin_path_file"
if [ ! -e "$theme_file" ]; then
    printf '%s\n' synthwave > "$theme_file"
    chmod 600 "$theme_file"
fi
mkdir -p "$state_home/cyber-ware"
install_state_tmp=$(mktemp "$state_home/cyber-ware/.install.state.XXXXXX")
{
    printf '%s\n' 'version=2'
    printf 'backup_name=%s\n' "$initial_backup_name"
    printf 'created_local_config=%s\n' "$created_local_config"
    printf 'source_revision=%s\ncommand_dir=%s\n' "$revision" "$command_dir"
    if [ "$created_local_config" = yes ]; then
        if [ "$local_hash_legacy_unknown" = yes ]; then
            printf '%s\n' 'local_config_sha256=unknown'
        elif [ -n "$preserved_local_hash" ]; then
            printf 'local_config_sha256=%s\n' "$preserved_local_hash"
        else
            printf 'local_config_sha256=%s\n' "$(sha256sum "$local_config" | cut -d ' ' -f 1)"
        fi
    fi
} > "$install_state_tmp"
chmod 600 "$install_state_tmp"
mv -- "$install_state_tmp" "$install_state"
install -m 755 "$source_dir/bin/cyber-ware" "$command_path"
install -m 644 "$stage_dir/hyprland.lua" "$main_config"
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    if ! hypr_request reload; then
        printf '%s\n' 'Hyprland reload failed; restoring the previous configuration.' >&2
        exit 1
    fi
    active_errors=$(hyprctl configerrors 2>&1) || active_errors='could not query Hyprland config errors'
    if [ -n "$active_errors" ]; then
        printf 'New config validation failed; restoring the previous configuration:\n%s\n' "$active_errors" >&2
        exit 1
    fi
    if ! hypr_request eval "assert(rawget(_G, 'cyber_ware_install_token') == '$install_token', 'cyber-ware entry point was not loaded')"; then
        printf '%s\n' 'Hyprland did not load the installed entry point (check --config or XDG_CONFIG_HOME); restoring the previous configuration.' >&2
        exit 1
    fi
    set_autoreload "$previous_autoreload" || exit 1
    autoreload_paused=no
fi
python3 "$source_dir/desktop/manage.py" install "${selected_theme:-synthwave}"
install_complete=yes
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    python3 "$source_dir/desktop/manage.py" settings || {
        printf '%s\n' 'Desktop files installed, but GTK interface preferences could not be applied; retry at next login.' >&2
        exit 1
    }
fi
printf 'Installed the cyber-ware Hyprland config in %s\n' "$hypr_dir"
printf 'Installed cyber-ware theme command in %s\n' "$command_path"
printf 'Source revision: %s\n' "$revision"
if [ -n "$backup_dir" ]; then
    printf 'Previous config files backed up to %s\n' "$backup_dir"
else
    printf '%s\n' 'No previous Hyprland entry point or module directory needed backing up.'
fi
if [ "$migrate_env" != yes ] && [ "$migrate_monitor" != yes ]; then
    printf '%s\n' 'Existing hyprland.local.lua machine overrides were left untouched.'
fi

failures=
install_component() {
    component=$1
    case " $selected_components " in
        *" $component "*)
            printf '\nInstalling %s...\n' "$component"
            if (CDPATH= cd -- "$source_dir/$component" && sh ./install.sh); then
                integration_ok=yes
                cw_enable_component "$component" || integration_ok=no
                if [ "$integration_ok" != yes ]; then
                    printf 'Default integration failed for %s; see the error above.\n' "$component" >&2
                    failures="$failures $component(integration)"
                fi
                printf 'Installed %s.\n\n' "$component"
            else
                printf 'Installation failed for %s; see its README for requirements. Continuing.\n\n' "$component" >&2
                failures="$failures $component"
            fi
            ;;
        *) printf 'Skipped %s.\n\n' "$component" ;;
    esac
}

for component in cyber-wall cyber-signal cyber-console cyber-panel cyber-jackout cyber-scan cyber-deck cyber-wave; do
    install_component "$component"
done

printf '%s\n' 'The config detects installed optional commands when Hyprland loads.'
if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] && command -v hyprctl >/dev/null 2>&1; then
    if hypr_request reload; then
        autoreload_paused=yes
        active_errors=$(hyprctl configerrors 2>&1) || active_errors='could not query Hyprland config errors'
        if [ -n "$active_errors" ]; then
            printf 'Desktop activation reported configuration errors:\n%s\n' "$active_errors" >&2
            exit 1
        fi
        if ! hypr_request eval "assert(rawget(_G, 'cyber_ware_install_token') == '$install_token', 'cyber-ware entry point was not loaded')" || \
            ! set_autoreload "$previous_autoreload"; then
            printf '%s\n' 'Desktop activation could not be verified; inspect hyprctl configerrors.' >&2
            exit 1
        fi
        autoreload_paused=no
        printf '%s\n' 'Hyprland reloaded; configured applications/services are activated without duplicate launches, and saved wallpaper restoration was requested.'
    else
        printf '%s\n' 'Hyprland is not reachable from this shell; after logging in, run: hyprctl reload' >&2
        exit 1
    fi
elif [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    printf '%s\n' 'hyprctl is unavailable; after logging in, run: hyprctl reload' >&2
else
    printf '%s\n' 'No active Hyprland session was detected; activation will run at the next login.'
fi
printf '%s\n' 'Selected components include their desktop integrations: cyber-jackout idle locking, cyber-deck clipboard history, and cyber-signal monitoring.'
case ":${PATH:-}:" in
    *":$command_dir:"*) ;;
    *) printf 'For interactive shell use, add %s to PATH (fish: fish_add_path %s). Hyprland/Waybar already use this recorded path.\n' "$command_dir" "$command_dir" ;;
esac
if [ -n "$failures" ]; then
    printf 'These component installs failed:%s\n' "$failures" >&2
    exit 1
fi
