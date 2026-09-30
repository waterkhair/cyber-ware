#!/bin/sh
set -eu

script_name=${0##*/}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$script_dir
case "$script_name" in sh|bash|dash|-sh|-bash) project_dir= ;; esac
download_dir=
stage_dir=
style_tmp=
cleanup() {
    [ -z "$style_tmp" ] || rm -f -- "$style_tmp"
    [ -z "$stage_dir" ] || rm -rf -- "$stage_dir"
    [ -z "$download_dir" ] || rm -rf -- "$download_dir"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ -z "$project_dir" ] || [ ! -f "$project_dir/bin/cyber-jackout" ]; then
    command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required to download cyber-jackout.' >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { printf '%s\n' 'tar is required to unpack cyber-jackout.' >&2; exit 1; }
    download_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-jackout-install.XXXXXX")
    revision=$(curl -fsSL https://api.github.com/repos/WaterKhair/cyber-ware/commits/main | sed -n 's/.*"sha": *"\([0-9a-f]*\)".*/\1/p' | sed -n '1p')
    [ "${#revision}" -eq 40 ] || { printf '%s\n' 'Could not resolve cyber-ware revision.' >&2; exit 1; }
    if ! curl -fsSL "https://github.com/WaterKhair/cyber-ware/archive/$revision.tar.gz" \
        | tar -xz --strip-components=1 -C "$download_dir"; then
        printf '%s\n' 'Could not download cyber-jackout. Check that cyber-ware has a public main branch.' >&2
        exit 1
    fi
    project_dir="$download_dir/cyber-jackout"
fi

[ -f "$project_dir/bin/cyber-jackout" ] || { printf '%s\n' 'cyber-jackout source was not found.' >&2; exit 1; }

prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
app_dir="$data_home/cyber-jackout"
command_dir="$prefix/bin"
command_path="$command_dir/cyber-jackout"
state_dir="$state_home/cyber-jackout"
wlogout_dir="$config_home/wlogout"
wlogout_layout="$wlogout_dir/layout"
theme_config="$config_home/cyber-jackout/theme"

case "$command_dir" in
    /bin|/usr/bin|/usr/local/bin)
        printf 'Refusing to install a user command into system directory %s.\n' "$command_dir" >&2
        exit 1
        ;;
esac
case "$app_dir:$state_dir:$wlogout_dir" in
    /cyber-jackout:*|*:/cyber-jackout:*|*:/wlogout)
        printf '%s\n' 'Refusing unsafe root-level cyber-jackout configuration paths.' >&2
        exit 1
        ;;
esac
if [ -L "$command_dir" ] || [ -L "$wlogout_dir" ] || [ -L "$config_home/cyber-jackout" ]; then
    printf '%s\n' 'Refusing symlinked command, wlogout, or cyber-jackout settings directory.' >&2
    exit 1
fi

for command in bash chmod cp cut dirname ln mkdir mktemp mv readlink rm sed sha256sum; do
    command -v "$command" >/dev/null 2>&1 || { printf 'Required installer command missing: %s\n' "$command" >&2; exit 1; }
done

if [ -e "$command_path" ] || [ -L "$command_path" ]; then
    if [ ! -L "$command_path" ] || [ "$(readlink -f -- "$command_path" 2>/dev/null || true)" != "$app_dir/bin/cyber-jackout" ]; then
        printf 'Refusing to overwrite existing file: %s\n' "$command_path" >&2
        exit 1
    fi
fi
if [ -L "$app_dir" ] || { [ -e "$app_dir" ] && [ ! -f "$app_dir/.cyber-jackout-managed" ]; }; then
    printf 'Refusing to overwrite unrecognized or unsafe data directory: %s\n' "$app_dir" >&2
    exit 1
fi
if [ -e "$state_dir" ] && { [ -L "$state_dir" ] || { [ ! -f "$state_dir/installed" ] && [ ! -f "$state_dir/.cyber-jackout-managed" ]; }; }; then
    printf 'Refusing to overwrite unrecognized or unsafe state directory: %s\n' "$state_dir" >&2
    exit 1
fi
if [ -L "$wlogout_dir/style.css" ]; then
    printf 'Refusing to replace a symlinked wlogout stylesheet: %s\n' "$wlogout_dir/style.css" >&2
    exit 1
fi
if [ -L "$wlogout_layout" ] || { [ -e "$wlogout_layout" ] && [ ! -f "$wlogout_layout" ]; }; then
    printf 'Refusing unsafe wlogout layout destination: %s\n' "$wlogout_layout" >&2
    exit 1
fi

theme=${CYBER_JACKOUT_THEME:-}
if [ -z "$theme" ] && [ -f "$theme_config" ]; then
    theme=$(sed -n '1p' "$theme_config")
fi
shared_theme_file=$config_home/cyber-ware/theme
if [ -z "${CYBER_JACKOUT_THEME:-}" ] && [ -f "$shared_theme_file" ]; then
    shared_theme=$(sed -n '1p' "$shared_theme_file")
    case "$shared_theme" in
        synthwave|greenline) theme=$shared_theme ;;
        *) printf 'Ignoring invalid shared cyber-ware theme in %s.\n' "$shared_theme_file" >&2 ;;
    esac
fi
theme=${theme:-synthwave}
case "$theme" in
    synthwave|greenline) ;;
    *) printf 'Unknown theme %s; choose synthwave or greenline.\n' "$theme" >&2; exit 1 ;;
esac
if [ "$theme" = greenline ] && ! command -v rsvg-convert >/dev/null 2>&1; then
    printf '%s\n' 'The greenline icon set needs librsvg (rsvg-convert); install it before choosing greenline.' >&2
    exit 1
fi
if [ ! -f "$project_dir/themes/$theme.css" ]; then
    printf 'Theme file is missing: %s\n' "$project_dir/themes/$theme.css" >&2
    exit 1
fi
if [ "$theme" = greenline ]; then
    for icon in lock logout suspend reboot shutdown; do
        if [ ! -f "$project_dir/icons/greenline/$icon.svg" ]; then
            printf 'Greenline icon is missing: %s\n' "$project_dir/icons/greenline/$icon.svg" >&2
            exit 1
        fi
    done
fi

mkdir -p "$command_dir" "$(dirname -- "$app_dir")" "$wlogout_dir" "$state_dir/backups" "$(dirname -- "$theme_config")"
first_install=no
if [ ! -f "$state_dir/installed" ]; then
    first_install=yes
    if [ -f "$wlogout_dir/style.css" ]; then
        cp -p -- "$wlogout_dir/style.css" "$state_dir/backups/style.css"
        printf 'yes\n' > "$state_dir/original-style-existed"
    else
        printf 'no\n' > "$state_dir/original-style-existed"
    fi
    if [ -f "$wlogout_layout" ]; then
        cp -p -- "$wlogout_layout" "$state_dir/backups/layout"
        printf 'yes\n' > "$state_dir/original-layout-existed"
    else
        printf 'no\n' > "$state_dir/original-layout-existed"
    fi
fi
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyber-jackout-stage.XXXXXX")
cp -R "$project_dir/." "$stage_dir/"
chmod 755 "$stage_dir/bin/cyber-jackout" "$stage_dir/libexec/cyber-jackout-power-finish"
: > "$stage_dir/.cyber-jackout-managed"

if [ -e "$app_dir" ]; then
    rm -rf -- "$app_dir"
fi
mv "$stage_dir" "$app_dir"
stage_dir=
ln -sfn "$app_dir/bin/cyber-jackout" "$command_path"

style_tmp=$(mktemp "$wlogout_dir/.style.css.cyber-jackout.XXXXXX")
if [ "$theme" = greenline ]; then
    icon_uri="$app_dir/icons/greenline"
    escaped_icon_uri=$(printf '%s' "$icon_uri" | sed 's/[\\&|]/\\&/g')
    sed "s|@ICON_DIR@|$escaped_icon_uri|g" "$app_dir/themes/$theme.css" > "$style_tmp"
else
    cp -- "$app_dir/themes/$theme.css" "$style_tmp"
fi
chmod 644 "$style_tmp"
mv -f -- "$style_tmp" "$wlogout_dir/style.css"
style_tmp=
printf '%s\n' "$theme" > "$theme_config"
chmod 600 "$theme_config"
sha256sum -- "$wlogout_dir/style.css" | cut -d ' ' -f 1 > "$state_dir/style.sha256"
layout_expected=$(cat "$state_dir/layout.sha256" 2>/dev/null || true)
layout_can_install=no
if [ "$first_install" = yes ] || [ ! -e "$wlogout_layout" ]; then
    layout_can_install=yes
elif [ -n "$layout_expected" ] && [ "$(sha256sum -- "$wlogout_layout" | cut -d ' ' -f 1)" = "$layout_expected" ]; then
    layout_can_install=yes
fi
if [ "$layout_can_install" = yes ]; then
    escape_sed() { printf '%s' "$1" | sed 's/[\\&#|]/\\&/g'; }
    jackout_escaped=$(escape_sed "$command_path")
    if command -v hyprlock >/dev/null 2>&1; then lock_action=hyprlock; else lock_action='loginctl lock-session'; fi
    lock_escaped=$(escape_sed "$lock_action")
    layout_tmp=$(mktemp "$wlogout_dir/.layout.cyber-jackout.XXXXXX")
    sed "s|@JACKOUT@|$jackout_escaped|g; s|@LOCK_ACTION@|$lock_escaped|g" "$app_dir/layout" > "$layout_tmp"
    chmod 644 "$layout_tmp"
    mv -f -- "$layout_tmp" "$wlogout_layout"
    sha256sum -- "$wlogout_layout" | cut -d ' ' -f 1 > "$state_dir/layout.sha256"
else
    printf '%s\n' 'Kept your modified wlogout layout; it was not overwritten. See README for the cyber-jackout actions.'
fi
: > "$state_dir/installed"
: > "$state_dir/.cyber-jackout-managed"

printf 'Installed cyber-jackout in %s\n' "$app_dir"
printf 'Command: %s\n' "$command_path"
printf 'wlogout theme: %s (switch with cyber-jackout --theme synthwave|greenline)\n' "$theme"
printf '%s\n' 'Run cyber-jackout --check to verify requirements.'
printf '%s\n' 'The managed wlogout layout routes logout, reboot, and shutdown through cyber-jackout; lock uses hyprlock when installed (otherwise loginctl), and suspend uses systemctl.'
