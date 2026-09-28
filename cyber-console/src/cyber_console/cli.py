#!/usr/bin/env python3
"""Single-command toggles for dedicated Ghostty TUI windows."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path


def paths() -> dict[str, Path]:
    home = Path.home()
    return {
        "config": Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "cyber-console/config.json",
        "data": Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "cyber-console",
        "prefix": Path(os.environ.get("PREFIX", home / ".local")),
        "command": Path(os.environ.get("CYBER_CONSOLE_BIN_PATH", Path(os.environ.get("PREFIX", home / ".local")) / "bin/cyber-console")),
    }


def load_config() -> dict:
    p = paths()
    config_path = p["config"]
    if not config_path.is_file():
        template = p["data"] / "config.example.json"
        if not template.is_file():
            raise RuntimeError("cyber-console is not installed (configuration template is missing).")
        config = json.loads(template.read_text(encoding="utf-8"))
    else:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read {config_path}: {error}") from error
    if not isinstance(config, dict) or not isinstance(config.get("applications"), dict):
        raise RuntimeError("Configuration must contain an applications object.")
    if not isinstance(config.get("terminal"), str) or not config["terminal"]:
        raise RuntimeError("Configuration terminal must be a non-empty executable name or path.")
    if not config["applications"]:
        raise RuntimeError("Configuration must define at least one application.")
    for name, app in config["applications"].items():
        if not isinstance(name, str) or not isinstance(app, dict):
            raise RuntimeError("Each application must be a named JSON object.")
        if not isinstance(app.get("class"), str) or not app["class"]:
            raise RuntimeError(f"Application {name!r} needs a non-empty class.")
        if not isinstance(app.get("title", name), str):
            raise RuntimeError(f"Application {name!r} title must be a string.")
        command = app.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise RuntimeError(f"Application {name!r} command must be a non-empty string array.")
    return config


def list_apps(config: dict) -> int:
    print(f"Terminal: {config['terminal']}")
    for name, app in config["applications"].items():
        executable = app.get("command", [""])[0]
        available = shutil.which(executable) is not None
        label = "ready" if available else "missing executable"
        print(f"{name:<10} {label}: {executable}")
    return 0


def matching_process(class_name: str) -> int | None:
    try:
        proc_entries = Path("/proc").iterdir()
    except OSError:
        return None
    for entry in proc_entries:
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
            argv = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
            if not argv or Path(argv[0]).name != "ghostty":
                continue
            for index, arg in enumerate(argv):
                if arg == f"--class={class_name}" or (arg == "--class" and index + 1 < len(argv) and argv[index + 1] == class_name):
                    return int(entry.name)
        except (OSError, ProcessLookupError, PermissionError, ValueError):
            continue
    return None


def client_address(class_name: str) -> str | None:
    if not shutil.which("hyprctl"):
        return None
    try:
        result = subprocess.run(
            ["hyprctl", "clients", "-j"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        clients = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    if not isinstance(clients, list):
        return None
    for client in clients:
        if isinstance(client, dict) and class_name in (client.get("class"), client.get("initialClass")):
            address = client.get("address")
            if isinstance(address, str) and address:
                return address
    return None


def close_window(class_name: str) -> bool:
    address = client_address(class_name)
    if address and shutil.which("hyprctl"):
        try:
            result = subprocess.run(
                ["hyprctl", "dispatch", "closewindow", f"address:{address}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                print("Toggled the floating window closed.")
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    pid = matching_process(class_name)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        print("Closed the dedicated Ghostty process.")
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def toggle(name: str, config: dict) -> int:
    app = config["applications"].get(name)
    if not isinstance(app, dict):
        print(f"Unknown tool {name!r}; run cyber-console --list.", file=sys.stderr)
        return 2
    class_name = app.get("class")
    title = app.get("title", name)
    command = app.get("command")
    terminal = config["terminal"]
    if not isinstance(class_name, str) or not class_name or not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        print(f"Invalid application entry for {name!r} in {paths()['config']}.", file=sys.stderr)
        return 1
    if close_window(class_name):
        return 0
    missing = [item for item in (terminal, command[0]) if shutil.which(item) is None]
    if missing:
        print("Missing executable(s): " + ", ".join(missing), file=sys.stderr)
        return 1
    argv = [terminal, f"--class={class_name}", f"--title={title}", "-e", *command]
    try:
        os.execvp(terminal, argv)
    except OSError as error:
        print(f"Could not start {name}: {error}", file=sys.stderr)
        return 1
    return 0


def uninstall(purge: bool) -> int:
    p = paths()
    if purge:
        print("This removes cyber-console configuration and saved tool settings.")
        if input("Type cyber-console to confirm: ").strip() != "cyber-console":
            print("Cancelled.")
            return 1
    p["command"].unlink(missing_ok=True)
    shutil.rmtree(p["data"], ignore_errors=True)
    if purge:
        p["config"].unlink(missing_ok=True)
        try:
            p["config"].parent.rmdir()
        except OSError:
            pass
    print("cyber-console was uninstalled. Hyprland rules and bindings were not changed.")
    if not purge:
        print(f"Configuration was preserved at {p['config']}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cyber-console", description="Toggle floating Ghostty terminal tools.")
    parser.add_argument("tool", nargs="?", help="tool to toggle")
    parser.add_argument("--list", action="store_true", help="list configured tools and check their commands")
    parser.add_argument("--check", action="store_true", help="check Ghostty, Hyprland integration, and configured tools")
    parser.add_argument("--uninstall", action="store_true", help="uninstall cyber-console but keep configuration")
    parser.add_argument("--purge", action="store_true", help="with --uninstall, also remove cyber-console configuration")
    args = parser.parse_args(argv)
    if args.purge and not args.uninstall:
        parser.error("--purge requires --uninstall")
    if args.uninstall:
        return uninstall(args.purge)
    try:
        config = load_config()
        if args.list:
            return list_apps(config)
        if args.check:
            required = (config["terminal"], "hyprctl")
            missing = [name for name in required if shutil.which(name) is None]
            if missing:
                print("Missing required executable(s): " + ", ".join(missing), file=sys.stderr)
                return 1
            print(f"Required commands available: {', '.join(required)}")
            return list_apps(config)
        if not args.tool:
            return list_apps(config)
        return toggle(args.tool, config)
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"cyber-console: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
