"""Standalone launcher and control command for cyber-wave."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import THEMES, current_theme, load_config, paths, set_theme

CLASS = "org.cyber-ware.cyber-wave"
SPECIAL = "Radio"


def _clients() -> list[dict]:
    try:
        result = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2, check=True)
        clients = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    return clients if isinstance(clients, list) else []


def _dispatch(*args: str) -> bool:
    if not args:
        return False
    if args[0] == "togglespecialworkspace" and len(args) == 2:
        expression = f"hl.dispatch(hl.dsp.workspace.toggle_special({json.dumps(args[1])}))"
    elif args[0] == "closewindow" and len(args) == 2:
        address = args[1].removeprefix("address:")
        if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
            return False
        encoded_address = json.dumps(address)
        expression = (
            "for _, w in ipairs(hl.get_windows()) do "
            f"if w.address == {encoded_address} then "
            "hl.dispatch(hl.dsp.window.close({window = w})); break end end"
        )
    else:
        return False
    try:
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and "error" not in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _ensure_picker_placement(client: dict) -> bool:
    address = client.get("address")
    if not isinstance(address, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", address):
        return False
    encoded_address = json.dumps(address)
    expression = (
        "for _, w in ipairs(hl.get_windows()) do "
        f"if w.address == {encoded_address} and w.class == {json.dumps(CLASS)} then "
        f"hl.dispatch(hl.dsp.window.move({{workspace = {json.dumps('special:' + SPECIAL)}, follow = false, window = w}})); "
        "hl.dispatch(hl.dsp.window.float({action = \"set\", window = w})); "
        "hl.dispatch(hl.dsp.window.resize({x = 1050, y = 720, relative = false, window = w})); "
        "hl.dispatch(hl.dsp.window.center({window = w})); break end end"
    )
    try:
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and "error" not in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _focus_picker(client: dict) -> bool:
    address = client.get("address")
    if not isinstance(address, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", address):
        return False
    expression = (
        "for _, w in ipairs(hl.get_windows()) do "
        f"if w.address == {json.dumps(address)} and w.class == {json.dumps(CLASS)} then "
        "hl.dispatch(hl.dsp.focus({window = w})); break end end"
    )
    try:
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and "error" not in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _radio_workspace_is_active() -> bool:
    try:
        result = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True, timeout=2, check=True)
        active = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False
    return isinstance(active, dict) and active.get("name") == "special:Radio"


def toggle() -> int:
    clients = _clients()
    existing = next((c for c in clients if CLASS in (c.get("class"), c.get("initialClass"))), None)
    if existing:
        if existing.get("workspace", {}).get("name") != f"special:{SPECIAL}" or not existing.get("floating"):
            if not _ensure_picker_placement(existing):
                raise RuntimeError("Could not place the picker on the floating Radio workspace")
        was_visible = bool(existing.get("visible"))
        if not _dispatch("togglespecialworkspace", SPECIAL):
            raise RuntimeError("Could not toggle the Radio special workspace")
        if not was_visible and not _focus_picker(existing):
            raise RuntimeError("Picker is visible, but Hyprland could not focus it")
        return 0
    p = paths()
    command = str(p["command"])
    subprocess.Popen(
        [command, "--ui"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        clients = _clients()
        client = next((c for c in clients if CLASS in (c.get("class"), c.get("initialClass"))), None)
        if client is not None:
            if not _radio_workspace_is_active():
                if not _dispatch("togglespecialworkspace", SPECIAL):
                    raise RuntimeError("Picker opened, but the Radio workspace could not be shown")
                if not _focus_picker(client):
                    raise RuntimeError("Picker opened, but Hyprland could not focus it")
            return 0
        time.sleep(0.08)
    raise RuntimeError("GTK picker started, but Hyprland did not report the cyber-wave window")


def uninstall(purge: bool) -> int:
    p = paths()
    manifest = p["data"] / "install.json"
    if p["data"].is_symlink() or (p["data"].exists() and not (p["data"] / ".cyber-wave-managed").is_file()):
        raise RuntimeError(f"Refusing to remove an unowned application directory: {p['data']}")
    if manifest.is_symlink():
        raise RuntimeError(f"Refusing symlinked install manifest: {manifest}")
    if manifest.is_file():
        details = json.loads(manifest.read_text(encoding="utf-8"))
        recorded = details.get("command") if isinstance(details, dict) else None
        if not isinstance(recorded, str) or not os.path.isabs(recorded) or os.path.basename(recorded) != "cyber-wave":
            raise RuntimeError("Invalid cyber-wave install manifest")
        command = Path(recorded)
    else:
        command = p["command"]
    if command.is_symlink() or (command.exists() and "# cyber-wave-managed-command" not in command.read_text(encoding="utf-8", errors="replace")):
        raise RuntimeError(f"Refusing to remove an unowned command: {command}")
    config_dir = p["config"].parent
    if purge and (config_dir.is_symlink() or (config_dir.exists() and not config_dir.is_dir())):
        raise RuntimeError(f"Refusing unsafe configuration directory: {config_dir}")
    if purge and input("Type cyber-wave to remove your station list and settings: ").strip() != "cyber-wave":
        print("Cancelled.")
        return 1
    from .player import _request
    _request(["quit"])
    for client in _clients():
        if CLASS in (client.get("class"), client.get("initialClass")) and client.get("address"):
            _dispatch("closewindow", f"address:{client['address']}")
    command.unlink(missing_ok=True)
    shutil.rmtree(p["data"], ignore_errors=False)
    if purge:
        p["config"].unlink(missing_ok=True)
        p["theme"].unlink(missing_ok=True)
        try:
            config_dir.rmdir()
        except OSError:
            pass
    print("Uninstalled cyber-wave." + (" Removed configuration." if purge else " Kept station configuration."))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cyber-wave", description="Persistent floating internet-radio picker")
    parser.add_argument("--ui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--check", action="store_true", help="check required commands and station configuration")
    parser.add_argument("--theme", choices=THEMES, help="select the cyber-wave theme")
    parser.add_argument("--uninstall", action="store_true", help="remove cyber-wave, keeping configuration")
    parser.add_argument("--purge", action="store_true", help="also remove cyber-wave configuration")
    args = parser.parse_args(argv)
    try:
        if args.purge and not args.uninstall:
            parser.error("--purge requires --uninstall")
        if args.uninstall:
            return uninstall(args.purge)
        if args.theme:
            set_theme(args.theme)
            print(f"cyber-wave theme set to {args.theme}.")
            return 0
        config = load_config()
        if args.check:
            required = ("python3", "hyprctl", "mpv")
            missing = [item for item in required if not shutil.which(item)]
            try:
                import gi

                gi.require_version("Gtk", "4.0")
                from gi.repository import Gtk  # noqa: F401
            except (ImportError, ValueError):
                missing.append("GTK 4 Python bindings (gtk4 and python-gobject)")
            if missing:
                print("Missing required commands: " + ", ".join(missing), file=sys.stderr)
                return 1
            print(f"cyber-wave is ready: {len(config['stations'])} station(s), theme {current_theme()}.")
            return 0
        if args.ui:
            from .app import run
            return run(config)
        return toggle()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"cyber-wave: {error}", file=sys.stderr)
        return 1
