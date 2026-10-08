# Sourced by the umbrella installer after component selection, before publication.
cw_enable_component() {
    case "$1" in
        cyber-jackout) "$command_dir/cyber-jackout" --enable-idle ;;
        cyber-deck) "$command_dir/cyber-deck" --clipboard enable ;;
        cyber-signal) "$command_dir/cyber-signal" --enable ;;
    esac
}

cw_install_packages() {
    # For managed systems and isolated tests: existing executable/import checks
    # still run. Standalone component installers do not source this helper.
    case "${CYBER_WARE_INSTALL_PACKAGES:-1}" in
        0) printf '%s\n' 'System packages externally managed; checking existing requirements only.'; return 0 ;;
        1) ;;
        *) printf '%s\n' 'CYBER_WARE_INSTALL_PACKAGES must be 0 or 1.' >&2; return 1 ;;
    esac
    if ! command -v pacman >/dev/null 2>&1; then
        printf '%s\n' 'Automatic package installation currently supports CachyOS/Arch with pacman.' \
            'On another distribution, install the README requirements and use CYBER_WARE_INSTALL_PACKAGES=0.' >&2
        return 1
    fi
    cw_requested=
    for cw_group in base $selected_components; do
        cw_group_packages=$(cw_packages "$cw_group") || return 1
        printf 'Packages for %s: %s\n' "$cw_group" "$cw_group_packages"
        for cw_package in $cw_group_packages; do
            case " $cw_requested " in
                *" $cw_package "*) ;;
                *) cw_requested="$cw_requested $cw_package" ;;
            esac
        done
    done
    cw_missing=
    cw_unavailable=
    for cw_package in $cw_requested; do
        if ! pacman -Q "$cw_package" >/dev/null 2>&1; then
            cw_missing="$cw_missing $cw_package"
            pacman -Si "$cw_package" >/dev/null 2>&1 || cw_unavailable="$cw_unavailable $cw_package"
        fi
    done
    if [ -n "$cw_unavailable" ]; then
        printf 'Required packages unavailable in configured repositories:%s\n' "$cw_unavailable" >&2
        printf '%s\n' 'Install those packages from a trusted source or configure an appropriate repository, then rerun.' \
            'cyber-ware does not add repositories or run an AUR helper. No desktop files changed.' >&2
        return 1
    fi
    if [ -z "$cw_missing" ]; then
        printf '%s\n' 'All selected system packages are already installed.'
        return 0
    fi
    printf 'Installing missing system packages:%s\n' "$cw_missing"
    printf '%s\n' 'Keep your system fully updated before installation. Package changes are not rolled back by cyber-ware uninstall.'
    command -v sudo >/dev/null 2>&1 || { printf '%s\n' 'Install sudo or provision the listed packages as administrator first.' >&2; return 1; }
    # /dev/tty prevents pacman from consuming the remainder of a curl | sh script.
    if ! (exec 3</dev/tty) 2>/dev/null; then
        printf '%s\n' 'A terminal is required for sudo and pacman confirmation. Run this installer from a terminal.' >&2
        return 1
    fi
    # Never refresh databases without a full upgrade (-Sy), never force removals,
    # and retain pacman's own transaction/conflict confirmation.
    if ! sudo pacman -S --needed -- $cw_missing </dev/tty; then
        printf '%s\n' 'Package installation failed or was cancelled; no desktop files changed.' \
            'If mirrors or dependencies are stale, complete sudo pacman -Syu and rerun.' >&2
        return 1
    fi
    for cw_package in $cw_missing; do
        pacman -Q "$cw_package" >/dev/null 2>&1 || {
            printf 'Package installation did not provide %s; no desktop files changed.\n' "$cw_package" >&2
            return 1
        }
    done
}
