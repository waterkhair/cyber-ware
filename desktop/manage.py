#!/usr/bin/env python3
"""Install, theme, and restore cyber-ware's portable base desktop files."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

THEMES = ('synthwave', 'greenline', 'husky')
INTERNAL = 'cyber-ware/desktop'

GHOSTTY = '''# cyber-ware: portable terminal defaults
font-family = JetBrainsMono Nerd Font
font-size = 12
class = Ghostty
window-padding-x = 10
window-padding-y = 5
window-padding-balance = true
background-opacity = 0.92
window-decoration = auto
cursor-style = underline
mouse-hide-while-typing = true
copy-on-select = true
scrollback-limit = 10000
term = xterm-ghostty
command = fish
'''

FISH = '''# cyber-ware: portable interactive shell; no personal paths or secrets.
if status is-interactive
    set -g fish_greeting
    fish_add_path --path --move $HOME/.local/bin
    set -l cyber_ware_config $HOME/.config
    if set -q XDG_CONFIG_HOME
        set cyber_ware_config $XDG_CONFIG_HOME
    end
    if test -f "$cyber_ware_config/cyber-ware/bin-path"
        set -l cyber_ware_bin (head -n 1 "$cyber_ware_config/cyber-ware/bin-path")
        if test -d "$cyber_ware_bin"
            fish_add_path --path --move "$cyber_ware_bin"
        end
    end
    if not set -q EDITOR
        for candidate in nvim vim nano vi
            if command -q $candidate
                set -gx EDITOR $candidate
                break
            end
        end
    end
    if not set -q SUDO_EDITOR; and set -q EDITOR
        set -gx SUDO_EDITOR $EDITOR
    end
    if command -q zoxide
        zoxide init fish | source
    end
end
'''

PROMPT = '''# cyber-ware: compact prompt with path and Git status.
function fish_prompt
    set -l last_status $status
    set_color $fish_color_cwd
    printf '%s' (prompt_pwd)
    set_color normal
    fish_git_prompt
    printf '\\n'
    if test $last_status -ne 0
        set_color red
    else
        set_color $fish_color_cwd
    end
    printf '❯ '
    set_color normal
end
'''

YAZI = '''# cyber-ware: spacious previews and portable mpv media opening.
[mgr]
ratio = [1, 3, 4]
[preview]
max_width = 2400
max_height = 2400
image_filter = "lanczos3"
[opener]
mpv = [{ run = "mpv -- %s", orphan = true, desc = "Open with mpv", for = "unix" }]
mpv_image = [{ run = "mpv --force-window=yes --keep-open=always -- %s", orphan = true, desc = "Open image with mpv", for = "unix" }]
[open]
prepend_rules = [
    { mime = "image/*", use = "mpv_image" },
    { mime = "audio/*", use = "mpv" },
    { mime = "video/*", use = "mpv" },
]
'''


def roots():
    home = Path.home()
    return (Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')),
            Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'cyber-ware')


def safe(path: Path):
    if not path.is_absolute() or '..' in path.parts or path == Path('/'):
        raise RuntimeError(f'Unsafe desktop path: {path}')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise RuntimeError(f'Refusing symlink: {part}')
    if path.exists() and not path.is_file():
        raise RuntimeError(f'Expected regular file: {path}')


def palette_text(name):
    bundled = Path(__file__).parent / 'themes' / name
    if not bundled.is_file():
        bundled = Path(__file__).resolve().parents[1] / 'cyber-console/themes' / name
    return bundled.read_text()


def render(theme):
    config, _ = roots()
    palette = palette_text(theme)
    values = dict(line.split(' = ', 1) for line in palette.splitlines() if ' = ' in line and not line.startswith('palette'))
    bg, fg = values['background'], values['foreground']
    accent = {'synthwave': '#00e5ff', 'greenline': '#8df0a6', 'husky': '#ffffff'}[theme]
    muted = {'synthwave': '#7f8ca3', 'greenline': '#718675', 'husky': '#888888'}[theme]
    panel = {'synthwave': '#131b26', 'greenline': '#101a12', 'husky': '#111111'}[theme]
    settings = '''[Settings]
gtk-application-prefer-dark-theme=true
gtk-theme-name=adw-gtk3-dark
gtk-icon-theme-name=breeze-dark
gtk-cursor-theme-name=breeze_cursors
gtk-cursor-theme-size=24
gtk-font-name=Noto Sans 10
'''
    css = f'''/* cyber-ware palette; retain toolkit widget layout. */
@define-color accent_color {accent};
@define-color accent_bg_color {accent};
@define-color accent_fg_color {bg};
@define-color window_bg_color {bg};
@define-color window_fg_color {fg};
@define-color view_bg_color {bg};
@define-color view_fg_color {fg};
'''
    # QPalette ColorRole order, matching qt5ct/qt6ct's color scheme format.
    colors = [fg, panel, muted, panel, bg, panel, fg, fg, fg, bg, bg,
              '#000000', accent, bg, accent, muted, panel, '#000000', panel, fg, muted, accent]
    qt_colors = '[ColorScheme]\n' + ''.join(
        role + '_colors=' + ', '.join('#ff' + c[1:] for c in colors) + '\n'
        for role in ('active', 'inactive', 'disabled'))
    files = {
        'ghostty/config': (GHOSTTY + palette).encode(),
        # Current Ghostty prefers config.ghostty; manage both so neither masks
        # the installed profile on old/new versions, restoring both on removal.
        'ghostty/config.ghostty': (GHOSTTY + palette).encode(),
        'fish/config.fish': FISH.encode(),
        'fish/functions/fish_prompt.fish': PROMPT.encode(),
        'fish/conf.d/cyber-ware-theme.fish': (
            f'set -g fish_color_cwd {accent[1:]}\nset -g fish_color_command {fg[1:]}\n'
            f'set -g fish_color_param {fg[1:]}\nset -g fish_color_autosuggestion {muted[1:]}\n').encode(),
        'yazi/yazi.toml': YAZI.encode(),
        'gtk-3.0/settings.ini': settings.encode(),
        'gtk-4.0/settings.ini': settings.encode(),
        'gtk-3.0/gtk.css': css.encode(),
        'gtk-4.0/gtk.css': css.encode(),
        'xsettingsd/xsettingsd.conf': b'Net/ThemeName "adw-gtk3-dark"\nNet/IconThemeName "breeze-dark"\nGtk/CursorThemeName "breeze_cursors"\nGtk/CursorThemeSize 24\nGtk/FontName "Noto Sans 10"\nNet/PreferDarkTheme 1\n',
        f'{INTERNAL}/manage.py': Path(__file__).read_bytes(),
    }
    for name in THEMES:
        files[f'{INTERNAL}/themes/{name}'] = palette_text(name).encode()
    for version in ('qt5ct', 'qt6ct'):
        files[f'{version}/colors/cyber-ware.conf'] = qt_colors.encode()
        files[f'{version}/{version}.conf'] = (
            '[Appearance]\nstyle=Fusion\ncustom_palette=true\nicon_theme=breeze-dark\n'
            f'color_scheme_path={config}/{version}/colors/cyber-ware.conf\n'
            '[Fonts]\ngeneral="Noto Sans,10,-1,5,50,0,0,0,0,0"\n'
            'fixed="JetBrainsMono Nerd Font,10,-1,5,50,0,0,0,0,0"\n').encode()
    return files


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data, mode=0o600):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.cyber-ware-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def snapshot(path):
    if not path.exists():
        return None
    return {'data': base64.b64encode(path.read_bytes()).decode(),
            'mode': stat.S_IMODE(path.stat().st_mode)}


def restore(path, value):
    if value is None:
        path.unlink(missing_ok=True)
    else:
        atomic(path, base64.b64decode(value['data'], validate=True), value['mode'])


def manage(action, theme='synthwave'):
    config, state = roots()
    files = render(theme)
    manifest = state / 'desktop.json'
    safe(manifest)
    previous = json.loads(manifest.read_text()) if manifest.exists() else {'version': 1, 'files': {}}
    if previous.get('version') != 1 or not isinstance(previous.get('files'), dict):
        raise RuntimeError('Invalid desktop installation manifest')
    if set(previous['files']) - set(files):
        raise RuntimeError('Unrecognized paths in desktop installation manifest')
    for relative in files:
        safe(config / relative)
    if action == 'check':
        return
    if action in ('theme', 'uninstall') and not manifest.exists():
        return
    records = dict(previous['files'])
    changes = {}
    for relative, content in files.items():
        path = config / relative
        record = records.get(relative)
        if record and path.exists() and digest(path.read_bytes()) != record['sha256']:
            print(f'Kept edited desktop file: {path}')
            continue
        if action == 'uninstall':
            if record:
                changes[path] = record['original']
                del records[relative]
        else:
            if action == 'theme' and not record:
                continue
            if record is None:
                record = {'original': snapshot(path)}
            records[relative] = {**record, 'sha256': digest(content)}
            changes[path] = {'data': base64.b64encode(content).decode(), 'mode': 0o600}
    # Preserve the helper/palettes if edited files still need ownership records.
    if action == 'uninstall' and records:
        for relative, record in previous['files'].items():
            if relative.startswith(INTERNAL + '/'):
                changes.pop(config / relative, None)
                records[relative] = record
    changes[manifest] = {'data': base64.b64encode((json.dumps({'version': 1, 'files': records}, indent=2) + '\n').encode()).decode(), 'mode': 0o600} if records else None
    before = {path: snapshot(path) for path in changes}
    try:
        for path, content in changes.items():
            restore(path, content)
    except Exception:
        for path, content in before.items():
            restore(path, content)
        raise
    print(f'cyber-ware desktop profile: {action} complete.')


def settings(remove=False):
    """Manage only interface preferences, preserving prior user/distro values."""
    _, state = roots()
    path = state / 'desktop-settings.json'
    safe(path)
    if not shutil.which('gsettings'):
        raise RuntimeError('gsettings is required for GTK desktop preferences')
    schema = 'org.gnome.desktop.interface'
    desired = {'color-scheme': "'prefer-dark'", 'gtk-theme': "'adw-gtk3-dark'",
               'icon-theme': "'breeze-dark'", 'cursor-theme': "'breeze_cursors'",
               'cursor-size': '24', 'font-name': "'Noto Sans 10'"}
    records = json.loads(path.read_text()) if path.exists() else {}
    if set(records) - set(desired):
        raise RuntimeError('Unknown keys in desktop settings record')
    changes = []
    for key, value in desired.items():
        current = subprocess.check_output(['gsettings', 'get', schema, key], text=True).strip()
        record = records.get(key)
        if record and current != record['value']:
            print(f'Kept edited interface setting: {key}')
            continue
        if remove:
            if record:
                changes.append((key, current, record['original']))
                del records[key]
        else:
            changes.append((key, current, value))
            records[key] = {'original': record['original'] if record else current, 'value': value}
    completed = []
    try:
        for key, previous, value in changes:
            subprocess.run(['gsettings', 'set', schema, key, value], check=True)
            completed.append((key, previous))
        if records:
            atomic(path, (json.dumps(records, indent=2) + '\n').encode())
        else:
            path.unlink(missing_ok=True)
    except Exception:
        for key, previous in reversed(completed):
            subprocess.run(['gsettings', 'set', schema, key, previous], check=False)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'install', 'theme', 'uninstall', 'settings', 'restore-settings'))
    parser.add_argument('theme', nargs='?', choices=THEMES, default='synthwave')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            manage(args.action, args.theme)
        else:
            _, state = roots()
            safe(state / 'desktop.lock')
            state.mkdir(parents=True, exist_ok=True)
            with (state / 'desktop.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if args.action in ('settings', 'restore-settings'):
                    settings(remove=args.action == 'restore-settings')
                else:
                    manage(args.action, args.theme)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f'cyber-ware desktop: {error}\n')


if __name__ == '__main__':
    main()
