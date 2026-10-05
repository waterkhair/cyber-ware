"""Single-command user interface for cyber-wall."""

from __future__ import annotations

import sys

from .config import AVAILABLE_THEMES, load_config, set_theme


USAGE = """Usage:
  cyber-wall                              Toggle the picker
  cyber-wall --set FILE                   Set an image/video wallpaper
  cyber-wall --set --restore              Restore the previous wallpaper
  cyber-wall --sync-lock-wallpaper        Sync it to Hyprlock (video uses a still frame)
  cyber-wall --theme [greenline|synthwave|husky] Show or set the picker theme
  cyber-wall --uninstall [--purge]        Uninstall (optionally remove saved data)
  cyber-wall --help                       Show this help
"""


def main() -> int:
    args = sys.argv[1:]
    try:
        if not args:
            from .toggle import toggle

            return toggle()
        if args in (["-h"], ["--help"]):
            print(USAGE, end="")
            return 0
        if args[0] == "--set":
            from .wallpaper import main as set_main

            return set_main(args[1:])
        if args == ["--sync-lock-wallpaper"]:
            from .lock_wallpaper import sync_lock_wallpaper

            print(f"Hyprlock wallpaper synced: {sync_lock_wallpaper()}")
            return 0
        if args[0] == "--theme":
            if len(args) == 1:
                config = load_config()
                print(f"Current theme: {config['theme']}")
                print(f"Available themes: {' | '.join(AVAILABLE_THEMES)}")
                return 0
            if len(args) != 2:
                raise ValueError("use: cyber-wall --theme [greenline|synthwave|husky]")
            set_theme(args[1])
            print(f"Theme set to {args[1]}. Close and reopen the picker to apply it.")
            return 0
        if args[0] == "--uninstall":
            from .uninstall import main as uninstall_main

            return uninstall_main(args[1:])
        raise ValueError(f"unknown option: {args[0]}")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"cyber-wall: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
