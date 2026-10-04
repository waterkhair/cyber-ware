"""Cleanly uninstall cyber-wall while preserving personal data by default."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .config import cache_dir, config_path, runtime_dir, state_dir
from .lock_wallpaper import _atomic_write, validate_purge
from .toggle import stop_picker
from .wallpaper import stop_wallpaper


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def main(args: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if args is None else args)
    if args not in ([], ["--purge"]):
        print("Usage: cyber-wall --uninstall [--purge]", file=sys.stderr)
        return 2
    purge = args == ["--purge"]
    if purge:
        print("This will remove cyber-wall configuration and saved wallpaper state.")
        print("Continue? Type cyber-wall to confirm: ", end="", flush=True)
        if input() != "cyber-wall":
            print("Cancelled; nothing was removed.")
            return 1

    lock_restore = None
    if purge:
        try:
            lock_restore = validate_purge()
        except RuntimeError as error:
            print(f"cyber-wall: purge cancelled: {error}", file=sys.stderr)
            return 1

    try:
        stop_picker()
        stop_wallpaper()
        if lock_restore is not None:
            config_file, original = lock_restore
            if original is None:
                config_file.unlink(missing_ok=True)
            else:
                _atomic_write(config_file, original, config_file.stat().st_mode & 0o777)
    except (OSError, RuntimeError) as error:
        print(f"cyber-wall: could not stop cleanly; uninstall cancelled: {error}", file=sys.stderr)
        return 1

    prefix = Path(os.environ.get("PREFIX", Path.home() / ".local")).expanduser()
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")).expanduser()
    command = prefix / "bin" / "cyber-wall"
    app_dir = data_home / "cyber-wall"
    try:
        command.unlink(missing_ok=True)
        _remove(app_dir)
        if purge:
            _remove(config_path().parent)
            _remove(state_dir())
            _remove(cache_dir())
        runtime = runtime_dir()
        try:
            runtime.rmdir()
        except OSError:
            pass
    except OSError as error:
        print(f"cyber-wall: uninstall was incomplete: {error}", file=sys.stderr)
        return 1

    print("cyber-wall program and command removed.")
    if purge:
        print("Configuration, saved wallpaper state, and cache were also removed.")
    else:
        print("Configuration, saved wallpaper state, and cache were preserved.")
    print("Hyprlock's main configuration is not edited; its wallpaper include is restored only during a safe --purge.")
    return 0
