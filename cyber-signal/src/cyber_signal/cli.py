"""Command-line interface for cyber-signal."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .checks import CHECKS, run_check
from .config import (THEMES, app_dir, atomic_json, config_dir, config_home,
                     install_manifest, load_config, state_dir)

USAGE = """cyber-signal — lightweight user-level system notifications

Usage:
  cyber-signal --check network|updates|disk  Run a check once
  cyber-signal --watch network               Monitor network state changes
  cyber-signal --test                        Send a preview notification
  cyber-signal --theme [synthwave|greenline] Show or change Mako theme
  cyber-signal --enable                      Enable user services and timers
  cyber-signal --disable                     Stop and disable user services
  cyber-signal --status                      Show component status
  cyber-signal --uninstall [--purge]          Uninstall (optionally remove user data)
  cyber-signal --help                        Show this help

Checks are configured in ~/.config/cyber-signal/config.json.
"""


def _theme(name: str | None) -> int:
    config = load_config()
    if name is None:
        print(f"Current theme: {config['theme']}")
        print(f"Available themes: {' | '.join(THEMES)}")
        print(f"Mako include target: {config_dir() / 'active.mako'}")
        return 0
    if name not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    source = Path(__file__).parent / "themes" / f"{name}.mako"
    if not source.is_file():
        raise RuntimeError(f"bundled theme file is missing: {source}")
    config_dir().mkdir(parents=True, exist_ok=True)
    active = config_dir() / "active.mako"
    active.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    config["theme"] = name
    atomic_json(config_dir() / "config.json", config)
    makoctl = shutil.which("makoctl")
    if makoctl:
        subprocess.run([makoctl, "reload"], check=False)
    print(f"Theme set to {name}; Mako include: include={active}")
    return 0


def _systemctl(action: str, *units: str) -> int:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        raise RuntimeError("systemctl not found; cyber-signal user services require systemd")
    return subprocess.run([systemctl, "--user", action, *units], check=False).returncode


def _enable() -> int:
    units = ["cyber-signal-network.service", "cyber-signal-updates.timer", "cyber-signal-disk.timer"]
    if _systemctl("daemon-reload") != 0:
        raise RuntimeError("systemd user manager is unavailable; try this from your desktop session")
    if _systemctl("enable", "--now", *units) != 0:
        raise RuntimeError("could not enable cyber-signal services; inspect systemctl --user status")
    print("Enabled network monitoring and update/disk timers for this user.")
    return 0


def _disable() -> int:
    units = ["cyber-signal-network.service", "cyber-signal-updates.timer", "cyber-signal-disk.timer",
             "cyber-signal-updates.service", "cyber-signal-disk.service"]
    result = _systemctl("disable", "--now", *units)
    print("Stopped and disabled cyber-signal user services." if result == 0
          else "Some units could not be stopped; check the systemd user manager.")
    return result


def _watch(kind: str) -> int:
    if kind != "network":
        raise ValueError("only --watch network is currently supported")
    config = load_config()
    if not config["checks"].get("network", True):
        print("Network notifications are disabled in config.", file=sys.stderr)
        return 0
    if not shutil.which("nmcli"):
        print("Network monitoring skipped: nmcli is missing (install NetworkManager).", file=sys.stderr)
        return 0
    # Establish a baseline without generating a login-time notification.
    from .checks import check_network

    check_network(baseline=True)
    interval = config["network_poll_seconds"]
    while True:
        time.sleep(interval)
        try:
            run_check("network")
        except (OSError, RuntimeError) as error:
            print(f"cyber-signal: network check: {error}", file=sys.stderr)


def _status() -> int:
    config = load_config()
    print(f"cyber-signal {__version__}")
    print(f"Theme: {config['theme']}")
    print(f"Configuration: {config_dir() / 'config.json'}")
    print(f"State: {state_dir()}")
    print(f"Application: {app_dir()}")
    for unit in ("cyber-signal-network.service", "cyber-signal-updates.timer", "cyber-signal-disk.timer"):
        result = subprocess.run(["systemctl", "--user", "is-active", unit],
                                text=True, capture_output=True, check=False) if shutil.which("systemctl") else None
        print(f"{unit}: {result.stdout.strip() if result and result.stdout.strip() else 'unknown'}")
    return 0


def _remove_mako_include() -> bool:
    """Remove only the installer-owned include block, preserving other config."""
    path = config_home() / "mako/config"
    try:
        original = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    start = "# BEGIN cyber-signal managed theme"
    end = "# END cyber-signal managed theme"
    output: list[str] = []
    in_block = False
    removed = False
    for line in original.splitlines(keepends=True):
        marker = line.rstrip("\r\n")
        if marker == start:
            in_block = True
            removed = True
            continue
        if in_block:
            if marker == end:
                in_block = False
            continue
        output.append(line)
    if in_block:
        # Incomplete markers: preserve the file instead of risking user config.
        return False
    if removed:
        path.write_text("".join(output), encoding="utf-8")
        makoctl = shutil.which("makoctl")
        if makoctl:
            subprocess.run([makoctl, "reload"], check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    return removed


def _uninstall(args: list[str]) -> int:
    if args not in ([], ["--purge"]):
        raise ValueError("usage: cyber-signal --uninstall [--purge]")
    purge = args == ["--purge"]
    if purge:
        answer = input("Type cyber-signal to remove its config, state, and generated Mako theme: ")
        if answer != "cyber-signal":
            print("Purge cancelled; nothing was removed.")
            return 1
    _disable()
    executable = Path.home() / ".local/bin/cyber-signal"
    try:
        import json
        manifest = json.loads(install_manifest().read_text(encoding="utf-8"))
        executable = Path(manifest.get("executable", executable))
    except (FileNotFoundError, ValueError, OSError):
        pass
    unit_dir = config_home() / "systemd/user"
    for name in ("network.service", "updates.service", "updates.timer", "disk.service", "disk.timer"):
        (unit_dir / f"cyber-signal-{name}").unlink(missing_ok=True)
    if shutil.which("systemctl"):
        _systemctl("daemon-reload")
    executable.unlink(missing_ok=True)
    shutil.rmtree(app_dir(), ignore_errors=True)
    removed_mako_include = _remove_mako_include()
    print("Removed cyber-signal command, application files, and user service units.")
    if removed_mako_include:
        print("Removed cyber-signal's managed Mako include; all other Mako settings were preserved.")
    else:
        print("No managed Mako include found; Mako config was preserved.")
    if purge:
        shutil.rmtree(config_dir(), ignore_errors=True)
        shutil.rmtree(state_dir(), ignore_errors=True)
        print("Removed cyber-signal configuration, generated theme, and state.")
    else:
        print("Personal config, generated Mako theme, and state were preserved. Use --purge to remove them.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    try:
        if args in ([], ["--help"], ["-h"]):
            print(USAGE, end="")
            return 0
        if args == ["--version"]:
            print(__version__)
            return 0
        if args[0] == "--check" and len(args) == 2 and args[1] in CHECKS:
            load_config()
            if args[1] == "network":
                # A one-shot invocation reports the current state, not a transition.
                from .checks import network_status
                state, description = network_status()
                print(f"{state}: {description}")
                return 0
            changed = run_check(args[1])
            print("Notification sent." if changed else "No new alert.")
            return 0
        if args == ["--test"]:
            from .notify import send
            send("cyber-signal test", "Notifications are reaching your desktop.")
            return 0
        if args[0] == "--theme" and len(args) <= 2:
            return _theme(args[1] if len(args) == 2 else None)
        if args == ["--enable"]:
            return _enable()
        if args == ["--disable"]:
            return _disable()
        if args == ["--status"]:
            return _status()
        if args[0] == "--watch" and len(args) == 2:
            return _watch(args[1])
        if args[0] == "--uninstall":
            return _uninstall(args[1:])
        raise ValueError(f"invalid arguments: {' '.join(args)}\nRun cyber-signal --help for usage.")
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"cyber-signal: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
