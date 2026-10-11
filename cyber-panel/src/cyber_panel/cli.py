#!/usr/bin/env python3
"""Manage cyber-panel's user-scoped Waybar configuration and themes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

THEMES = ("synthwave", "greenline", "husky")
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
        restart_waybar()
    print(f"Theme set to {name}.")


def _running_waybars() -> list[Path]:
    instances = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid() or (entry / "comm").read_text().strip() != "waybar":
                continue
            env = _process_environment(entry)
            if any(os.environ.get(key) and env.get(key) != os.environ[key]
                   for key in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR")):
                continue
            instances.append(entry)
        except OSError:
            continue
    return instances


def _process_environment(entry: Path) -> dict[str, str]:
    return dict(item.split("=", 1) for item in
                os.fsdecode((entry / "environ").read_bytes()).split("\0") if "=" in item)


def _restart_process(entry: Path, log) -> subprocess.Popen | None:
    # A pidfd targets the original process even if its PID is later reused.
    try:
        handle = os.pidfd_open(int(entry.name))
    except ProcessLookupError:
        return None
    try:
        if select.select([handle], [], [], 0)[0]:
            return None
        args = [os.fsdecode(arg) for arg in (entry / "cmdline").read_bytes().split(b"\0") if arg]
        executable = os.readlink(entry / "exe")
        cwd = os.readlink(entry / "cwd")
        env = _process_environment(entry)
        if not args or not Path(executable).is_file() or not Path(cwd).is_dir():
            raise RuntimeError("Cannot safely relaunch this Waybar process; restart it manually.")
        signal.pidfd_send_signal(handle, signal.SIGTERM)
        if not select.select([handle], [], [], 5)[0]:
            raise RuntimeError("Waybar did not exit within 5 seconds; no duplicate was started.")
        return subprocess.Popen(args, executable=executable, cwd=cwd, env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, close_fds=True)
    finally:
        os.close(handle)


def restart_waybar(start_if_missing: bool = False) -> None:
    # Waybar 0.15.0's MPRIS callbacks can outlive a module after SIGUSR2.
    # Restart the process so later player events cannot reach deleted widgets.
    if not os.environ.get("WAYLAND_DISPLAY"):
        if start_if_missing:
            raise RuntimeError("Run cyber-panel --restart from your graphical session.")
        print("No graphical session; the selected theme will apply next launch.")
        return
    state = paths()["state"]
    if state.is_symlink():
        raise RuntimeError(f"Refusing symlinked state directory: {state}")
    state.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    with os.fdopen(os.open(state / "waybar-restart.lock", flags, 0o600), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        instances = _running_waybars()
        if not instances and not start_if_missing:
            print("Waybar is not running; the selected theme will apply next launch.")
            return
        log_path = state / "waybar.log"
        with os.fdopen(os.open(log_path, flags | os.O_APPEND, 0o600), "a") as log:
            children = []
            for entry in instances:
                child = _restart_process(entry, log)
                if child is not None:
                    children.append(child)
            if not instances:
                executable = shutil.which("waybar")
                if not executable or not os.environ.get("WAYLAND_DISPLAY"):
                    raise RuntimeError("Start Waybar from your graphical session with waybar installed.")
                children.append(subprocess.Popen([executable], stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, start_new_session=True, close_fds=True))
            time.sleep(0.2)
            if any(child.poll() is not None for child in children):
                raise RuntimeError(f"Waybar exited during startup; see {log_path}")
        print(f"Waybar running after a clean restart; log: {log_path}")


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
    parser.add_argument("--theme", nargs="?", const="", metavar="NAME", help="show the current theme or select synthwave/greenline/husky")
    parser.add_argument("--status", action="store_true", help="show install and theme status")
    parser.add_argument("--restart", action="store_true", help="restart Waybar safely, or start it if stopped")
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
        elif args.restart:
            restart_waybar(start_if_missing=True)
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
