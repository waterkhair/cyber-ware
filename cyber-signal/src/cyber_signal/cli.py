"""Command-line interface for cyber-signal."""

from __future__ import annotations

import shutil
import os
import subprocess
import sys
import tempfile
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
  cyber-signal --theme [synthwave|greenline] [--no-reload] Save/apply a theme
  cyber-signal --enable                      Enable user services and timers
  cyber-signal --disable                     Stop and disable user services
  cyber-signal --status                      Show component status
  cyber-signal --uninstall [--purge]          Uninstall (optionally remove user data)
  cyber-signal --help                        Show this help

Checks are configured in ~/.config/cyber-signal/config.json.
"""


def _theme(name: str | None, *, reload_mako: bool = True) -> int:
    config = load_config()
    if name is None:
        print(f"Current theme: {config['theme']}")
        print(f"Available themes: {' | '.join(THEMES)}")
        print(f"Mako config: {config_home() / 'mako/config'}")
        return 0
    if name not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    source = Path(__file__).parent / "themes" / f"{name}.mako"
    if not source.is_file():
        raise RuntimeError(f"bundled theme file is missing: {source}")
    config_dir().mkdir(parents=True, exist_ok=True)
    active = config_dir() / "active.mako"
    theme_text = source.read_text(encoding="utf-8")
    active.write_text(theme_text, encoding="utf-8")
    config["theme"] = name
    atomic_json(config_dir() / "config.json", config)

    mako_config = _write_mako_styles(theme_text)
    makoctl = shutil.which("makoctl")
    if reload_mako and mako_config and makoctl:
        reload_result = subprocess.run([makoctl, "reload"], check=False,
                                       text=True, capture_output=True)
        if reload_result.returncode != 0:
            detail = (reload_result.stderr or reload_result.stdout).strip()
            print(f"Theme files were updated, but Mako could not reload: {detail or 'unknown error'}",
                  file=sys.stderr)
            return 1
    elif reload_mako and not mako_config:
        print("Mako is not installed; the theme is saved but cannot be applied yet.", file=sys.stderr)
    print(f"Theme set to {name}; Mako styles: {config_home() / 'mako/config'}")
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


def _write_mako_styles(theme_text: str) -> bool:
    """Replace cyber-signal's marked style block, leaving other Mako rules intact."""
    if not (shutil.which("mako") or shutil.which("makoctl")):
        return False
    path = config_home() / "mako/config"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError(f"refusing unsafe Mako config destination: {path}")
    try:
        original = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        original = ""

    start = "# BEGIN cyber-signal managed theme"
    end = "# END cyber-signal managed theme"
    legacy_include = f"include={config_dir() / 'active.mako'}"
    output: list[str] = []
    in_block = False
    for line in original.splitlines(keepends=True):
        marker = line.rstrip("\r\n")
        if marker == start:
            if in_block:
                raise RuntimeError("Mako config contains nested cyber-signal theme markers")
            in_block = True
            continue
        if in_block:
            if marker == end:
                in_block = False
            continue
        if marker == legacy_include:
            continue
        output.append(line)
    if in_block:
        raise RuntimeError("Mako config has an incomplete cyber-signal theme block; it was left unchanged")

    base = "".join(output)
    if base and not base.endswith("\n"):
        base += "\n"
    if base and not base.endswith("\n\n"):
        base += "\n"
    block = f"{start}\n{theme_text.rstrip()}\n{end}\n"
    fd, temporary = tempfile.mkstemp(prefix=".config.cyber-signal.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(base + block)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def _remove_mako_block() -> bool:
    """Remove only cyber-signal's installer-owned Mako block."""
    path = config_home() / "mako/config"
    try:
        original = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    if path.is_symlink():
        return False
    start = "# BEGIN cyber-signal managed theme"
    end = "# END cyber-signal managed theme"
    legacy_include = f"include={config_dir() / 'active.mako'}"
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
        if marker == legacy_include:
            removed = True
            continue
        output.append(line)
    if in_block:
        # Incomplete markers: preserve the file instead of risking user config.
        return False
    if removed:
        fd, temporary = tempfile.mkstemp(prefix=".config.cyber-signal.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write("".join(output))
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
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
    executable = Path.home() / ".local/bin/cyber-signal"
    manifest_owned = False
    try:
        import json
        manifest = json.loads(install_manifest().read_text(encoding="utf-8"))
        executable = Path(manifest.get("executable", executable))
        manifest_owned = manifest.get("executable") == str(executable)
    except (FileNotFoundError, ValueError, OSError):
        pass
    if executable.is_symlink() or (executable.exists() and "# cyber-signal-managed-command" not in executable.read_text(encoding="utf-8", errors="replace") and not manifest_owned):
        print(f"Refusing to remove an unowned command or symlink: {executable}", file=sys.stderr)
        return 1
    if app_dir().is_symlink() or (app_dir().exists() and not (app_dir() / ".cyber-signal-managed").is_file() and not manifest_owned):
        print(f"Refusing to remove an unowned or symlinked application directory: {app_dir()}", file=sys.stderr)
        return 1
    _disable()
    unit_dir = config_home() / "systemd/user"
    for name in ("network.service", "updates.service", "updates.timer", "disk.service", "disk.timer"):
        (unit_dir / f"cyber-signal-{name}").unlink(missing_ok=True)
    if shutil.which("systemctl"):
        _systemctl("daemon-reload")
    executable.unlink(missing_ok=True)
    shutil.rmtree(app_dir() / "src/cyber_signal", ignore_errors=True)
    (app_dir() / "install.json").unlink(missing_ok=True)
    (app_dir() / ".cyber-signal-managed").unlink(missing_ok=True)
    for directory in (app_dir() / "src", app_dir()):
        try:
            directory.rmdir()
        except OSError:
            pass
    removed_mako_block = _remove_mako_block()
    print("Removed cyber-signal command, application files, and user service units.")
    if removed_mako_block:
        print("Removed cyber-signal's managed Mako styles; all other Mako settings were preserved.")
    else:
        print("No managed Mako style block found; Mako config was preserved.")
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
        if args[0] == "--theme" and len(args) <= 3:
            no_reload = "--no-reload" in args[1:]
            theme_args = [arg for arg in args[1:] if arg != "--no-reload"]
            if len(theme_args) > 1:
                raise ValueError("usage: cyber-signal --theme [synthwave|greenline] [--no-reload]")
            return _theme(theme_args[0] if theme_args else None, reload_mako=not no_reload)
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
