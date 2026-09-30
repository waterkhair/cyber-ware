#!/usr/bin/env python3
"""Manage cyber-panel's user-scoped Waybar configuration and themes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
from pathlib import Path

THEMES = ("synthwave", "greenline")
MANAGED_FILES = ("config.jsonc", "style.css")


def paths() -> dict[str, Path]:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    return {
        "waybar": config_home / "waybar",
        "config": config_home / "cyber-panel" / "config.json",
        "state": state_home / "cyber-panel",
        "app": data_home / "cyber-panel",
        "prefix": Path(os.environ.get("PREFIX", home / ".local")),
    }


def app_dir() -> Path:
    return Path(os.environ.get("CYBER_PANEL_APP_DIR", paths()["app"]))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.cyber-panel-tmp")
    temporary.write_bytes(content)
    temporary.chmod(mode)
    temporary.replace(path)


def read_state(p: dict[str, Path]) -> dict:
    state_file = p["state"] / "install.json"
    if not state_file.exists():
        raise RuntimeError("cyber-panel is not installed (no install state found).")
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read cyber-panel install state: {error}") from error
    if state.get("version") != 1:
        raise RuntimeError("Unsupported cyber-panel install state version.")
    return state


def apply_theme(name: str, p: dict[str, Path], reload_bar: bool = True) -> None:
    if name not in THEMES:
        raise ValueError(f"Unknown theme {name!r}; choose: {', '.join(THEMES)}")
    source = app_dir() / "themes" / f"{name}.css"
    if not source.is_file():
        raise RuntimeError(f"Theme file is missing: {source}")
    config = p["config"]
    current = {}
    if config.exists():
        try:
            current = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read cyber-panel settings: {error}") from error
    current["theme"] = name
    atomic_write(p["waybar"] / "style.css", source.read_bytes())
    atomic_write(config, (json.dumps(current, indent=2) + "\n").encode(), 0o600)
    if reload_bar:
        reload_waybar()
    print(f"Theme set to {name}.")


def reload_waybar() -> None:
    proc = Path("/proc")
    signaled = 0
    try:
        entries = proc.iterdir()
    except OSError:
        return
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            executable = (entry / "comm").read_text(encoding="utf-8").strip()
            if executable == "waybar":
                os.kill(int(entry.name), signal.SIGUSR2)
                signaled += 1
        except (OSError, ProcessLookupError, PermissionError, ValueError):
            continue
    if signaled:
        print("Reloaded running Waybar instance(s).")
    else:
        print("Waybar is not running; the selected theme will apply next launch.")


def show_status(p: dict[str, Path]) -> None:
    config = p["config"]
    theme = "not configured"
    if config.exists():
        try:
            theme = json.loads(config.read_text(encoding="utf-8")).get("theme", "synthwave")
        except (OSError, json.JSONDecodeError):
            theme = "settings file is invalid"
    installed = (p["state"] / "install.json").is_file()
    print(f"cyber-panel: {'installed' if installed else 'not installed'}")
    print(f"Theme: {theme}")
    print(f"Waybar config: {p['waybar'] / 'config.jsonc'}")


def uninstall(p: dict[str, Path], purge: bool) -> None:
    state_file = p["state"] / "install.json"
    command = Path(p["prefix"] / "bin/cyber-panel")
    if state_file.is_symlink() or p["app"].is_symlink() or p["waybar"].is_symlink() or (p["app"].exists() and not (p["app"] / ".cyber-panel-managed").is_file()):
        raise RuntimeError("refusing to uninstall an unowned or symlinked cyber-panel installation")
    state = read_state(p)
    command = Path(state.get("command_path", command))
    if command.is_symlink() or (command.exists() and "# cyber-panel-managed-command" not in command.read_text(encoding="utf-8", errors="replace")):
        raise RuntimeError(f"refusing to remove an unowned command or symlink: {command}")
    backup_dir = p["state"] / "backups"
    changed_dir = p["state"] / "before-uninstall"
    for name in MANAGED_FILES:
        target = p["waybar"] / name
        if target.is_symlink():
            raise RuntimeError(f"refusing to restore over a symlink: {target}")
        backup = backup_dir / name
        original_exists = bool(state.get("originals", {}).get(name, False))
        if target.exists() and digest(target) != state.get("installed_hashes", {}).get(name):
            changed_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, changed_dir / name)
            print(f"Preserved your edited {name} at {changed_dir / name}.")
        if original_exists and backup.is_file():
            atomic_write(target, backup.read_bytes(), backup.stat().st_mode & 0o777)
        elif target.exists():
            target.unlink()

    command.unlink(missing_ok=True)
    shutil.rmtree(p["app"] / "src/cyber_panel", ignore_errors=True)
    shutil.rmtree(p["app"] / "themes", ignore_errors=True)
    (p["app"] / "config.jsonc").unlink(missing_ok=True)
    (p["app"] / ".cyber-panel-managed").unlink(missing_ok=True)
    for directory in (p["app"] / "src", p["app"]):
        try:
            directory.rmdir()
        except OSError:
            pass
    if purge:
        p["config"].unlink(missing_ok=True)
        try:
            p["config"].parent.rmdir()
        except OSError:
            pass
        shutil.rmtree(p["state"], ignore_errors=True)
    print("cyber-panel was uninstalled; original Waybar files were restored when available.")
    if not purge:
        print(f"Settings and recovery copies remain in {p['state']}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cyber-panel", description="Manage the cyber-panel Waybar setup.")
    parser.add_argument("--theme", nargs="?", const="", metavar="NAME", help="show the current theme or select synthwave/greenline")
    parser.add_argument("--status", action="store_true", help="show install and theme status")
    parser.add_argument("--uninstall", action="store_true", help="restore previous Waybar files and uninstall")
    parser.add_argument("--purge", action="store_true", help="with --uninstall, also delete cyber-panel settings and recovery copies")
    args = parser.parse_args(argv)
    if args.purge and not args.uninstall:
        parser.error("--purge requires --uninstall")
    p = paths()
    try:
        if args.uninstall:
            if args.purge:
                print("This removes cyber-panel settings and all its recovery copies after restoring the previous Waybar files.")
                if input("Type cyber-panel to confirm: ").strip() != "cyber-panel":
                    print("Cancelled.")
                    return 1
            uninstall(p, args.purge)
        elif args.theme is not None:
            if args.theme:
                apply_theme(args.theme, p)
            else:
                settings = p["config"]
                theme = "synthwave"
                if settings.is_file():
                    theme = json.loads(settings.read_text(encoding="utf-8")).get("theme", theme)
                print(f"Current theme: {theme}; available: {', '.join(THEMES)}")
        else:
            show_status(p)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"cyber-panel: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
