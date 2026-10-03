"""Command-line interface for cyber-deck."""

from __future__ import annotations

import os
import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import THEMES, config_dir, current_theme, data_dir, fuzzel_config, set_theme

USAGE = """cyber-deck — themed Fuzzel application launcher

Usage:
  cyber-deck                              Toggle the application launcher
  cyber-deck --theme [synthwave|greenline] Show or set the theme
  cyber-deck --check                     Check Fuzzel and theme configs
  cyber-deck --uninstall [--purge]        Uninstall (optionally remove themes)
  cyber-deck --help                      Show this help
"""


def _deck_pids() -> list[int]:
    matches: list[int] = []
    try:
        entries = Path("/proc").iterdir()
    except OSError:
        return matches
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            argv = [part.decode(errors="replace") for part in entry.joinpath("cmdline").read_bytes().split(b"\0") if part]
        except (OSError, ProcessLookupError, PermissionError):
            continue
        if not argv or Path(argv[0]).name != "fuzzel":
            continue
        for index, argument in enumerate(argv):
            option = argument.split("=", 1)[1] if argument.startswith("--config=") else (
                argv[index + 1] if argument == "--config" and index + 1 < len(argv) else None
            )
            if option in {str(config_dir() / "themes" / f"{theme}.ini") for theme in THEMES}:
                matches.append(int(entry.name))
                break
    return matches


def _toggle() -> int:
    config = fuzzel_config()
    pids = _deck_pids()
    if pids:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return 0
    fuzzel = shutil.which("fuzzel")
    if not fuzzel:
        raise RuntimeError("fuzzel was not found; install it with your distribution package manager")
    os.execv(fuzzel, [fuzzel, f"--config={config}"])
    return 0


def _check() -> int:
    fuzzel = shutil.which("fuzzel")
    if not fuzzel:
        raise RuntimeError("fuzzel was not found; install it with your distribution package manager")
    for theme in THEMES:
        config = fuzzel_config(theme)
        result = subprocess.run([fuzzel, "--config", str(config), "--check-config"], check=False)
        if result.returncode:
            return result.returncode
        print(f"{theme}: valid ({config})")
    return 0


def _uninstall(purge: bool) -> int:
    app = data_dir()
    manifest = app / "install.json"
    if manifest.is_symlink():
        raise RuntimeError(f"Refusing a symlinked installation manifest: {manifest}")
    if manifest.is_file():
        recorded = json.loads(manifest.read_text())
        value = recorded.get("command") if isinstance(recorded, dict) else None
        if not isinstance(value, str) or not Path(value).is_absolute() or Path(value).name != "cyber-deck":
            raise RuntimeError(f"Invalid command path in installation manifest: {manifest}")
        command = Path(value)
    else:
        # Support uninstalling installations made before manifests were introduced.
        prefix = Path(os.environ.get("PREFIX", Path.home() / ".local")).expanduser()
        command = prefix / "bin/cyber-deck"
    if command.is_symlink() or (command.exists() and "# cyber-deck-managed-command" not in command.read_text(encoding="utf-8", errors="replace")):
        raise RuntimeError(f"Refusing to remove an unowned command or symlink: {command}")
    if app.is_symlink() or (app.exists() and not (app / ".cyber-deck-managed").is_file()):
        raise RuntimeError(f"Refusing to remove an unowned or symlinked application directory: {app}")
    if config_dir().is_symlink() or (config_dir().exists() and not config_dir().is_dir()):
        raise RuntimeError(f"Refusing an unsafe configuration directory: {config_dir()}")
    if purge:
        print("This removes cyber-deck theme selection and custom theme files.")
        if input("Type cyber-deck to confirm: ").strip() != "cyber-deck":
            print("Cancelled.")
            return 1
    pids = _deck_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and any(Path(f"/proc/{pid}").exists() for pid in pids):
        time.sleep(0.05)
    if any(Path(f"/proc/{pid}").exists() for pid in pids):
        raise RuntimeError("Fuzzel did not close cleanly; uninstall cancelled")
    command.unlink(missing_ok=True)
    if app.exists():
        shutil.rmtree(app)
    if purge:
        shutil.rmtree(config_dir(), ignore_errors=True)
    print("cyber-deck was uninstalled.")
    if not purge:
        print(f"Theme selection and theme files were preserved at {config_dir()}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args:
            return _toggle()
        if args in (["-h"], ["--help"]):
            print(USAGE, end="")
            return 0
        if args[0] == "--theme":
            if len(args) == 1:
                print(f"Current theme: {current_theme()}")
                print(f"Available themes: {' | '.join(THEMES)}")
                return 0
            if len(args) != 2:
                raise ValueError("use: cyber-deck --theme [synthwave|greenline]")
            fuzzel_config(args[1])
            set_theme(args[1])
            print(f"Theme set to {args[1]}; it will apply the next time the launcher opens.")
            return 0
        if args == ["--check"]:
            return _check()
        if args[0] == "--uninstall":
            if args[1:] not in ([], ["--purge"]):
                raise ValueError("use: cyber-deck --uninstall [--purge]")
            return _uninstall(args[1:] == ["--purge"])
        raise ValueError(f"unknown option: {args[0]}")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"cyber-deck: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
