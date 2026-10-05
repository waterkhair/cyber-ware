"""Command-line interface for cyber-deck."""

from __future__ import annotations

import os
import json
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import (THEMES, clipboard_is_enabled, config_dir, current_theme,
                     data_dir, fuzzel_config, set_clipboard_enabled, set_theme)

USAGE = """cyber-deck — themed Fuzzel application launcher

Usage:
  cyber-deck                              Toggle the application launcher
  cyber-deck --clipboard                  Pick a saved clipboard item
  cyber-deck --clipboard enable|disable   Enable or disable history collection
  cyber-deck --theme [synthwave|greenline|husky] Show or set the theme
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
    if clipboard_is_enabled():
        missing = [name for name in ("cliphist", "wl-copy", "wl-paste") if not shutil.which(name)]
        if missing:
            print(f"Clipboard feature enabled, but missing: {', '.join(missing)}", file=sys.stderr)
            return 1
        print("Clipboard history: enabled; cliphist and wl-copy are available")
    else:
        print("Clipboard history: disabled")
    return 0


def _clipboard() -> int:
    if not clipboard_is_enabled():
        raise RuntimeError("clipboard history is disabled; run cyber-deck --clipboard enable first")
    cliphist, wl_copy, fuzzel = (shutil.which(name) for name in ("cliphist", "wl-copy", "fuzzel"))
    if not cliphist or not wl_copy or not fuzzel:
        missing = [name for name, path in (("cliphist", cliphist), ("wl-copy", wl_copy), ("fuzzel", fuzzel)) if not path]
        raise RuntimeError(f"clipboard picker dependencies are missing: {', '.join(missing)}")
    listing = subprocess.run([cliphist, "list"], capture_output=True, check=False)
    if listing.returncode:
        raise RuntimeError("cliphist could not read clipboard history")
    if not listing.stdout:
        print("Clipboard history is empty.")
        return 0
    menu = subprocess.run([fuzzel, "--dmenu", f"--config={fuzzel_config()}"],
                          input=listing.stdout, capture_output=True, check=False)
    if menu.returncode:
        return 0 if menu.returncode in (1, 130) else menu.returncode
    selected = menu.stdout.strip(b"\r\n")
    item_id, separator, preview = selected.partition(b"\t")
    if not separator or not re.fullmatch(rb"\s*\d+\s*", item_id):
        raise RuntimeError("Fuzzel returned an invalid clipboard history row")
    decoded = subprocess.run([cliphist, "decode"], input=selected + b"\n",
                             capture_output=True, check=False)
    if decoded.returncode:
        raise RuntimeError("cliphist could not decode the selected history item")
    image_type = re.search(rb"\[(image/[A-Za-z0-9.+-]+)\]", preview)
    copy_command = [wl_copy]
    if image_type:
        copy_command.extend(["--type", image_type.group(1).decode("ascii")])
    copied = subprocess.run(copy_command, input=decoded.stdout, capture_output=True, check=False)
    if copied.returncode:
        detail = (copied.stderr or copied.stdout).decode(errors="replace").strip()
        raise RuntimeError(f"wl-copy could not restore the selected item: {detail or 'unknown error'}")
    return 0


def _stop_clipboard_watcher() -> None:
    # Stop only this specific cliphist watcher, leaving other wl-paste users alone.
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            argv = [part.decode(errors="replace") for part in
                    entry.joinpath("cmdline").read_bytes().split(b"\0") if part]
        except (OSError, ProcessLookupError, PermissionError):
            continue
        if argv and Path(argv[0]).name == "wl-paste" and "--watch" in argv and \
                any(Path(arg).name == "cliphist" for arg in argv) and argv[-1:] == ["store"]:
            try:
                os.kill(int(entry.name), signal.SIGTERM)
            except ProcessLookupError:
                pass


def _set_clipboard(enabled: bool) -> int:
    if enabled:
        missing = [name for name in ("cliphist", "wl-copy", "wl-paste") if not shutil.which(name)]
        if missing:
            raise RuntimeError(f"clipboard history requires: {', '.join(missing)}")
    set_clipboard_enabled(enabled)
    if not enabled:
        _stop_clipboard_watcher()
    state = "enabled" if enabled else "disabled"
    print(f"Clipboard history {state}. Run hyprctl reload to update Super+V and session collection.")
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
    if clipboard_is_enabled():
        set_clipboard_enabled(False)
        _stop_clipboard_watcher()
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
                raise ValueError("use: cyber-deck --theme [synthwave|greenline|husky]")
            fuzzel_config(args[1])
            set_theme(args[1])
            print(f"Theme set to {args[1]}; it will apply the next time the launcher opens.")
            return 0
        if args == ["--check"]:
            return _check()
        if args == ["--clipboard"]:
            return _clipboard()
        if args == ["--clipboard", "enable"]:
            return _set_clipboard(True)
        if args == ["--clipboard", "disable"]:
            return _set_clipboard(False)
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
